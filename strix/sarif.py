"""SARIF (Static Analysis Results Interchange Format) support for Strix.

Provides conversion of Strix vulnerability reports to SARIF 2.1.0 format and
upload to the GitHub code-scanning API.
"""

import base64
import gzip
import hashlib
import json
import logging
from typing import Any

import requests


logger = logging.getLogger(__name__)

_SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
)
_SARIF_VERSION = "2.1.0"
_TOOL_NAME = "Strix"
_TOOL_URI = "https://github.com/seonghobae/strix"

_SEVERITY_LEVEL: dict[str, str] = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}

# Fallback CVSS scores used when a report has no numeric cvss value.
# GitHub code scanning interprets security-severity as a CVSS-like numeric score
# (0.0–10.0); it must never be an empty string or a text label.
_SEVERITY_DEFAULT_CVSS: dict[str, str] = {
    "critical": "9.5",
    "high": "8.0",
    "medium": "5.5",
    "low": "2.0",
    "info": "0.0",
}


def _make_rule_id(report: dict[str, Any]) -> str:
    """Generate a deterministic rule ID for a vulnerability report."""
    cwe = report.get("cwe")
    if cwe:
        return cwe
    title = report.get("title", "unknown")
    digest = hashlib.sha1(title.encode(), usedforsecurity=False).hexdigest()[:8]
    return f"STRIX-{digest.upper()}"


def _make_rule(report: dict[str, Any]) -> dict[str, Any]:
    """Build a SARIF rule object from a vulnerability report."""
    rule_id = _make_rule_id(report)
    severity = report.get("severity", "medium").lower()
    tags = ["security"]
    cwe = report.get("cwe")
    if cwe:
        tags.append(cwe)

    # security-severity must be a numeric string (CVSS score 0.0–10.0).
    # Use the actual CVSS score when available; fall back to a severity-derived
    # default so the value is never empty or a text label.
    cvss_value = report.get("cvss")
    if cvss_value is not None:
        security_severity = str(float(cvss_value))
    else:
        security_severity = _SEVERITY_DEFAULT_CVSS.get(severity, "5.5")

    rule: dict[str, Any] = {
        "id": rule_id,
        "name": report.get("title", rule_id),
        "shortDescription": {"text": report.get("title", rule_id)},
        "fullDescription": {"text": report.get("description") or report.get("title", rule_id)},
        "properties": {
            "tags": tags,
            "precision": "high",
            "problem.severity": _SEVERITY_LEVEL.get(severity, "warning"),
            "security-severity": security_severity,
        },
    }

    cve = report.get("cve")
    if cve:
        rule["helpUri"] = f"https://nvd.nist.gov/vuln/detail/{cve}"

    return rule


def _fingerprint(rule_id: str, uri: str, start_line: int) -> str:
    """Compute a stable partial fingerprint for deduplication."""
    raw = f"{rule_id}:{uri}:{start_line}"
    return hashlib.sha1(raw.encode(), usedforsecurity=False).hexdigest()


def _make_location(loc: dict[str, Any]) -> dict[str, Any]:
    """Convert a Strix code location to a SARIF physicalLocation."""
    region: dict[str, Any] = {"startLine": loc["start_line"]}
    if loc.get("end_line"):
        region["endLine"] = loc["end_line"]
    if loc.get("snippet"):
        region["snippet"] = {"text": loc["snippet"]}

    return {
        "physicalLocation": {
            "artifactLocation": {
                "uri": loc["file"],
                "uriBaseId": "%SRCROOT%",
            },
            "region": region,
        }
    }


def to_sarif(
    vulnerability_reports: list[dict[str, Any]],
    tool_version: str = "unknown",
) -> dict[str, Any]:
    """Convert a list of Strix vulnerability reports to a SARIF 2.1.0 document.

    Args:
        vulnerability_reports: Vulnerability reports from ``Tracer.vulnerability_reports``.
        tool_version: Version string to embed in the SARIF tool driver.

    Returns:
        A dict representing a valid SARIF 2.1.0 document.
    """
    rules: list[dict[str, Any]] = []
    rule_index_map: dict[str, int] = {}
    results: list[dict[str, Any]] = []

    for report in vulnerability_reports:
        rule_id = _make_rule_id(report)

        if rule_id not in rule_index_map:
            rule_index_map[rule_id] = len(rules)
            rules.append(_make_rule(report))

        rule_idx = rule_index_map[rule_id]
        severity = report.get("severity", "medium").lower()

        message_text = report.get("description") or report.get("title", "")
        if report.get("remediation_steps"):
            message_text = f"{message_text}\n\nRemediation: {report['remediation_steps']}"

        result: dict[str, Any] = {
            "ruleId": rule_id,
            "ruleIndex": rule_idx,
            "message": {"text": message_text},
            "level": _SEVERITY_LEVEL.get(severity, "warning"),
        }

        code_locations = report.get("code_locations") or []
        if code_locations:
            sarif_locations = [_make_location(loc) for loc in code_locations]
            result["locations"] = sarif_locations
            first_loc = code_locations[0]
            result["partialFingerprints"] = {
                "primaryLocationLineHash": _fingerprint(
                    rule_id, first_loc["file"], first_loc["start_line"]
                )
            }
        else:
            target = report.get("endpoint") or report.get("target", "")
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": target},
                    }
                }
            ]
            result["partialFingerprints"] = {
                "primaryLocationLineHash": _fingerprint(rule_id, target, 0)
            }

        # security-severity belongs on the rule, not on individual results.
        # Store the raw CVSS score and CVE for informational purposes only.
        properties: dict[str, Any] = {}
        if report.get("cvss") is not None:
            properties["cvss"] = report["cvss"]
        if report.get("cve"):
            properties["cve"] = report["cve"]
        if properties:
            result["properties"] = properties

        results.append(result)

    sarif: dict[str, Any] = {
        "$schema": _SARIF_SCHEMA,
        "version": _SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": _TOOL_NAME,
                        "version": tool_version,
                        "informationUri": _TOOL_URI,
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }

    return sarif


def encode_sarif(sarif: dict[str, Any]) -> str:
    """Gzip-compress and base64-encode a SARIF document for GitHub API upload.

    Args:
        sarif: A SARIF document as returned by :func:`to_sarif`.

    Returns:
        A base64-encoded string of the gzip-compressed SARIF JSON.
    """
    sarif_bytes = json.dumps(sarif, ensure_ascii=False).encode("utf-8")
    compressed = gzip.compress(sarif_bytes)
    return base64.b64encode(compressed).decode("ascii")


def upload_sarif_to_github(
    sarif: dict[str, Any],
    github_token: str,
    github_repo: str,
    ref: str,
    commit_sha: str,
    github_api_url: str = "https://api.github.com",
) -> dict[str, Any]:
    """Upload a SARIF document to the GitHub code-scanning API.

    Args:
        sarif: A SARIF document as returned by :func:`to_sarif`.
        github_token: A GitHub personal access token or Actions token with
            ``security_events`` write permission.
        github_repo: Repository in ``owner/repo`` format.
        ref: Git ref the SARIF results apply to (e.g. ``refs/heads/main``).
        commit_sha: The full 40-character SHA of the commit the results apply to.
        github_api_url: Override the GitHub API base URL (useful for GitHub Enterprise).

    Returns:
        A dict with ``success`` (bool), ``status_code`` (int), and either
        ``sarif_id`` (str) on success or ``error`` (str) on failure.
    """
    encoded = encode_sarif(sarif)
    url = f"{github_api_url.rstrip('/')}/repos/{github_repo}/code-scanning/sarifs"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    payload = {
        "commit_sha": commit_sha,
        "ref": ref,
        "sarif": encoded,
        "tool_name": _TOOL_NAME,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as exc:
        logger.error("SARIF upload request failed: %s", exc)
        return {"success": False, "status_code": 0, "error": str(exc)}

    if response.status_code in (200, 202):
        body = response.json() if response.content else {}
        sarif_id = body.get("id", "")
        logger.info("SARIF uploaded successfully (id=%s)", sarif_id)
        return {"success": True, "status_code": response.status_code, "sarif_id": sarif_id}

    logger.error(
        "SARIF upload failed: HTTP %d – %s", response.status_code, response.text[:500]
    )
    return {
        "success": False,
        "status_code": response.status_code,
        "error": response.text[:500],
    }

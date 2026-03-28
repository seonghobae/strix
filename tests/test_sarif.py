"""Tests for strix/sarif.py and the Tracer.to_sarif() integration."""

import base64
import gzip
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from strix.sarif import encode_sarif, to_sarif, upload_sarif_to_github


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(
    *,
    report_id: str = "vuln-0001",
    title: str = "SQL Injection",
    severity: str = "high",
    description: str = "User input is concatenated directly into a SQL query.",
    remediation_steps: str = "Use parameterised queries.",
    cvss: float = 8.1,
    cve: str | None = None,
    cwe: str | None = "CWE-89",
    code_locations: list[dict[str, Any]] | None = None,
    endpoint: str | None = None,
    target: str = "https://example.com",
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "id": report_id,
        "title": title,
        "severity": severity,
        "description": description,
        "remediation_steps": remediation_steps,
        "cvss": cvss,
        "target": target,
        "timestamp": "2024-01-01 00:00:00 UTC",
    }
    if cve:
        report["cve"] = cve
    if cwe:
        report["cwe"] = cwe
    if code_locations:
        report["code_locations"] = code_locations
    if endpoint:
        report["endpoint"] = endpoint
    return report


# ---------------------------------------------------------------------------
# to_sarif() – document structure
# ---------------------------------------------------------------------------


def test_to_sarif_returns_valid_schema_and_version() -> None:
    sarif = to_sarif([], tool_version="0.8.3")
    assert sarif["version"] == "2.1.0"
    assert "sarif-schema-2.1.0.json" in sarif["$schema"]
    assert len(sarif["runs"]) == 1


def test_to_sarif_tool_driver() -> None:
    sarif = to_sarif([], tool_version="1.2.3")
    driver = sarif["runs"][0]["tool"]["driver"]
    assert driver["name"] == "Strix"
    assert driver["version"] == "1.2.3"
    assert "strix" in driver["informationUri"].lower()


def test_to_sarif_empty_reports() -> None:
    sarif = to_sarif([])
    run = sarif["runs"][0]
    assert run["results"] == []
    assert run["tool"]["driver"]["rules"] == []


def test_to_sarif_single_report_produces_one_result_and_one_rule() -> None:
    report = _make_report()
    sarif = to_sarif([report])
    run = sarif["runs"][0]
    assert len(run["results"]) == 1
    assert len(run["tool"]["driver"]["rules"]) == 1


def test_to_sarif_rule_uses_cwe_as_id() -> None:
    report = _make_report(cwe="CWE-89")
    sarif = to_sarif([report])
    rule = sarif["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["id"] == "CWE-89"


def test_to_sarif_rule_id_falls_back_to_hash_when_no_cwe() -> None:
    report = _make_report(cwe=None)
    sarif = to_sarif([report])
    rule = sarif["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["id"].startswith("STRIX-")


def test_to_sarif_deduplicates_rules_for_same_cwe() -> None:
    r1 = _make_report(report_id="vuln-0001", cwe="CWE-89", title="SQL Injection #1")
    r2 = _make_report(report_id="vuln-0002", cwe="CWE-89", title="SQL Injection #2")
    sarif = to_sarif([r1, r2])
    run = sarif["runs"][0]
    assert len(run["tool"]["driver"]["rules"]) == 1
    assert len(run["results"]) == 2
    assert run["results"][0]["ruleIndex"] == 0
    assert run["results"][1]["ruleIndex"] == 0


# ---------------------------------------------------------------------------
# security-severity must be a numeric string on the rule (GitHub requirement)
# ---------------------------------------------------------------------------


def test_to_sarif_rule_security_severity_uses_cvss_when_available() -> None:
    report = _make_report(cvss=8.1, severity="high")
    sarif = to_sarif([report])
    rule = sarif["runs"][0]["tool"]["driver"]["rules"][0]
    ss = rule["properties"]["security-severity"]
    # Must be parseable as a float in [0, 10]
    assert 0.0 <= float(ss) <= 10.0
    assert float(ss) == 8.1


@pytest.mark.parametrize(
    ("severity", "expected_min", "expected_max"),
    [
        ("critical", 9.0, 10.0),
        ("high", 7.0, 8.9),
        ("medium", 4.0, 6.9),
        ("low", 0.1, 3.9),
        ("info", 0.0, 0.9),
    ],
)
def test_to_sarif_rule_security_severity_fallback_is_numeric_and_in_range(
    severity: str, expected_min: float, expected_max: float
) -> None:
    # Build a report with NO cvss score so the fallback kicks in
    report = _make_report(severity=severity)
    del report["cvss"]
    sarif = to_sarif([report])
    rule = sarif["runs"][0]["tool"]["driver"]["rules"][0]
    ss = rule["properties"]["security-severity"]
    value = float(ss)
    assert expected_min <= value <= expected_max, (
        f"security-severity {ss!r} out of expected range [{expected_min}, {expected_max}] "
        f"for severity={severity!r}"
    )


def test_to_sarif_result_does_not_have_invalid_security_severity_label() -> None:
    """Result properties must not contain a text label like 'high' for security-severity."""
    report = _make_report(severity="critical")
    sarif = to_sarif([report])
    result = sarif["runs"][0]["results"][0]
    props = result.get("properties", {})
    # If security-severity appears on a result at all, it must be numeric
    if "security-severity" in props:
        float(props["security-severity"])  # raises ValueError if it's a label like "critical"


# ---------------------------------------------------------------------------
# Severity level mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("severity", "expected_level"),
    [
        ("critical", "error"),
        ("high", "error"),
        ("medium", "warning"),
        ("low", "note"),
        ("info", "note"),
    ],
)
def test_to_sarif_severity_to_level_mapping(severity: str, expected_level: str) -> None:
    report = _make_report(severity=severity)
    sarif = to_sarif([report])
    result = sarif["runs"][0]["results"][0]
    assert result["level"] == expected_level


# ---------------------------------------------------------------------------
# Code locations
# ---------------------------------------------------------------------------


def test_to_sarif_result_with_code_locations() -> None:
    locs = [{"file": "src/app.py", "start_line": 10, "end_line": 12, "snippet": "x = y"}]
    report = _make_report(code_locations=locs)
    sarif = to_sarif([report])
    result = sarif["runs"][0]["results"][0]
    assert len(result["locations"]) == 1
    phys = result["locations"][0]["physicalLocation"]
    assert phys["artifactLocation"]["uri"] == "src/app.py"
    assert phys["artifactLocation"]["uriBaseId"] == "%SRCROOT%"
    assert phys["region"]["startLine"] == 10
    assert phys["region"]["endLine"] == 12
    assert phys["region"]["snippet"]["text"] == "x = y"


def test_to_sarif_result_without_code_locations_falls_back_to_target() -> None:
    report = _make_report(code_locations=None, target="https://example.com")
    sarif = to_sarif([report])
    result = sarif["runs"][0]["results"][0]
    assert len(result["locations"]) == 1
    uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == "https://example.com"


def test_to_sarif_result_without_code_locations_prefers_endpoint() -> None:
    report = _make_report(code_locations=None, endpoint="/api/login", target="https://example.com")
    sarif = to_sarif([report])
    result = sarif["runs"][0]["results"][0]
    uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == "/api/login"


# ---------------------------------------------------------------------------
# Partial fingerprint
# ---------------------------------------------------------------------------


def test_to_sarif_partial_fingerprint_is_deterministic() -> None:
    locs = [{"file": "app.py", "start_line": 5, "end_line": 5}]
    report = _make_report(code_locations=locs)
    sarif1 = to_sarif([report])
    sarif2 = to_sarif([report])
    fp1 = sarif1["runs"][0]["results"][0]["partialFingerprints"]["primaryLocationLineHash"]
    fp2 = sarif2["runs"][0]["results"][0]["partialFingerprints"]["primaryLocationLineHash"]
    assert fp1 == fp2


def test_to_sarif_different_locations_give_different_fingerprints() -> None:
    locs_a = [{"file": "app.py", "start_line": 5, "end_line": 5}]
    locs_b = [{"file": "app.py", "start_line": 99, "end_line": 99}]
    sarif_a = to_sarif([_make_report(code_locations=locs_a)])
    sarif_b = to_sarif([_make_report(code_locations=locs_b)])
    fp_a = sarif_a["runs"][0]["results"][0]["partialFingerprints"]["primaryLocationLineHash"]
    fp_b = sarif_b["runs"][0]["results"][0]["partialFingerprints"]["primaryLocationLineHash"]
    assert fp_a != fp_b


# ---------------------------------------------------------------------------
# encode_sarif()
# ---------------------------------------------------------------------------


def test_encode_sarif_produces_valid_base64_gzip_json() -> None:
    sarif = to_sarif([_make_report()])
    encoded = encode_sarif(sarif)
    decoded_bytes = base64.b64decode(encoded)
    decompressed = gzip.decompress(decoded_bytes)
    recovered = json.loads(decompressed)
    assert recovered["version"] == "2.1.0"


# ---------------------------------------------------------------------------
# upload_sarif_to_github()
# ---------------------------------------------------------------------------


def test_upload_sarif_success() -> None:
    sarif = to_sarif([_make_report()])
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.content = b'{"id": "abc123"}'
    mock_response.json.return_value = {"id": "abc123"}

    with patch("strix.sarif.requests.post", return_value=mock_response) as mock_post:
        result = upload_sarif_to_github(
            sarif=sarif,
            github_token="ghp_token",
            github_repo="owner/repo",
            ref="refs/heads/main",
            commit_sha="a" * 40,
        )

    assert result["success"] is True
    assert result["status_code"] == 202
    assert result["sarif_id"] == "abc123"

    call_kwargs = mock_post.call_args
    payload = call_kwargs.kwargs["json"]
    assert payload["commit_sha"] == "a" * 40
    assert payload["ref"] == "refs/heads/main"
    assert "sarif" in payload


def test_upload_sarif_http_error() -> None:
    sarif = to_sarif([])
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.content = b"Forbidden"
    mock_response.text = "Forbidden"

    with patch("strix.sarif.requests.post", return_value=mock_response):
        result = upload_sarif_to_github(
            sarif=sarif,
            github_token="bad_token",
            github_repo="owner/repo",
            ref="refs/heads/main",
            commit_sha="b" * 40,
        )

    assert result["success"] is False
    assert result["status_code"] == 403
    assert "Forbidden" in result["error"]


def test_upload_sarif_network_error() -> None:
    import requests as req_lib

    sarif = to_sarif([])
    with patch("strix.sarif.requests.post", side_effect=req_lib.ConnectionError("unreachable")):
        result = upload_sarif_to_github(
            sarif=sarif,
            github_token="ghp_token",
            github_repo="owner/repo",
            ref="refs/heads/main",
            commit_sha="c" * 40,
        )

    assert result["success"] is False
    assert result["status_code"] == 0
    assert "unreachable" in result["error"]


def test_upload_sarif_uses_custom_api_url() -> None:
    sarif = to_sarif([])
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.content = b"{}"
    mock_response.json.return_value = {}

    with patch("strix.sarif.requests.post", return_value=mock_response) as mock_post:
        upload_sarif_to_github(
            sarif=sarif,
            github_token="token",
            github_repo="org/repo",
            ref="refs/heads/main",
            commit_sha="d" * 40,
            github_api_url="https://github.example.com/api/v3",
        )

    url_used = mock_post.call_args.args[0]
    assert url_used.startswith("https://github.example.com/api/v3")


# ---------------------------------------------------------------------------
# Tracer.to_sarif() integration
# ---------------------------------------------------------------------------


def test_tracer_to_sarif_returns_sarif_document(tmp_path, monkeypatch) -> None:
    import strix.telemetry.tracer as tracer_module
    from strix.telemetry import utils as telemetry_utils
    from strix.telemetry.tracer import Tracer, set_global_tracer

    monkeypatch.setattr(tracer_module, "_global_tracer", None)
    monkeypatch.setattr(tracer_module, "_OTEL_BOOTSTRAPPED", False)
    monkeypatch.setattr(tracer_module, "_OTEL_REMOTE_ENABLED", False)
    telemetry_utils.reset_events_write_locks()
    monkeypatch.chdir(tmp_path)

    tracer = Tracer("sarif-integration-test")
    set_global_tracer(tracer)

    tracer.add_vulnerability_report(
        title="XSS in search",
        severity="medium",
        description="Reflected XSS via the q parameter.",
        cwe="CWE-79",
    )

    sarif = tracer.to_sarif(tool_version="0.8.3")

    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["version"] == "0.8.3"
    assert len(run["results"]) == 1
    assert run["results"][0]["ruleId"] == "CWE-79"

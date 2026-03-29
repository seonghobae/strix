from unittest.mock import MagicMock, patch

from strix.tools.reporting.reporting_actions import (
    _extract_cve,
    _extract_cwe,
    _validate_code_locations,
    _validate_cve,
    _validate_cvss_parameters,
    _validate_cwe,
    _validate_file_path,
    _validate_required_fields,
    calculate_cvss_and_severity,
    create_vulnerability_report,
    parse_code_locations_xml,
    parse_cvss_xml,
)


def test_parse_cvss_xml_empty():
    assert parse_cvss_xml("") is None
    assert parse_cvss_xml("   ") is None


def test_parse_cvss_xml_valid():
    xml = """
    <attack_vector>N</attack_vector>
    <attack_complexity>L</attack_complexity>
    <privileges_required>N</privileges_required>
    <user_interaction>N</user_interaction>
    <scope>U</scope>
    <confidentiality>H</confidentiality>
    <integrity>H</integrity>
    <availability>H</availability>
    """
    expected = {
        "attack_vector": "N",
        "attack_complexity": "L",
        "privileges_required": "N",
        "user_interaction": "N",
        "scope": "U",
        "confidentiality": "H",
        "integrity": "H",
        "availability": "H",
    }
    assert parse_cvss_xml(xml) == expected


def test_parse_code_locations_xml_empty():
    assert parse_code_locations_xml("") is None
    assert parse_code_locations_xml("   ") is None


def test_parse_code_locations_xml_valid():
    xml = """
    <location>
        <file>src/main.py</file>
        <start_line>10</start_line>
        <end_line>20</end_line>
        <snippet>print("hello")\n</snippet>
        <label>vuln</label>
        <fix_before>old</fix_before>
        <fix_after>new</fix_after>
    </location>
    """
    res = parse_code_locations_xml(xml)
    assert res is not None
    assert len(res) == 1
    loc = res[0]
    assert loc["file"] == "src/main.py"
    assert loc["start_line"] == 10
    assert loc["end_line"] == 20
    assert loc["snippet"] == 'print("hello")'
    assert loc["label"] == "vuln"
    assert loc["fix_before"] == "old"
    assert loc["fix_after"] == "new"


def test_parse_code_locations_invalid_lines():
    xml = """
    <location>
        <file>src/main.py</file>
        <start_line>abc</start_line>
        <end_line>def</end_line>
    </location>
    """
    # Should ignore invalid integers and not include start_line/end_line
    # If file is present but start_line is not, it should be excluded
    res = parse_code_locations_xml(xml)
    assert res is None


def test_validate_file_path():
    assert _validate_file_path("") == "file path cannot be empty"
    assert _validate_file_path("   ") == "file path cannot be empty"
    assert (
        _validate_file_path("/absolute/path")
        == "file path must be relative, got absolute: '/absolute/path'"
    )
    assert (
        _validate_file_path("relative/../path")
        == "file path must not contain '..': 'relative/../path'"
    )
    assert _validate_file_path("valid/relative/path.py") is None


def test_validate_code_locations():
    # Valid
    valid = [{"file": "src/main.py", "start_line": 10, "end_line": 20}]
    assert _validate_code_locations(valid) == []

    # Invalid file path
    invalid_file = [{"file": "", "start_line": 10, "end_line": 20}]
    errs = _validate_code_locations(invalid_file)
    assert "code_locations[0]: file path cannot be empty" in errs

    # Invalid start_line
    invalid_start = [{"file": "src.py", "start_line": -1, "end_line": 20}]
    errs = _validate_code_locations(invalid_start)
    assert "code_locations[0]: start_line must be a positive integer" in errs

    # Missing end_line
    missing_end = [{"file": "src.py", "start_line": 10}]
    errs = _validate_code_locations(missing_end)
    assert "code_locations[0]: end_line is required" in errs

    # Invalid end_line type
    invalid_end_type = [{"file": "src.py", "start_line": 10, "end_line": -5}]
    errs = _validate_code_locations(invalid_end_type)
    assert "code_locations[0]: end_line must be a positive integer" in errs

    # end_line < start_line
    end_less_than_start = [{"file": "src.py", "start_line": 20, "end_line": 10}]
    errs = _validate_code_locations(end_less_than_start)
    assert "code_locations[0]: end_line (10) must be >= start_line (20)" in errs


def test_extract_cve():
    assert _extract_cve("Some text CVE-2023-12345 more text") == "CVE-2023-12345"
    assert _extract_cve("No CVE here") == "No CVE here"


def test_validate_cve():
    assert _validate_cve("CVE-2023-12345") is None
    assert "invalid CVE format" in _validate_cve("CVE-23-123")


def test_extract_cwe():
    assert _extract_cwe("Some text CWE-79 more text") == "CWE-79"
    assert _extract_cwe("No CWE") == "No CWE"


def test_validate_cwe():
    assert _validate_cwe("CWE-79") is None
    assert "invalid CWE format" in _validate_cwe("CWE-abc")


def test_calculate_cvss_and_severity():
    # Valid calculation
    score, severity, vector = calculate_cvss_and_severity("N", "L", "N", "N", "U", "H", "H", "H")
    assert score == 9.8
    assert severity == "critical"
    assert "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" in vector

    # Invalid calculation (will fallback to 7.5, high)
    score, severity, vector = calculate_cvss_and_severity("X", "X", "X", "X", "X", "X", "X", "X")
    assert score == 7.5
    assert severity == "high"
    assert vector == ""


def test_validate_required_fields():
    # Missing required field
    errs = _validate_required_fields(title="", description="desc")
    assert "Title cannot be empty" in errs

    # All fields present
    errs = _validate_required_fields(
        title="t",
        description="d",
        impact="i",
        target="t",
        technical_analysis="ta",
        poc_description="pd",
        poc_script_code="ps",
        remediation_steps="rs",
    )
    assert len(errs) == 0


def test_validate_cvss_parameters():
    errs = _validate_cvss_parameters(
        attack_vector="X",
        attack_complexity="L",
        privileges_required="N",
        user_interaction="N",
        scope="U",
        confidentiality="H",
        integrity="H",
        availability="H",
    )
    assert "Invalid attack_vector: X." in errs[0]

    errs = _validate_cvss_parameters(
        attack_vector="N",
        attack_complexity="L",
        privileges_required="N",
        user_interaction="N",
        scope="U",
        confidentiality="H",
        integrity="H",
        availability="H",
    )
    assert len(errs) == 0


@patch("strix.telemetry.tracer.get_global_tracer")
def test_create_vulnerability_report_success(mock_get_tracer):
    mock_tracer = MagicMock()
    mock_get_tracer.return_value = mock_tracer
    mock_tracer.get_existing_vulnerabilities.return_value = []
    mock_tracer.add_vulnerability_report.return_value = "report_id_1"

    cvss_xml = (
        "<attack_vector>N</attack_vector><attack_complexity>L</attack_complexity>"
        "<privileges_required>N</privileges_required><user_interaction>N</user_interaction>"
        "<scope>U</scope><confidentiality>H</confidentiality><integrity>H</integrity>"
        "<availability>H</availability>"
    )

    res = create_vulnerability_report(
        title="SQLi",
        description="desc",
        impact="imp",
        target="tgt",
        technical_analysis="tech",
        poc_description="poc_desc",
        poc_script_code="poc_code",
        remediation_steps="rem",
        cvss_breakdown=cvss_xml,
    )

    assert res["success"] is True
    assert res["report_id"] == "report_id_1"


@patch("strix.telemetry.tracer.get_global_tracer")
def test_create_vulnerability_report_duplicate(mock_get_tracer):
    mock_tracer = MagicMock()
    mock_get_tracer.return_value = mock_tracer

    # Mock dedupe to say it's a duplicate
    mock_tracer.get_existing_vulnerabilities.return_value = [
        {"id": "dup_id_1", "title": "Old SQLi"}
    ]

    with patch("strix.llm.dedupe.check_duplicate") as mock_check_duplicate:
        mock_check_duplicate.return_value = {
            "is_duplicate": True,
            "duplicate_id": "dup_id_1",
            "confidence": 0.99,
            "reason": "matches",
        }

        cvss_xml = (
            "<attack_vector>N</attack_vector><attack_complexity>L</attack_complexity>"
            "<privileges_required>N</privileges_required><user_interaction>N</user_interaction>"
            "<scope>U</scope><confidentiality>H</confidentiality><integrity>H</integrity>"
            "<availability>H</availability>"
        )

        res = create_vulnerability_report(
            title="SQLi",
            description="desc",
            impact="imp",
            target="tgt",
            technical_analysis="tech",
            poc_description="poc_desc",
            poc_script_code="poc_code",
            remediation_steps="rem",
            cvss_breakdown=cvss_xml,
        )

        assert res["success"] is False
        assert "Potential duplicate" in res["message"]
        assert res["duplicate_of"] == "dup_id_1"


def test_create_vulnerability_report_validation_failures():
    res = create_vulnerability_report(
        title="",  # missing
        description="desc",
        impact="imp",
        target="tgt",
        technical_analysis="tech",
        poc_description="poc",
        poc_script_code="poc",
        remediation_steps="rem",
        cvss_breakdown="invalid xml",
    )
    assert res["success"] is False
    assert "Title cannot be empty" in res["errors"]
    assert "cvss: could not parse CVSS breakdown XML" in res["errors"]


@patch("strix.telemetry.tracer.get_global_tracer")
def test_create_vulnerability_report_no_tracer(mock_get_tracer):
    mock_get_tracer.return_value = None

    cvss_xml = (
        "<attack_vector>N</attack_vector><attack_complexity>L</attack_complexity>"
        "<privileges_required>N</privileges_required><user_interaction>N</user_interaction>"
        "<scope>U</scope><confidentiality>H</confidentiality><integrity>H</integrity>"
        "<availability>H</availability>"
    )

    res = create_vulnerability_report(
        title="SQLi",
        description="desc",
        impact="imp",
        target="tgt",
        technical_analysis="tech",
        poc_description="poc_desc",
        poc_script_code="poc_code",
        remediation_steps="rem",
        cvss_breakdown=cvss_xml,
    )

    assert res["success"] is True
    assert res["warning"] == "Report could not be persisted - tracer unavailable"


def test_create_vulnerability_report_tracer_import_error():
    # In order to simulate ImportError when doing `from ... import get_global_tracer`,
    # we can use patch.dict on sys.modules to remove it, or mock __import__.
    # Since the module imports are dynamically done, patching `sys.modules` works.
    import sys

    cvss_xml = (
        "<attack_vector>N</attack_vector><attack_complexity>L</attack_complexity>"
        "<privileges_required>N</privileges_required><user_interaction>N</user_interaction>"
        "<scope>U</scope><confidentiality>H</confidentiality><integrity>H</integrity>"
        "<availability>H</availability>"
    )

    # Let's mock check_duplicate or get_global_tracer to throw ImportError instead.
    # Oh wait, `from strix.telemetry.tracer import get_global_tracer` is inside the func.
    # Patching sys.modules is safer.
    with (
        patch(
            "strix.tools.reporting.reporting_actions.get_global_tracer",
            side_effect=ImportError("Mocked error"),
            create=True,
        ),
        patch.dict(sys.modules, {"strix.telemetry.tracer": None}),
    ):
        res = create_vulnerability_report(
            title="SQLi",
            description="desc",
            impact="imp",
            target="tgt",
            technical_analysis="tech",
            poc_description="poc_desc",
            poc_script_code="poc_code",
            remediation_steps="rem",
            cvss_breakdown=cvss_xml,
        )

    assert res["success"] is False
    assert "Failed to create vulnerability report" in res["message"]


@patch("strix.telemetry.tracer.get_global_tracer")
def test_create_vulnerability_report_cve_cwe_validation(mock_get_tracer):
    mock_get_tracer.return_value = None
    cvss_xml = (
        "<attack_vector>N</attack_vector><attack_complexity>L</attack_complexity>"
        "<privileges_required>N</privileges_required><user_interaction>N</user_interaction>"
        "<scope>U</scope><confidentiality>H</confidentiality><integrity>H</integrity>"
        "<availability>H</availability>"
    )

    res = create_vulnerability_report(
        title="SQLi",
        description="desc",
        impact="imp",
        target="tgt",
        technical_analysis="tech",
        poc_description="poc_desc",
        poc_script_code="poc_code",
        remediation_steps="rem",
        cvss_breakdown=cvss_xml,
        cve="CVE-23-1",
        cwe="CWE-abc",
        code_locations="""
        <location>
            <file>../src/main.py</file>
            <start_line>10</start_line>
            <end_line>20</end_line>
        </location>
        """,
    )
    assert res["success"] is False
    assert any("invalid CVE format" in e for e in res["errors"])
    assert any("invalid CWE format" in e for e in res["errors"])
    assert any("file path must not contain '..'" in e for e in res["errors"])

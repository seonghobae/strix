from strix.telemetry.tracer import Tracer, set_global_tracer


def test_vulnerability_reporting(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    tracer = Tracer("vuln-test")
    set_global_tracer(tracer)

    report_id = tracer.add_vulnerability_report(
        title="SQL Injection",
        severity="high",
        description="Found SQLi in login form",
        impact="Can drop tables",
        target="login",
        technical_analysis="Payload ' OR 1=1 --",
        poc_description="Run curl",
        poc_script_code="curl -X POST ...",
        remediation_steps="Use prepared statements",
        cvss=8.5,
        cvss_breakdown={"attackVector": "NETWORK"},
        endpoint="/login",
        method="POST",
        cve="CVE-2024-1234",
        cwe="CWE-89",
        code_locations=[{"file": "login.py", "start_line": 42}],
    )

    assert report_id == "vuln-0001"

    vulns = tracer.get_existing_vulnerabilities()
    assert len(vulns) == 1
    assert vulns[0]["title"] == "SQL Injection"

    # Test to_sarif
    sarif_doc = tracer.to_sarif(tool_version="1.0.0")
    assert "runs" in sarif_doc


def test_update_scan_final_fields(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tracer = Tracer("scan-fields-test")
    set_global_tracer(tracer)

    tracer.update_scan_final_fields(
        executive_summary="Executive",
        methodology="Method",
        technical_analysis="Tech",
        recommendations="Recs",
    )

    assert tracer.scan_results and tracer.scan_results.get("scan_completed") is True
    assert tracer.final_scan_result and "Executive" in tracer.final_scan_result
    assert tracer.final_scan_result and "Method" in tracer.final_scan_result


def test_tool_execution_updates(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tracer = Tracer("tool-exec-test")
    set_global_tracer(tracer)

    exec_id = tracer.log_tool_execution_start(
        agent_id="agent-1", tool_name="test_tool", args={"param": "value"}
    )

    tracer.update_tool_execution(exec_id, status="completed", result={"ok": True})

    tools = tracer.get_agent_tools("agent-1")
    assert len(tools) == 1
    assert tools[0]["status"] == "completed"
    assert tools[0]["result"] == {"ok": True}

    count = tracer.get_real_tool_count()
    assert count == 1

    # Update execution for vulnerability report specifically
    vuln_exec_id = tracer.log_tool_execution_start(
        agent_id="agent-1", tool_name="create_vulnerability_report", args={"foo": "bar"}
    )
    tracer.update_tool_execution(vuln_exec_id, status="error", result="failed")

    # Update invalid id
    tracer.update_tool_execution(9999, status="completed")


def test_agent_status_updates(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tracer = Tracer("agent-status-test")
    set_global_tracer(tracer)

    tracer.log_agent_creation("agent-1", "Agent 1", "test")
    tracer.update_agent_status("agent-1", "running")
    assert tracer.agents["agent-1"]["status"] == "running"

    tracer.update_agent_status("agent-1", "error", error_message="boom")
    assert tracer.agents["agent-1"]["error_message"] == "boom"


def test_streaming_content(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tracer = Tracer("streaming-test")
    set_global_tracer(tracer)

    tracer.update_streaming_content("agent-1", "streaming content chunk")
    assert tracer.get_streaming_content("agent-1") == "streaming content chunk"

    tracer.clear_streaming_content("agent-1")
    assert tracer.get_streaming_content("agent-1") is None

    tracer.update_streaming_content("agent-1", "more streaming content")
    finalized = tracer.finalize_streaming_as_interrupted("agent-1")
    assert finalized == "more streaming content"
    assert tracer.get_streaming_content("agent-1") is None

    # finalize again retrieves from interrupted content
    finalized2 = tracer.finalize_streaming_as_interrupted("agent-1")
    assert finalized2 == "more streaming content"

    # finalize empty
    assert tracer.finalize_streaming_as_interrupted("agent-1") is None


def test_save_run_data_exceptions_and_cleanup(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tracer = Tracer("cleanup-test")
    set_global_tracer(tracer)

    # test cleanup marks complete
    tracer.cleanup()
    assert tracer._run_completed_emitted is True


def test_active_run_metadata_and_events_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    tracer1 = Tracer("test-1")
    set_global_tracer(None)  # type: ignore
    assert tracer1._active_events_file_path() == tracer1.events_file_path
    assert tracer1._active_run_metadata() == tracer1.run_metadata

    set_global_tracer(tracer1)
    assert tracer1._active_events_file_path() == tracer1.events_file_path
    assert tracer1._active_run_metadata() == tracer1.run_metadata


def test_calculate_duration_invalid(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tracer = Tracer("duration-test")
    tracer.start_time = "invalid-date"
    tracer.end_time = "invalid-date"
    assert tracer._calculate_duration() == 0.0


def test_get_total_llm_stats(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tracer = Tracer("llm-stats-test")

    from strix.tools.agents_graph.agents_graph_actions import _agent_instances

    class FakeLLMStats:
        input_tokens = 10
        output_tokens = 20
        cached_tokens = 5
        cost = 0.001
        requests = 2

    class FakeLLM:
        _total_stats = FakeLLMStats()

    class FakeAgent:
        llm = FakeLLM()

    _agent_instances["fake"] = FakeAgent()
    stats = tracer.get_total_llm_stats()
    assert stats["total_tokens"] == 30
    assert stats["total"]["cost"] == 0.001

    _agent_instances.clear()

def test_set_association_properties_exceptions(monkeypatch):
    from strix.telemetry import tracer as tracer_module
    tracer = Tracer("assoc-prop-test")

    # Test Traceloop is None
    monkeypatch.setattr(tracer_module, "Traceloop", None)
    # Should return early without error
    tracer._set_association_properties({"foo": "bar"})

    # Test Traceloop raises Exception
    class FakeTraceloop:
        @staticmethod
        def set_association_properties(_props):
            raise RuntimeError("Mocked exception")

    monkeypatch.setattr(tracer_module, "Traceloop", FakeTraceloop)
    # Should catch exception and log debug without crashing
    tracer._set_association_properties({"foo": "bar"})

def test_append_event_record_oserror(monkeypatch):
    from strix.telemetry import tracer as tracer_module
    tracer = Tracer("append-record-test")

    def fake_append(*args, **kwargs):
        raise OSError("Mocked OSError")

    monkeypatch.setattr(tracer_module, "append_jsonl_record", fake_append)
    # Should catch exception
    tracer._append_event_record({"foo": "bar"})

def test_enrich_actor_non_string_agent_id():
    tracer = Tracer("enrich-actor-test")

    # Non-string agent_id
    actor = {"agent_id": 123}
    enriched = tracer._enrich_actor(actor)
    assert enriched and enriched.get("agent_id") == 123
    assert enriched is not None and "agent_name" not in enriched

def test_log_event_current_span_and_otel_exception(monkeypatch):
    from opentelemetry.trace import SpanContext, TraceFlags

    from strix.telemetry import tracer as tracer_module
    tracer = Tracer("log-event-test")
    # Enable telemetry to bypass early return
    tracer._telemetry_enabled = True

    # Test trace.get_current_span().get_span_context() returning valid context
    real_context = SpanContext(
        trace_id=12345678901234567890123456789012,
        span_id=1234567890,
        is_remote=False,
        trace_flags=TraceFlags(1)
    )

    class FakeSpan:
        def get_span_context(self):
            return real_context

    class FakeTrace:
        @staticmethod
        def get_current_span():
            return FakeSpan()

    monkeypatch.setattr(tracer_module, "trace", FakeTrace)

    # We also mock _otel_tracer.start_as_current_span to raise Exception
    class FakeOtelTracer:
        def start_as_current_span(self, *_args, **_kwargs):
            raise RuntimeError("Mocked OTEL exception")

    tracer._otel_tracer = FakeOtelTracer()

    # Calling log_event should hit parent_span_id assignment and the OTEL Exception catch
    tracer._emit_event("test_event", actor={"agent_id": "test"})

def test_log_event_fallback_uuid(monkeypatch):

    from strix.telemetry import tracer as tracer_module

    tracer = Tracer("fallback-uuid-test")
    tracer._telemetry_enabled = True

    class FakeUUID:
        int = 0
        hex = "fallback_hex"

    # Patch uuid4 so it returns a fake UUID with int = 0
    monkeypatch.setattr(tracer_module, "uuid4", lambda: FakeUUID())

    tracer._emit_event("fallback_test")
    # Should not crash and use fallback_hex for trace_id and span_id

def test_vulnerability_found_callback():
    tracer = Tracer("vuln-callback-test")
    called = []

    def fake_callback(report):
        called.append(report)

    tracer.vulnerability_found_callback = (fake_callback)
    tracer.add_vulnerability_report(
        title="Callback Test",
        severity="low",
        description="test",
        code_locations=[]
    )

    assert len(called) == 1
    assert called[0]["title"] == "Callback Test"

def test_export_markdown_vulnerabilities_full_code_locations(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tracer = Tracer("markdown-vuln-test")

    tracer.add_vulnerability_report(
        title="Full Code Locations Test",
        severity="high",
        description="test",
        code_locations=[
            {
                "file": "test.py",
                "start_line": 10,
                "end_line": 15,
                "label": "Test Label",
                "snippet": "test_snippet()",
                "fix_before": "old_code()",
                "fix_after": "new_code()"
            }
        ]
    )

    # Run save_run_data which triggers _export_markdown_vulnerabilities
    tracer.save_run_data()

def test_finalize_run_exception(monkeypatch):
    tracer = Tracer("finalize-run-test")

    def fake_get_run_dir(*args, **kwargs):
        raise OSError("Mocked OSError during save_run_data")

    monkeypatch.setattr(tracer, "get_run_dir", fake_get_run_dir)
    # Should catch exception and not crash
    tracer.save_run_data(mark_complete=True)

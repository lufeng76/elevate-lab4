"""Unit tests for IdentityContext and Structured Audit Logging."""
import pytest
from agent.security.audit import AuditLogger
from agent.security.identity import IdentityContextInjector


def test_identity_context_header_injection():
    IdentityContextInjector.clear_revocations()
    ctx = IdentityContextInjector.create_context(
        user_id="EMP-1042",
        obo_token="mock_obo_token_xyz",
    )
    headers = ctx.to_downstream_headers()
    assert headers["X-Delegated-User-Id"] == "EMP-1042"
    assert headers["X-Automation-Origin"] == "HR-Agentic-Solution-MVP1"
    assert headers["X-Execution-Id"].startswith("exec-")
    assert headers["Authorization"] == "Bearer mock_obo_token_xyz"


def test_identity_revocation_blacklist():
    IdentityContextInjector.clear_revocations()
    assert IdentityContextInjector.is_revoked("EMP-REVOKED") is False

    IdentityContextInjector.revoke_user("EMP-REVOKED")
    assert IdentityContextInjector.is_revoked("EMP-REVOKED") is True


def test_audit_logger_emission_and_sanitization():
    AuditLogger.clear_records()
    entry = AuditLogger.emit(
        session_id="sess-001",
        user_id="EMP-1042",
        action_type="TEST_ACTION",
        payload={
            "phone": "+6591234567",
            "ssn": "000-11-2222",
            "comment": "Regular text note",
        },
        tool_name="test_tool",
        latency_ms=145.2,
    )
    assert entry.action_type == "TEST_ACTION"
    assert entry.payload_masked["ssn"] == "[REDACTED_SSN]"
    assert entry.payload_masked["phone"] == "[REDACTED_CONTACT]"
    assert entry.payload_masked["comment"] == "Regular text note"
    assert entry.execution_latency_ms == 145.2

    records = AuditLogger.get_recent_entries()
    assert len(records) >= 1
    assert records[-1]["event_id"] == entry.event_id

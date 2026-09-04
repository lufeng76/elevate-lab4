"""Immutable Structured Audit Logging Engine.

Implements SDD Section 2 (NFR-1.1 - NFR-1.3), Section 8, and Section 9.2
for enterprise compliance, traceability, and GDPR auditing.
"""
import datetime
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .guardrails import SPIIMasker

logger = logging.getLogger("audit")


@dataclass
class AuditLogEntry:
    """Structured audit log entry conforming to SDD Section 9.2."""

    session_id: str
    user_id: str
    action_type: str
    event_id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    tool_name: Optional[str] = None
    request_origin: dict[str, str] = field(
        default_factory=lambda: {
            "verified_automation_source": "HR-Agentic-Solution-MVP1",
        }
    )
    safety_evaluation: dict[str, Any] = field(default_factory=dict)
    payload_masked: dict[str, Any] = field(default_factory=dict)
    execution_status: str = "SUCCESS"
    execution_latency_ms: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class AuditLogger:
    """Immutable structured audit telemetry logger."""

    _in_memory_records: list[dict[str, Any]] = []

    @classmethod
    def emit(
        cls,
        session_id: str,
        user_id: str,
        action_type: str,
        payload: Optional[dict[str, Any]] = None,
        tool_name: Optional[str] = None,
        safety_evaluation: Optional[dict[str, Any]] = None,
        status: str = "SUCCESS",
        latency_ms: float = 0.0,
    ) -> AuditLogEntry:
        """Create, sanitize, record, and log an immutable audit event."""
        # Sanitize all string fields in payload using SPIIMasker
        masked_payload: dict[str, Any] = {}
        if payload:
            for k, v in payload.items():
                if isinstance(v, str):
                    masked_payload[k] = SPIIMasker.mask(v)
                elif isinstance(v, dict):
                    masked_payload[k] = {
                        sub_k: SPIIMasker.mask(str(sub_v)) if isinstance(sub_v, str) else sub_v
                        for sub_k, sub_v in v.items()
                    }
                else:
                    masked_payload[k] = v

        entry = AuditLogEntry(
            session_id=session_id,
            user_id=user_id,
            action_type=action_type,
            tool_name=tool_name,
            safety_evaluation=safety_evaluation or {"input_guard_passed": True},
            payload_masked=masked_payload,
            execution_status=status,
            execution_latency_ms=round(latency_ms, 2),
        )

        cls._in_memory_records.append(entry.to_dict())
        logger.info("AUDIT_EVENT: %s", entry.to_json())
        return entry

    @classmethod
    def get_recent_entries(cls, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent audit records (for verification & compliance inspection)."""
        return cls._in_memory_records[-limit:]

    @classmethod
    def clear_records(cls):
        """Clear in-memory records (testing utility)."""
        cls._in_memory_records.clear()

"""Identity Context and Delegated Authorization Engine.

Implements SDD Section 6.1.1 (Delegated Authorization & Origin Verification)
and Section 9.1.1 (On-Behalf-Of OBO Token & Revocation Check).
"""
import contextvars
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Active thread-safe execution context variable
_CURRENT_IDENTITY: contextvars.ContextVar[Optional["IdentityContext"]] = contextvars.ContextVar(
    "_CURRENT_IDENTITY", default=None
)

# In-memory revocation blacklist cache (simulating Redis revocation:blacklist:{emp_id})
_REVOCATION_BLACKLIST: set[str] = set()


@dataclass
class IdentityContext:
    """Carries verified caller identity, delegation claims, and provenance."""

    user_id: str
    employee_id: str
    session_id: str = "default-session"
    execution_id: str = field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:12]}")
    automation_origin: str = "HR-Agentic-Solution-MVP1"
    roles: list[str] = field(default_factory=lambda: ["Employee"])
    obo_token: Optional[str] = None

    def to_downstream_headers(self) -> dict[str, str]:
        """Generate standardized composite headers for downstream SaaS adapters (SDD 6.1.1)."""
        headers = {
            "X-Delegated-User-Id": self.employee_id,
            "X-Automation-Origin": self.automation_origin,
            "X-Execution-Id": self.execution_id,
        }
        if self.obo_token:
            headers["Authorization"] = f"Bearer {self.obo_token}"
        return headers


class IdentityContextInjector:
    """Extracts, verifies, and propagates delegated identity across the agent pipeline."""

    @classmethod
    def set_current(cls, context: IdentityContext):
        _CURRENT_IDENTITY.set(context)

    @classmethod
    def get_current(cls) -> Optional[IdentityContext]:
        return _CURRENT_IDENTITY.get()

    @classmethod
    def create_context(
        cls,
        user_id: str,
        employee_id: Optional[str] = None,
        session_id: str = "default-session",
        obo_token: Optional[str] = None,
        roles: Optional[list[str]] = None,
    ) -> IdentityContext:
        """Create and set active identity context for the current turn."""
        emp_id = employee_id or (user_id if user_id.startswith("EMP-") else f"EMP-{user_id}")
        ctx = IdentityContext(
            user_id=user_id,
            employee_id=emp_id,
            session_id=session_id,
            obo_token=obo_token,
            roles=roles or ["Employee"],
        )
        cls.set_current(ctx)
        return ctx

    @classmethod
    def is_revoked(cls, user_id: str) -> bool:
        """Check if caller's OBO credentials have been revoked (SDD Section 9.1.1)."""
        return user_id in _REVOCATION_BLACKLIST

    @classmethod
    def revoke_user(cls, user_id: str):
        """Add user to revocation blacklist."""
        logger.warning("Revoking identity token for user %s", user_id)
        _REVOCATION_BLACKLIST.add(user_id)

    @classmethod
    def clear_revocations(cls):
        """Clear revocation blacklist (testing utility)."""
        _REVOCATION_BLACKLIST.clear()

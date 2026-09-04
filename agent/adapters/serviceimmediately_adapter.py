"""ServiceImmediately ITSM Enterprise Integration Adapter.

Implements SDD Section 6.2 (ITSM Adapter, Incident Lifecycle State Machine,
and Ticket Management).
"""
import datetime
import enum
import logging
from dataclasses import dataclass, field
from typing import Optional

from .. import config
from ..security.identity import IdentityContextInjector

logger = logging.getLogger(__name__)


class IncidentState(str, enum.Enum):
    NEW = "New"
    IN_PROGRESS = "In_Progress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


# Valid state transitions according to SDD Section 6.2.1 state machine
VALID_TRANSITIONS: dict[IncidentState, set[IncidentState]] = {
    IncidentState.NEW: {IncidentState.IN_PROGRESS},
    IncidentState.IN_PROGRESS: {IncidentState.RESOLVED},
    IncidentState.RESOLVED: {IncidentState.CLOSED, IncidentState.IN_PROGRESS},
    IncidentState.CLOSED: set(),  # Terminal state
}


@dataclass
class TicketComment:
    comment_id: str
    ticket_id: str
    author_id: str
    comment_body: str
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


@dataclass
class IncidentTicket:
    ticket_id: str
    requestor_id: str
    category: str
    priority: str
    short_description: str
    detailed_description: str
    state: IncidentState = IncidentState.NEW
    assignee: str = "Unassigned"
    automation_origin: str = "HR-Agentic-Solution-MVP1"
    resolution_notes: Optional[str] = None
    comments: list[TicketComment] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class ServiceImmediatelyAdapter:
    """Adapter mediating access to ServiceImmediately ITSM with state machine enforcement."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or config.MCP_SERVICEIMMEDIATELY_URL
        self._tickets: dict[str, IncidentTicket] = {}
        self._counter = 1000

    def _get_headers(self) -> dict[str, str]:
        ctx = IdentityContextInjector.get_current()
        if ctx:
            return ctx.to_downstream_headers()
        return {
            "X-Delegated-User-Id": config.DEFAULT_EMPLOYEE_ID,
            "X-Automation-Origin": "HR-Agentic-Solution-MVP1",
        }

    def create_incident(
        self,
        requestor_employee_id: str,
        category: str,
        short_description: str,
        detailed_description: str,
        priority: str = "3 - Moderate",
    ) -> dict:
        """Create a new incident ticket in ServiceImmediately (SDD 5.2 / 6.2)."""
        logger.info("ServiceImmediatelyAdapter.create_incident for %s", requestor_employee_id)

        valid_categories = {"Hardware", "Software", "HR_Inquiry", "Facilities", "Network"}
        if category not in valid_categories:
            raise ValueError(f"Invalid category '{category}'. Allowed: {sorted(valid_categories)}")

        valid_priorities = {"1 - Critical", "2 - High", "3 - Moderate", "4 - Low"}
        if priority not in valid_priorities:
            raise ValueError(f"Invalid priority '{priority}'. Allowed: {sorted(valid_priorities)}")

        self._counter += 1
        ticket_id = f"INC{self._counter}"
        ticket = IncidentTicket(
            ticket_id=ticket_id,
            requestor_id=requestor_employee_id,
            category=category,
            priority=priority,
            short_description=short_description,
            detailed_description=detailed_description,
            state=IncidentState.NEW,
        )
        self._tickets[ticket_id] = ticket

        return {
            "status": "CREATED",
            "ticket_id": ticket_id,
            "state": ticket.state.value,
            "priority": ticket.priority,
            "category": ticket.category,
            "short_description": ticket.short_description,
        }

    def get_ticket(self, ticket_id: str) -> IncidentTicket:
        """Retrieve ticket details."""
        logger.info("ServiceImmediatelyAdapter.get_ticket: %s", ticket_id)
        if ticket_id not in self._tickets:
            raise KeyError(f"Ticket '{ticket_id}' not found.")
        return self._tickets[ticket_id]

    def post_comment(self, ticket_id: str, comment: str, author_id: str = "agent") -> dict:
        """Append a note or comment to ticket timeline."""
        logger.info("ServiceImmediatelyAdapter.post_comment to %s", ticket_id)
        ticket = self.get_ticket(ticket_id)
        cid = f"COMM-{len(ticket.comments) + 1}"
        entry = TicketComment(
            comment_id=cid,
            ticket_id=ticket_id,
            author_id=author_id,
            comment_body=comment,
        )
        ticket.comments.append(entry)
        ticket.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {"status": "SUCCESS", "comment_id": cid, "ticket_id": ticket_id}

    def update_status(
        self,
        ticket_id: str,
        target_state: IncidentState | str,
        resolution_notes: Optional[str] = None,
    ) -> dict:
        """Transition ticket status according to SDD 6.2.1 state machine."""
        logger.info("ServiceImmediatelyAdapter.update_status for %s to %s", ticket_id, target_state)
        ticket = self.get_ticket(ticket_id)

        if isinstance(target_state, str):
            try:
                target_state = IncidentState(target_state)
            except ValueError:
                raise ValueError(
                    f"Unknown state '{target_state}'. Allowed: {[s.value for s in IncidentState]}"
                )

        current_state = ticket.state
        allowed = VALID_TRANSITIONS.get(current_state, set())

        if target_state not in allowed:
            raise ValueError(
                f"Forbidden state transition: Cannot transition from '{current_state.value}' "
                f"directly to '{target_state.value}'. Allowed: {[s.value for s in allowed]}"
            )

        # Enforce resolution notes requirement when resolving or closing
        if target_state in (IncidentState.RESOLVED, IncidentState.CLOSED) and not resolution_notes:
            raise ValueError(f"Mandatory 'resolution_notes' required when moving to {target_state.value}.")

        ticket.state = target_state
        if resolution_notes:
            ticket.resolution_notes = resolution_notes
        ticket.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return {
            "status": "UPDATED",
            "ticket_id": ticket_id,
            "previous_state": current_state.value,
            "new_state": target_state.value,
            "resolution_notes": ticket.resolution_notes,
        }

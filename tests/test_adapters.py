"""Unit tests for WorkWeek and ServiceImmediately enterprise adapters."""
import datetime
import pytest
from agent.adapters.serviceimmediately_adapter import (
    IncidentState,
    ServiceImmediatelyAdapter,
)
from agent.adapters.workweek_adapter import LeaveRequest, WorkWeekAdapter


def test_workweek_profile_and_contact():
    adapter = WorkWeekAdapter()
    profile = adapter.get_profile("EMP-1042")
    assert profile.employee_id == "EMP-1042"

    # Update contact with valid E.164 phone
    res = adapter.update_contact(
        "EMP-1042",
        address="10 Pasir Panjang Road, Singapore",
        phone_number="+6598765432",
    )
    assert res["status"] == "SUCCESS"
    assert res["updated_phone"] == "+6598765432"

    # Update contact with invalid phone format should raise ValueError
    with pytest.raises(ValueError, match="E.164"):
        adapter.update_contact("EMP-1042", phone_number="not-a-phone")


def test_workweek_leave_submission():
    adapter = WorkWeekAdapter()
    today = datetime.date.today()
    start = (today + datetime.timedelta(days=5)).isoformat()
    end = (today + datetime.timedelta(days=7)).isoformat()

    # Valid submission
    req = LeaveRequest(start_date=start, end_date=end, leave_type="Vacation", days_requested=3.0)
    res = adapter.submit_leave("EMP-1042", req)
    assert res["status"] == "SUBMITTED"
    assert res["days_requested"] == 3.0
    assert "leave_id" in res

    # Insufficient balance check (balance is now 14 - 3 = 11)
    req_excessive = LeaveRequest(start_date=start, end_date=end, leave_type="Vacation", days_requested=100.0)
    with pytest.raises(ValueError, match="Insufficient vacation leave balance"):
        adapter.submit_leave("EMP-1042", req_excessive)

    # Past start date check
    past_date = (today - datetime.timedelta(days=2)).isoformat()
    req_past = LeaveRequest(start_date=past_date, end_date=end, leave_type="Vacation", days_requested=1.0)
    with pytest.raises(ValueError, match="cannot be in the past"):
        adapter.submit_leave("EMP-1042", req_past)


def test_serviceimmediately_lifecycle_state_machine():
    adapter = ServiceImmediatelyAdapter()

    # 1. Create incident (starts at New)
    created = adapter.create_incident(
        requestor_employee_id="EMP-1042",
        category="Hardware",
        short_description="Monitor request",
        detailed_description="Need second monitor for dual screen setup",
        priority="4 - Low",
    )
    ticket_id = created["ticket_id"]
    assert created["state"] == IncidentState.NEW.value

    # 2. Transition New -> In_Progress (Allowed)
    upd1 = adapter.update_status(ticket_id, IncidentState.IN_PROGRESS)
    assert upd1["new_state"] == IncidentState.IN_PROGRESS.value

    # 3. Transition In_Progress -> Resolved (Allowed with resolution notes)
    upd2 = adapter.update_status(
        ticket_id,
        IncidentState.RESOLVED,
        resolution_notes="Monitor shipped via DHL tracking #12345",
    )
    assert upd2["new_state"] == IncidentState.RESOLVED.value

    # 4. Transition Resolved -> Closed (Allowed with notes)
    upd3 = adapter.update_status(ticket_id, IncidentState.CLOSED, resolution_notes="Delivered and verified.")
    assert upd3["new_state"] == IncidentState.CLOSED.value


def test_serviceimmediately_forbidden_transition():
    adapter = ServiceImmediatelyAdapter()
    created = adapter.create_incident(
        requestor_employee_id="EMP-1042",
        category="Software",
        short_description="License issue",
        detailed_description="Cannot access IDE license",
        priority="3 - Moderate",
    )
    ticket_id = created["ticket_id"]

    # Direct New -> Closed is strictly forbidden by SDD Section 6.2.1
    with pytest.raises(ValueError, match="Forbidden state transition"):
        adapter.update_status(ticket_id, IncidentState.CLOSED, resolution_notes="Premature close")

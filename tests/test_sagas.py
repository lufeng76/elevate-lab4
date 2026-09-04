"""Unit tests for Cross-System Saga Coordinator (UC-2.1, UC-2.2)."""
import datetime
from unittest.mock import MagicMock
import pytest

from agent.adapters.serviceimmediately_adapter import ServiceImmediatelyAdapter
from agent.adapters.workweek_adapter import WorkWeekAdapter
from agent.orchestration.saga_coordinator import SagaCoordinator


def test_medical_leave_saga_happy_path():
    coordinator = SagaCoordinator()
    today = datetime.date.today()
    start = (today + datetime.timedelta(days=10)).isoformat()
    end = (today + datetime.timedelta(days=14)).isoformat()

    result = coordinator.execute_medical_leave_saga(
        employee_id="EMP-1042",
        start_date=start,
        end_date=end,
        days=4.0,
    )
    assert result.status == "SUCCESS"
    assert len(result.steps) == 2
    assert result.steps[0].status == "COMPLETED"
    assert result.steps[1].status == "COMPLETED"
    assert "LV-" in result.user_message
    assert "INC" in result.user_message


def test_medical_leave_saga_compensation_on_si_failure():
    # Mock ServiceImmediately to simulate downstream 503 outage
    mock_si = MagicMock(spec=ServiceImmediatelyAdapter)
    mock_si.create_incident.side_effect = RuntimeError("HTTP 503 Service Unavailable")

    ww = WorkWeekAdapter()
    coordinator = SagaCoordinator(workweek_adapter=ww, serviceimmediately_adapter=mock_si)

    today = datetime.date.today()
    start = (today + datetime.timedelta(days=10)).isoformat()
    end = (today + datetime.timedelta(days=14)).isoformat()

    result = coordinator.execute_medical_leave_saga(
        employee_id="EMP-1042",
        start_date=start,
        end_date=end,
        days=3.0,
    )
    assert result.status == "PARTIAL_FAILURE_COMPENSATED"
    assert result.compensation_executed is True
    assert "ticketing system is temporarily unavailable" in result.user_message


def test_equipment_procurement_saga_happy_path():
    coordinator = SagaCoordinator()
    result = coordinator.execute_equipment_procurement_saga(
        employee_id="EMP-1042",
        equipment_type="27-inch 4K Monitor",
    )
    assert result.status == "SUCCESS"
    assert len(result.steps) == 2
    assert "Hardware procurement ticket" in result.user_message

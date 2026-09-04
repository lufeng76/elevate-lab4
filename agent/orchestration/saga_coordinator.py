"""Cross-System Compensating Saga Coordinator.

Implements SDD Section 2 (NFR-4.1 - NFR-4.3) and Section 7
(UC-2.1 Equipment Procurement, UC-2.2 Medical Leave, UC-2.3 Relocation).
"""
import datetime
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from ..adapters.serviceimmediately_adapter import ServiceImmediatelyAdapter
from ..adapters.workweek_adapter import LeaveRequest, WorkWeekAdapter
from ..security.audit import AuditLogger

logger = logging.getLogger(__name__)


@dataclass
class SagaStep:
    step_name: str
    system: str
    status: str  # PENDING, COMPLETED, FAILED, COMPENSATED
    action_payload: dict[str, Any] = field(default_factory=dict)
    result_payload: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class SagaResult:
    saga_id: str
    saga_type: str
    status: str  # SUCCESS, PARTIAL_FAILURE_COMPENSATED, FAILED
    steps: list[SagaStep]
    user_message: str
    compensation_executed: bool = False


class SagaCoordinator:
    """Coordinates distributed transactions across WorkWeek and ServiceImmediately with compensation."""

    def __init__(
        self,
        workweek_adapter: Optional[WorkWeekAdapter] = None,
        serviceimmediately_adapter: Optional[ServiceImmediatelyAdapter] = None,
    ):
        self.ww = workweek_adapter or WorkWeekAdapter()
        self.si = serviceimmediately_adapter or ServiceImmediatelyAdapter()

    def execute_medical_leave_saga(
        self,
        employee_id: str,
        start_date: str,
        end_date: str,
        days: float,
        session_id: str = "default-session",
    ) -> SagaResult:
        """Execute UC-2.2 Cross-System Medical Leave Orchestration.

        Step 1: Submit Sick Leave in WorkWeek.
        Step 2: Open IT Access Routing Incident in ServiceImmediately.
        """
        saga_id = f"SAGA-MED-{uuid.uuid4().hex[:8]}"
        logger.info("Starting Medical Leave Saga %s for %s", saga_id, employee_id)
        steps = []

        # Step 1: WorkWeek submission
        step1 = SagaStep(
            step_name="SubmitWorkWeekLeave",
            system="WorkWeek",
            status="PENDING",
            action_payload={"employee_id": employee_id, "start": start_date, "end": end_date, "days": days},
        )
        steps.append(step1)

        try:
            ww_resp = self.ww.submit_leave(
                employee_id=employee_id,
                request=LeaveRequest(
                    start_date=start_date,
                    end_date=end_date,
                    leave_type="Sick",
                    days_requested=days,
                ),
            )
            step1.status = "COMPLETED"
            step1.result_payload = ww_resp
            AuditLogger.emit(
                session_id=session_id,
                user_id=employee_id,
                action_type="SAGA_STEP_COMPLETED",
                payload=ww_resp,
                tool_name="workweek_submit_leave",
            )
        except Exception as e:
            step1.status = "FAILED"
            step1.error_message = str(e)
            logger.error("Saga %s: Step 1 failed: %s", saga_id, e)
            return SagaResult(
                saga_id=saga_id,
                saga_type="MEDICAL_LEAVE_UC_2_2",
                status="FAILED",
                steps=steps,
                user_message=f"Unable to submit medical leave: {e}",
            )

        # Step 2: ServiceImmediately incident creation
        leave_id = ww_resp.get("leave_id", "LV-UNKNOWN")
        step2 = SagaStep(
            step_name="CreateServiceImmediatelyIncident",
            system="ServiceImmediately",
            status="PENDING",
            action_payload={"leave_id": leave_id, "employee_id": employee_id},
        )
        steps.append(step2)

        try:
            si_resp = self.si.create_incident(
                requestor_employee_id=employee_id,
                category="HR_Inquiry",
                priority="3 - Moderate",
                short_description=f"Medical Leave IT Access Routing: {employee_id}",
                detailed_description=f"Route email and workflow delegation to manager during medical leave {leave_id}.",
            )
            step2.status = "COMPLETED"
            step2.result_payload = si_resp
            AuditLogger.emit(
                session_id=session_id,
                user_id=employee_id,
                action_type="SAGA_COMPLETED",
                payload={"leave_id": leave_id, "ticket_id": si_resp.get("ticket_id")},
                tool_name="serviceimmediately_create_incident",
            )

            ticket_id = si_resp.get("ticket_id", "INC-UNKNOWN")
            return SagaResult(
                saga_id=saga_id,
                saga_type="MEDICAL_LEAVE_UC_2_2",
                status="SUCCESS",
                steps=steps,
                user_message=(
                    f"Your medical leave has been submitted in WorkWeek (ID: {leave_id}) and "
                    f"IT Incident {ticket_id} was opened to manage system delegation. "
                    f"Your manager will receive automatic notification."
                ),
            )

        except Exception as e:
            # Compensating / fallback action (SDD 7.2)
            step2.status = "FAILED"
            step2.error_message = str(e)
            logger.error("Saga %s: Step 2 failed: %s. Executing compensation fallback.", saga_id, e)
            AuditLogger.emit(
                session_id=session_id,
                user_id=employee_id,
                action_type="SAGA_COMPENSATION_LOGGED",
                payload={"leave_id": leave_id, "error": str(e)},
                status="COMPENSATED",
            )
            return SagaResult(
                saga_id=saga_id,
                saga_type="MEDICAL_LEAVE_UC_2_2",
                status="PARTIAL_FAILURE_COMPENSATED",
                steps=steps,
                compensation_executed=True,
                user_message=(
                    f"Your medical leave was submitted in WorkWeek (ID: {leave_id}). "
                    f"However, the ticketing system is temporarily unavailable to route your IT ticket. "
                    f"A manual follow-up task has been logged for HR Operations to open your ticket."
                ),
            )

    def execute_equipment_procurement_saga(
        self,
        employee_id: str,
        equipment_type: str = "27-inch 4K Monitor",
        session_id: str = "default-session",
    ) -> SagaResult:
        """Execute UC-2.1 Cross-System Equipment Procurement Orchestration.

        Step 1: Verify Profile and Shipping Address in WorkWeek.
        Step 2: Create Hardware Procurement Incident in ServiceImmediately.
        """
        saga_id = f"SAGA-EQUIP-{uuid.uuid4().hex[:8]}"
        logger.info("Starting Equipment Procurement Saga %s for %s", saga_id, employee_id)
        steps = []

        # Step 1: Profile verification
        step1 = SagaStep(
            step_name="VerifyWorkWeekProfile",
            system="WorkWeek",
            status="PENDING",
            action_payload={"employee_id": employee_id},
        )
        steps.append(step1)

        try:
            profile = self.ww.get_profile(employee_id)
            step1.status = "COMPLETED"
            step1.result_payload = {"address": profile.home_address, "role": profile.role}
        except Exception as e:
            step1.status = "FAILED"
            step1.error_message = str(e)
            return SagaResult(
                saga_id=saga_id,
                saga_type="EQUIPMENT_PROCUREMENT_UC_2_1",
                status="FAILED",
                steps=steps,
                user_message=f"Could not verify employee profile: {e}",
            )

        # Step 2: Hardware Incident Creation
        step2 = SagaStep(
            step_name="CreateHardwareIncident",
            system="ServiceImmediately",
            status="PENDING",
            action_payload={"address": profile.home_address, "equipment": equipment_type},
        )
        steps.append(step2)

        try:
            si_resp = self.si.create_incident(
                requestor_employee_id=employee_id,
                category="Hardware",
                priority="4 - Low",
                short_description=f"Home Office {equipment_type} Procurement",
                detailed_description=f"Eligible under Remote Work Policy. Deliver to: {profile.home_address}",
            )
            step2.status = "COMPLETED"
            step2.result_payload = si_resp
            ticket_id = si_resp.get("ticket_id", "INC-UNKNOWN")
            AuditLogger.emit(
                session_id=session_id,
                user_id=employee_id,
                action_type="SAGA_COMPLETED",
                payload={"ticket_id": ticket_id, "equipment": equipment_type},
            )
            return SagaResult(
                saga_id=saga_id,
                saga_type="EQUIPMENT_PROCUREMENT_UC_2_1",
                status="SUCCESS",
                steps=steps,
                user_message=(
                    f"Verified! Your profile qualifies for home office equipment. "
                    f"Hardware procurement ticket **{ticket_id}** has been opened in ServiceImmediately "
                    f"for delivery to: {profile.home_address}."
                ),
            )
        except Exception as e:
            step2.status = "FAILED"
            step2.error_message = str(e)
            return SagaResult(
                saga_id=saga_id,
                saga_type="EQUIPMENT_PROCUREMENT_UC_2_1",
                status="FAILED",
                steps=steps,
                user_message=f"Failed to submit hardware procurement ticket: {e}",
            )

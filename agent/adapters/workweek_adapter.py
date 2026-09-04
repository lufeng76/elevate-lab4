"""WorkWeek HCM Enterprise Integration Adapter.

Implements SDD Section 6.1 (WorkWeek Adapter Specification, validation rules,
and delegated identity propagation).
"""
import datetime
import logging
import re
from dataclasses import dataclass
from typing import Optional

from .. import config
from ..security.identity import IdentityContextInjector

logger = logging.getLogger(__name__)

E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


@dataclass
class EmployeeProfile:
    employee_id: str
    first_name: str = "Alex"
    last_name: str = "Tan"
    email: str = "alex.tan@corp.altostrat.com"
    department: str = "Engineering"
    role: str = "Senior Software Engineer"
    manager_id: str = "EMP-9001"
    hire_date: str = "2021-03-15"
    home_address: str = "12 Marina Boulevard, Singapore 018982"
    phone_number: str = "+6591234567"


@dataclass
class LeaveBalance:
    employee_id: str
    vacation_accrued: float = 18.0
    vacation_used: float = 4.0
    vacation_remaining: float = 14.0
    sick_accrued: float = 14.0
    sick_used: float = 2.0
    sick_remaining: float = 12.0


@dataclass
class LeaveRequest:
    start_date: str
    end_date: str
    leave_type: str  # "Vacation" | "Sick"
    days_requested: float


class WorkWeekAdapter:
    """Adapter mediating access to WorkWeek HCM with deterministic validation."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or config.MCP_WORKWEEK_URL
        # In-memory mock state for local/isolated testing
        self._profiles: dict[str, EmployeeProfile] = {}
        self._balances: dict[str, LeaveBalance] = {}

    def _get_headers(self) -> dict[str, str]:
        ctx = IdentityContextInjector.get_current()
        if ctx:
            return ctx.to_downstream_headers()
        return {
            "X-Delegated-User-Id": config.DEFAULT_EMPLOYEE_ID,
            "X-Automation-Origin": "HR-Agentic-Solution-MVP1",
        }

    def get_profile(self, employee_id: str) -> EmployeeProfile:
        """Fetch employee profile (SDD 6.1.2)."""
        logger.info("WorkWeekAdapter.get_profile for %s", employee_id)
        if employee_id not in self._profiles:
            self._profiles[employee_id] = EmployeeProfile(employee_id=employee_id)
        return self._profiles[employee_id]

    def update_contact(
        self,
        employee_id: str,
        address: Optional[str] = None,
        phone_number: Optional[str] = None,
    ) -> dict:
        """Update personal contact information with validation."""
        logger.info("WorkWeekAdapter.update_contact for %s", employee_id)
        profile = self.get_profile(employee_id)

        if phone_number:
            if not E164_REGEX.match(phone_number):
                raise ValueError(
                    f"Invalid phone number format '{phone_number}'. Must adhere to E.164 (e.g. +6591234567)."
                )
            profile.phone_number = phone_number

        if address:
            if len(address.strip()) < 5:
                raise ValueError("Address must be at least 5 characters long.")
            profile.home_address = address.strip()

        return {
            "status": "SUCCESS",
            "employee_id": employee_id,
            "updated_phone": profile.phone_number,
            "updated_address": profile.home_address,
        }

    def get_balances(self, employee_id: str) -> LeaveBalance:
        """Fetch accrued and remaining PTO balances."""
        logger.info("WorkWeekAdapter.get_balances for %s", employee_id)
        if employee_id not in self._balances:
            self._balances[employee_id] = LeaveBalance(employee_id=employee_id)
        return self._balances[employee_id]

    def submit_leave(self, employee_id: str, request: LeaveRequest) -> dict:
        """Submit a formal leave request with business constraint checks."""
        logger.info("WorkWeekAdapter.submit_leave for %s: %s", employee_id, request)

        # 1. Date format and ordering validation
        try:
            start = datetime.date.fromisoformat(request.start_date)
            end = datetime.date.fromisoformat(request.end_date)
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}. Expected YYYY-MM-DD.")

        today = datetime.date.today()
        if start < today:
            raise ValueError(f"Start date {request.start_date} cannot be in the past.")
        if end < start:
            raise ValueError(f"End date {request.end_date} cannot precede start date {request.start_date}.")

        if request.leave_type not in ("Vacation", "Sick"):
            raise ValueError(f"Unsupported leave type '{request.leave_type}'. Allowed: 'Vacation', 'Sick'.")

        if request.days_requested <= 0:
            raise ValueError("days_requested must be greater than zero.")

        # 2. Balance adequacy check
        balance = self.get_balances(employee_id)
        remaining = balance.vacation_remaining if request.leave_type == "Vacation" else balance.sick_remaining

        if request.days_requested > remaining:
            raise ValueError(
                f"Insufficient {request.leave_type.lower()} leave balance: requested "
                f"{request.days_requested} days, but only {remaining} days available."
            )

        # Deduct balance in mock state
        if request.leave_type == "Vacation":
            balance.vacation_used += request.days_requested
            balance.vacation_remaining -= request.days_requested
        else:
            balance.sick_used += request.days_requested
            balance.sick_remaining -= request.days_requested

        leave_id = f"LV-{datetime.datetime.now().strftime('%Y%m%d')}-{abs(hash(employee_id)) % 10000:04d}"
        return {
            "status": "SUBMITTED",
            "leave_id": leave_id,
            "employee_id": employee_id,
            "leave_type": request.leave_type,
            "days_requested": request.days_requested,
            "remaining_balance": (
                balance.vacation_remaining if request.leave_type == "Vacation" else balance.sick_remaining
            ),
        }

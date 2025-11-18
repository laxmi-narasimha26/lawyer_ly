"""
Billing and Time Tracking Integration Service
Tracks billable hours and integrates with practice management systems
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TimeEntry:
    """Billable time entry"""
    entry_id: str
    user_id: str
    client_id: str
    case_id: str
    activity_type: str  # research, drafting, consultation, court, review
    description: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    billable: bool = True
    hourly_rate: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    billed: bool = False


@dataclass
class Invoice:
    """Client invoice"""
    invoice_id: str
    client_id: str
    case_id: str
    time_entries: List[TimeEntry]
    total_hours: float
    total_amount: Decimal
    issue_date: datetime
    due_date: datetime
    status: str  # draft, sent, paid, overdue
    payment_date: Optional[datetime] = None


class BillingService:
    """
    Billing and time tracking service

    Features:
    - Automatic time tracking
    - Billable hours calculation
    - Invoice generation
    - Rate management
    - Activity-based billing
    - Integration with practice management systems
    """

    def __init__(self):
        self.time_entries: List[TimeEntry] = []
        self.active_timers: Dict[str, Dict[str, Any]] = {}
        self.rate_cards: Dict[str, Decimal] = {
            "research": Decimal("300"),  # ₹300/hour
            "drafting": Decimal("400"),
            "consultation": Decimal("500"),
            "court": Decimal("600"),
            "review": Decimal("350"),
            "default": Decimal("400")
        }

    async def start_timer(
        self,
        user_id: str,
        client_id: str,
        case_id: str,
        activity_type: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """Start time tracking for an activity"""

        timer_key = f"{user_id}_{case_id}"

        # Stop existing timer if any
        if timer_key in self.active_timers:
            await self.stop_timer(user_id, case_id)

        self.active_timers[timer_key] = {
            "user_id": user_id,
            "client_id": client_id,
            "case_id": case_id,
            "activity_type": activity_type,
            "description": description,
            "start_time": datetime.utcnow()
        }

        logger.info(f"Started timer for user {user_id}, case {case_id}")

        return {
            "timer_id": timer_key,
            "started_at": datetime.utcnow().isoformat(),
            "activity_type": activity_type
        }

    async def stop_timer(
        self,
        user_id: str,
        case_id: str,
        description_update: Optional[str] = None
    ) -> TimeEntry:
        """Stop timer and create time entry"""

        timer_key = f"{user_id}_{case_id}"

        if timer_key not in self.active_timers:
            raise ValueError(f"No active timer found for user {user_id}, case {case_id}")

        timer = self.active_timers[timer_key]
        end_time = datetime.utcnow()
        duration = (end_time - timer["start_time"]).total_seconds() / 60  # minutes

        # Update description if provided
        description = description_update or timer["description"]

        # Get rate for activity
        hourly_rate = self.rate_cards.get(
            timer["activity_type"],
            self.rate_cards["default"]
        )

        # Calculate amount
        hours = Decimal(duration) / Decimal(60)
        amount = hours * hourly_rate

        # Create time entry
        entry = TimeEntry(
            entry_id=f"time_{datetime.utcnow().timestamp()}",
            user_id=timer["user_id"],
            client_id=timer["client_id"],
            case_id=timer["case_id"],
            activity_type=timer["activity_type"],
            description=description,
            start_time=timer["start_time"],
            end_time=end_time,
            duration_minutes=int(duration),
            hourly_rate=hourly_rate,
            amount=amount
        )

        self.time_entries.append(entry)

        # Remove active timer
        del self.active_timers[timer_key]

        logger.info(
            f"Stopped timer for user {user_id}, case {case_id}. "
            f"Duration: {duration:.1f} min, Amount: ₹{amount:.2f}"
        )

        return entry

    async def add_manual_entry(
        self,
        user_id: str,
        client_id: str,
        case_id: str,
        activity_type: str,
        description: str,
        duration_minutes: int,
        start_time: Optional[datetime] = None
    ) -> TimeEntry:
        """Add manual time entry"""

        if start_time is None:
            start_time = datetime.utcnow() - timedelta(minutes=duration_minutes)

        end_time = start_time + timedelta(minutes=duration_minutes)

        # Get rate
        hourly_rate = self.rate_cards.get(activity_type, self.rate_cards["default"])

        # Calculate amount
        hours = Decimal(duration_minutes) / Decimal(60)
        amount = hours * hourly_rate

        entry = TimeEntry(
            entry_id=f"time_{datetime.utcnow().timestamp()}",
            user_id=user_id,
            client_id=client_id,
            case_id=case_id,
            activity_type=activity_type,
            description=description,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            hourly_rate=hourly_rate,
            amount=amount
        )

        self.time_entries.append(entry)

        logger.info(f"Added manual time entry: {duration_minutes} min, ₹{amount:.2f}")

        return entry

    async def generate_invoice(
        self,
        client_id: str,
        case_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Invoice:
        """Generate invoice for client/case"""

        # Filter time entries
        entries = [
            entry for entry in self.time_entries
            if entry.client_id == client_id
            and entry.case_id == case_id
            and entry.billable
            and not entry.billed
        ]

        # Apply date filters
        if start_date:
            entries = [e for e in entries if e.start_time >= start_date]
        if end_date:
            entries = [e for e in entries if e.end_time <= end_date]

        if not entries:
            raise ValueError("No billable entries found for the specified criteria")

        # Calculate totals
        total_minutes = sum(e.duration_minutes for e in entries)
        total_hours = total_minutes / 60
        total_amount = sum(e.amount for e in entries)

        # Create invoice
        invoice = Invoice(
            invoice_id=f"INV_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            client_id=client_id,
            case_id=case_id,
            time_entries=entries,
            total_hours=total_hours,
            total_amount=total_amount,
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=30),
            status="draft"
        )

        # Mark entries as billed
        for entry in entries:
            entry.billed = True

        logger.info(
            f"Generated invoice {invoice.invoice_id}: "
            f"{total_hours:.2f} hours, ₹{total_amount:.2f}"
        )

        return invoice

    def get_time_entries(
        self,
        user_id: Optional[str] = None,
        client_id: Optional[str] = None,
        case_id: Optional[str] = None,
        unbilled_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get time entries with optional filters"""

        entries = self.time_entries

        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        if client_id:
            entries = [e for e in entries if e.client_id == client_id]
        if case_id:
            entries = [e for e in entries if e.case_id == case_id]
        if unbilled_only:
            entries = [e for e in entries if not e.billed]

        return [
            {
                "entry_id": e.entry_id,
                "user_id": e.user_id,
                "client_id": e.client_id,
                "case_id": e.case_id,
                "activity_type": e.activity_type,
                "description": e.description,
                "start_time": e.start_time.isoformat(),
                "duration_minutes": e.duration_minutes,
                "hourly_rate": float(e.hourly_rate),
                "amount": float(e.amount),
                "billed": e.billed
            }
            for e in entries
        ]

    def get_active_timers(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get active timers"""

        timers = []

        for timer_key, timer in self.active_timers.items():
            if user_id and timer["user_id"] != user_id:
                continue

            elapsed = (datetime.utcnow() - timer["start_time"]).total_seconds() / 60

            timers.append({
                "timer_id": timer_key,
                "user_id": timer["user_id"],
                "case_id": timer["case_id"],
                "activity_type": timer["activity_type"],
                "description": timer["description"],
                "started_at": timer["start_time"].isoformat(),
                "elapsed_minutes": int(elapsed)
            })

        return timers

    def set_rate(self, activity_type: str, rate: Decimal):
        """Set hourly rate for activity type"""
        self.rate_cards[activity_type] = rate
        logger.info(f"Set rate for {activity_type}: ₹{rate}/hour")

    def get_rates(self) -> Dict[str, float]:
        """Get all hourly rates"""
        return {k: float(v) for k, v in self.rate_cards.items()}


# Global instance
billing_service = BillingService()

import csv
import io
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List


def _parse_int(value):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"n/a", "na", "null", "none"}:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def parse_fat_csv(csv_content: str) -> List[Dict[str, int | str]]:
    """Parse a CSV export from the alliance FAT report into structured rows."""
    if not csv_content:
        return []

    reader = csv.DictReader(io.StringIO(csv_content))
    if reader.fieldnames is None:
        return []

    records = []
    for row in reader:
        if not row or not row.get("Main Character"):
            continue

        name = (row.get("Main Character") or "").strip()
        if not name:
            continue

        records.append(
            {
                "character_name": name,
                "total_fats": _parse_int(row.get("Total FATs")),
                "strategic_fats": _parse_int(row.get("Strategic & Deployment")),
                "regular_fats": _parse_int(row.get("Total FATs")) - _parse_int(row.get("Strategic & Deployment")),
            }
        )
    return records


def calculate_member_payout(strategic_fats: int, regular_fats: int, strategic_rate: float, regular_rate: float) -> int:
    """Return the member payout in ISK based on the configured FAT rates."""
    return int((strategic_fats * strategic_rate) + (regular_fats * regular_rate))


def evaluate_member_threshold(member_total_fats: int, required_fats: int) -> bool:
    """Return True when the member is below the configured threshold and should receive the corp role."""
    return member_total_fats < required_fats


def resolve_group_action(member_total_fats: int, required_fats: int, remove_above_fats: int | None = None) -> str:
    """Return action needed for the FAT compliance group: add, remove, or none."""
    if remove_above_fats is not None and member_total_fats >= remove_above_fats:
        return "remove"
    if member_total_fats < required_fats:
        return "add"
    return "none"


def sync_member_group(user, member_total_fats: int, required_fats: int, group_name: str | None = None, group_id: int | None = None, remove_above_fats: int | None = 15):
    """Add or remove an Alliance Auth group for the member based on the FAT threshold."""
    if not user or not group_name and group_id is None:
        return "none"

    try:
        from django.contrib.auth.models import Group
    except ImportError:
        return "none"

    group = None
    if group_id is not None:
        try:
            group = Group.objects.get(pk=group_id)
        except Group.DoesNotExist:
            group = None
    elif group_name:
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            group = None

    if group is None:
        return "none"

    action = resolve_group_action(member_total_fats, required_fats, remove_above_fats)
    if action == "add" and not user.groups.filter(pk=group.pk).exists():
        user.groups.add(group)
    elif action == "remove" and user.groups.filter(pk=group.pk).exists():
        user.groups.remove(group)
    return action


def create_invoice_deduction(user, amount: int | float, reason: str, invoice_due_days: int = 7):
    """Create a deduction invoice in the invoice manager when the app is installed."""
    if not user or amount <= 0:
        return None

    try:
        from django.utils import timezone
        from invoices.models import Invoice
    except ImportError:
        return None

    main = getattr(user.profile, "main_character", None)
    if main is None:
        return None

    invoice_ref = f"fat-reward-{main.character_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
    due_date = timezone.now() + timedelta(days=invoice_due_days)
    invoice = Invoice.objects.create(
        character=main,
        amount=Decimal(str(amount)),
        invoice_ref=invoice_ref,
        due_date=due_date,
        note=reason,
        paid=False,
    )
    return invoice


def send_webhook_notification(webhook_url: str, message: str):
    """Send a payout message to a configured webhook if provided."""
    if not webhook_url:
        return False

    try:
        import requests
    except ImportError:
        return False

    payload = {"content": message}
    response = requests.post(webhook_url, json=payload, timeout=10)
    return response.status_code in {200, 201, 202, 204}

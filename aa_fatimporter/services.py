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
    """Parse an alliance FAT CSV export into structured rows for reporting.

    This data is intentionally separate from corp FAT compliance; the corp threshold
    should be evaluated from corp-side AA data, not from the imported alliance CSV.
    """
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
    """Return True when the corp member is below the configured corp FAT threshold."""
    return member_total_fats < required_fats


def evaluate_corp_fat_threshold(corp_total_fats: int, corp_required_fats: int) -> bool:
    """This is the corp-side check used for the corp compliance group."""
    return corp_total_fats < corp_required_fats


def get_corp_fat_total_from_source(source_name: str, user=None, days: int = 90) -> int:
    """Return the corp FAT total from the configured corp data source.

    AFAT is treated as a corp FAT data source for the corp compliance logic. When the source is not
    installed or unavailable, this function safely returns zero instead of crashing.
    """
    if source_name == "afat":
        try:
            from afat.models import FatLink
        except ImportError:
            return 0

        if user is not None:
            try:
                return FatLink.objects.filter(
                    character__character_ownership__user=user,
                ).count()
            except Exception:
                return 0
        return 0

    return 0


def resolve_group_action(member_total_fats: int, required_fats: int, remove_above_fats: int | None = None) -> str:
    """Return the action for a compliance group based on a total FAT count.

    The removal threshold is treated as "above this value" rather than "at or above" to avoid
    removing members exactly at the configured cutoff.
    """
    if remove_above_fats is not None and member_total_fats > remove_above_fats:
        return "remove"
    if member_total_fats < required_fats:
        return "add"
    return "none"


def resolve_alliance_and_corp_group_actions(alliance_total_fats: int, corp_total_fats: int, alliance_required: int, corp_required: int, alliance_remove_above: int | None = None, corp_remove_above: int | None = None):
    """Return the group actions for both alliance and corp compliance checks.

    The admin may choose whether both checks target the same AA group.
    """
    return {
        "alliance": resolve_group_action(alliance_total_fats, alliance_required, alliance_remove_above),
        "corp": resolve_group_action(corp_total_fats, corp_required, corp_remove_above),
    }


def resolve_group_selection_config(same_group_for_both: bool):
    """Return the admin field layout for one or two group dropdowns."""
    if same_group_for_both:
        return {"mode": "single", "fields": ["alliance_group"]}
    return {"mode": "dual", "fields": ["alliance_group", "corp_group"]}


def aggregate_member_fat_totals(records: List[Dict[str, int | str]]) -> Dict[str, int]:
    """Aggregate FAT totals by member name, normalizing to lowercase for comparison."""
    totals: Dict[str, int] = {}
    for record in records:
        name = str(record.get("character_name") or "").strip()
        if not name:
            continue
        normalized = name.lower()
        totals[normalized] = totals.get(normalized, 0) + int(record.get("total_fats", 0) or 0)
    return totals


def resolve_user_for_character_name(character_name: str):
    """Best-effort lookup for an AA user by main character name."""
    if not character_name:
        return None

    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(profile__main_character__character_name__iexact=character_name).first()
    except Exception:
        return None


def apply_member_fat_rules(records: List[Dict[str, int | str]], settings) -> Dict[str, object]:
    """Evaluate member FATs against configured alliance/corp thresholds and return actions.

    This is the runtime enforcement layer used after the CSV import completes.
    """
    totals = aggregate_member_fat_totals(records)
    members: Dict[str, Dict[str, object]] = {}

    for name, total in totals.items():
        alliance_action = resolve_group_action(
            total,
            getattr(settings, "alliance_required_fats_per_90_days", 0),
            getattr(settings, "alliance_remove_above_fats", None),
        )
        corp_action = resolve_group_action(
            total,
            getattr(settings, "corp_required_fats_per_90_days", 0),
            getattr(settings, "corp_remove_group_above_fats", None),
        )
        members[name] = {
            "character_name": name,
            "total_fats": total,
            "alliance_action": alliance_action,
            "corp_action": corp_action,
        }

    return {"totals": totals, "members": members}


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

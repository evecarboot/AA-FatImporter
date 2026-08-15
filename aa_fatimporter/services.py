import csv
import hashlib
import io
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List

from aa_fatimporter.models import (
    FatImportSettings,
    FatImportSummarySettings,
    FatPayoutRecord,
)

logger = logging.getLogger(__name__)


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


def _find_column(row, preferred_name, fieldnames):
    """Find a column value using the preferred name, with case-insensitive fallback."""
    if preferred_name in row:
        return row.get(preferred_name)
    # Case-insensitive match
    for fname in fieldnames:
        if fname and fname.lower() == preferred_name.lower():
            return row.get(fname)
    # Fuzzy match: check if preferred_name is a substring of any fieldname
    for fname in fieldnames:
        if fname and preferred_name.lower() in fname.lower():
            return row.get(fname)
    return None


def parse_fat_csv(csv_content: str, column_character: str = "Main Character",
                  column_total_fats: str = "Total FATs",
                  column_strategic_fats: str = "Strategic & Deployment") -> List[Dict[str, int | str]]:
    """Parse an alliance FAT CSV export into structured rows for reporting.

    Column names are configurable to support different FAT export formats. Falls back
    to case-insensitive and fuzzy matching when the exact column name isn't found.
    """
    if not csv_content:
        return []

    reader = csv.DictReader(io.StringIO(csv_content))
    if reader.fieldnames is None:
        return []

    fieldnames = reader.fieldnames
    records = []
    for row in reader:
        if not row:
            continue

        name_raw = _find_column(row, column_character, fieldnames)
        if not name_raw:
            continue

        name = (name_raw or "").strip()
        if not name:
            continue

        total = _parse_int(_find_column(row, column_total_fats, fieldnames))
        strategic = _parse_int(_find_column(row, column_strategic_fats, fieldnames))

        records.append(
            {
                "character_name": name,
                "total_fats": total,
                "strategic_fats": strategic,
                "regular_fats": total - strategic,
            }
        )
    return records


def compute_csv_hash(csv_content: str) -> str:
    """Return a SHA-256 hash of the CSV content for duplicate detection."""
    if not csv_content:
        return ""
    return hashlib.sha256(csv_content.encode("utf-8")).hexdigest()


def apply_strategic_weighting(total_fats: int, strategic_fats: int, multiplier) -> int:
    """Apply a strategic FAT multiplier to compute a weighted total for compliance.

    Weighted total = regular_fats + (strategic_fats * multiplier).
    Returns an integer (rounded down) for comparison against thresholds.
    """
    multiplier_dec = Decimal(str(multiplier))
    regular = total_fats - strategic_fats
    weighted = Decimal(str(regular)) + (Decimal(str(strategic_fats)) * multiplier_dec)
    return int(weighted)


def log_audit_event(action: str, user=None, character_name: str = "", details: str = ""):
    """Create a FatAuditLog entry. Silently fails if the table doesn't exist."""
    try:
        from aa_fatimporter.models import FatAuditLog
        FatAuditLog.objects.create(
            user=user,
            action=action,
            character_name=character_name,
            details=details,
        )
    except Exception:
        logger.debug("Failed to create audit log entry", exc_info=True)


def notify_user_group_change(user, action: str, group_name: str, scope: str):
    """Notify a member when they are added to or removed from a compliance group.

    Uses AA's notification system when available, falls back to no-op.
    """
    try:
        from allianceauth.notifications import notify
        if action == "add":
            message = f"You have been added to the {scope} FAT compliance group '{group_name}'."
        elif action == "remove":
            message = f"You have been removed from the {scope} FAT compliance group '{group_name}' due to FAT requirements."
        else:
            return
        notify(user, "FAT Compliance Update", message)
    except ImportError:
        logger.debug("allianceauth.notifications not available, skipping notification")
    except Exception:
        logger.debug("Failed to send group change notification", exc_info=True)


def calculate_member_payout(strategic_fats: int, regular_fats: int, strategic_rate, regular_rate) -> Decimal:
    """Return the member payout in ISK based on the configured FAT rates.

    Rates may be ``Decimal``, ``int``, ``float`` or strings; they are coerced to
    ``Decimal`` so the result is exact and safe to store in a ``DecimalField``.
    """
    strategic = Decimal(str(strategic_rate)) * Decimal(strategic_fats)
    regular = Decimal(str(regular_rate)) * Decimal(regular_fats)
    return strategic + regular


def evaluate_member_threshold(member_total_fats: int, required_fats: int) -> bool:
    """Return True when the corp member is below the configured corp FAT threshold."""
    return member_total_fats < required_fats


def evaluate_corp_fat_threshold(corp_total_fats: int, corp_required_fats: int) -> bool:
    """This is the corp-side check used for the corp compliance group."""
    return corp_total_fats < corp_required_fats


def get_corp_fat_total_from_source(source_name: str, user=None, days: int = 90) -> int:
    """Return the corp FAT total from the configured corp data source.

    AFAT is treated as a corp FAT data source for the corp compliance logic. Individual FAT
    registrations are stored in the ``Fat`` model (linked to ``FatLink`` via ``fatlink`` FK).
    The ``afattime`` field on ``FatLink`` records when the FAT link was created and is used
    to filter to the configured ``days`` window (default 90). When the source is not installed
    or unavailable, this function safely returns zero instead of crashing.
    """
    if source_name == "afat":
        try:
            from afat.models import Fat
        except ImportError:
            return 0

        if user is not None:
            try:
                from django.utils import timezone
                from datetime import timedelta
                cutoff = timezone.now() - timedelta(days=days)
                return Fat.objects.filter(
                    character__character_ownership__user=user,
                    fatlink__afattime__gte=cutoff,
                ).count()
            except Exception:
                return 0
        return 0

    return 0


def afat_available() -> bool:
    """Return True when the AFAT app is installed and importable."""
    try:
        from afat.models import Fat  # noqa: F401
        return True
    except ImportError:
        return False


def evaluate_corp_compliance_for_user(user, settings) -> tuple[int, str]:
    """Return ``(corp_total_fats, corp_action)`` for a resolved AA user.

    Corp FATs are sourced from AFAT (the corp data source), not the alliance CSV.
    When AFAT is not installed the action is ``"skipped"`` so callers can skip corp
    group enforcement entirely instead of marking everyone non-compliant.
    """
    if user is None or not afat_available():
        return 0, "skipped"

    corp_required = getattr(settings, "corp_required_fats_per_90_days", 0)
    corp_remove_above = getattr(settings, "corp_remove_group_above_fats", None)
    days = getattr(settings, "fat_window_days", 90)
    corp_total = get_corp_fat_total_from_source("afat", user=user, days=days)
    action = resolve_group_action(corp_total, corp_required, corp_remove_above)
    return corp_total, action


def is_user_exempt(user, scope="both") -> bool:
    """Return True if the user has an active FAT exemption for the given scope.

    ``scope`` is one of ``"alliance"``, ``"corp"``, or ``"both"``. An exemption with
    scope ``"both"`` covers all checks; an exemption with a specific scope only covers
    that scope.
    """
    if user is None:
        return False

    try:
        from aa_fatimporter.models import FatExemption
        exemptions = FatExemption.objects.filter(user=user)
        for exemption in exemptions:
            if not exemption.is_active:
                continue
            if exemption.scope == "both" or exemption.scope == scope:
                return True
        return False
    except Exception:
        return False


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


def aggregate_member_fat_breakdown(records: List[Dict[str, int | str]]) -> Dict[str, Dict[str, int]]:
    """Aggregate total/strategic/regular FATs per member, keyed by lowercase name."""
    breakdown: Dict[str, Dict[str, int]] = {}
    for record in records:
        name = str(record.get("character_name") or "").strip()
        if not name:
            continue
        normalized = name.lower()
        entry = breakdown.setdefault(normalized, {"total_fats": 0, "strategic_fats": 0, "regular_fats": 0})
        entry["total_fats"] += int(record.get("total_fats", 0) or 0)
        entry["strategic_fats"] += int(record.get("strategic_fats", 0) or 0)
        entry["regular_fats"] += int(record.get("regular_fats", 0) or 0)
    return breakdown


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
    breakdown = aggregate_member_fat_breakdown(records)
    members: Dict[str, Dict[str, object]] = {}

    for name, total in totals.items():
        entry = breakdown.get(name, {})
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
            "strategic_fats": entry.get("strategic_fats", 0),
            "regular_fats": entry.get("regular_fats", 0),
            "alliance_action": alliance_action,
            "corp_action": corp_action,
        }

    return {"totals": totals, "members": members}


def _resolve_summary_config() -> tuple[object, object]:
    """Prefer the dedicated summary settings only when they are explicitly configured.

    The main FAT import settings remain the live default for admin-configured thresholds and
    webhook values. This prevents the summary system from silently ignoring the values the admin
    has configured in the main settings page.
    """
    primary_settings = FatImportSettings.objects.first()
    summary_settings = FatImportSummarySettings.objects.first()

    if summary_settings is None:
        return primary_settings, primary_settings

    summary_url = getattr(summary_settings, "webhook_url", "") or ""
    summary_enabled = getattr(summary_settings, "webhook_enabled", False)
    summary_post = getattr(summary_settings, "post_import_summary", False)
    summary_title = getattr(summary_settings, "summary_title", "") or ""

    if summary_url or summary_enabled or summary_post or summary_title.strip() not in ("", "FAT Import Summary"):
        return summary_settings, primary_settings

    return primary_settings, summary_settings


def format_import_summary_message(records: List[Dict[str, int | str]], settings) -> str:
    """Build a compact Discord-friendly leaderboard for the import summary."""
    totals = aggregate_member_fat_totals(records)
    threshold = getattr(settings, "alliance_required_fats_per_90_days", 0)
    title = getattr(settings, "summary_title", "FAT Import Summary") or "FAT Import Summary"
    top_count = int(getattr(settings, "dashboard_top_count", 5) or 5)
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    top = ordered[:top_count]
    bottom = ordered[-top_count:][::-1]
    below_threshold = [
        f"{name.title()} ({total})"
        for name, total in ordered
        if total < threshold
    ]

    top_line = "\n".join(
        f"{index}. {name.title()} - {total} FATs"
        for index, (name, total) in enumerate(top, start=1)
    ) or "No members in top list."

    bottom_line = "\n".join(
        f"{index}. {name.title()} - {total} FATs"
        for index, (name, total) in enumerate(bottom, start=1)
    ) or "No members in bottom list."

    below_line = ", ".join(below_threshold) if below_threshold else "None"

    member_count = len(ordered)
    below_count = len(below_threshold)
    goal_count = sum(1 for _, total in ordered if total >= threshold)

    return (
        "```md\n"
        f"{title}\n"
        "=" * min(len(title), 40) + "\n"
        f"Members processed: {member_count}\n"
        f"At or above minimum: {goal_count}\n"
        f"Below alliance minimum: {below_count}\n"
        "\n"
        f"Top {min(top_count, len(top) or top_count)}\n"
        "-" * min(len(f"Top {min(top_count, len(top) or top_count)}"), 40) + "\n"
        f"{top_line}\n"
        "\n"
        f"Bottom {min(top_count, len(bottom) or top_count)}\n"
        "-" * min(len(f"Bottom {min(top_count, len(bottom) or top_count)}"), 40) + "\n"
        f"{bottom_line}\n"
        "\n"
        "Below alliance minimum\n"
        "----------------------\n"
        f"{below_line}\n"
        "```"
    )


def send_import_summary_webhook(records: List[Dict[str, int | str]], settings=None) -> bool:
    """Send the import summary to the admin-configured webhook.

    Settings resolution priority:
    1. Explicitly-passed ``settings`` with a webhook_url (caller override)
    2. Dedicated ``FatImportSummarySettings`` when explicitly configured
    3. Main ``FatImportSettings`` as fallback
    """
    if settings is not None and getattr(settings, "webhook_url", ""):
        settings_for_summary = settings
    else:
        settings_for_summary, _ = _resolve_summary_config()

    if settings_for_summary is None:
        return False

    webhook_url = getattr(settings_for_summary, "webhook_url", "") or ""
    if not webhook_url:
        return False

    enabled = getattr(settings_for_summary, "webhook_enabled", False) or getattr(
        settings_for_summary, "post_import_summary", False
    )
    if not enabled:
        return False

    message = format_import_summary_message(records, settings_for_summary)
    # Try synchronous first; if it fails, queue a retry task.
    success = send_webhook_notification(webhook_url, message)
    if not success:
        try:
            from aa_fatimporter.tasks import send_webhook_with_retry
            send_webhook_with_retry.apply_async(args=[webhook_url, message])
        except Exception:
            pass
    return success


def sync_member_group(user, member_total_fats: int, required_fats: int, group_name: str | None = None, group_id: int | None = None, remove_above_fats: int | None = 15, notify_scope: str | None = None, notify: bool = False):
    """Add or remove an Alliance Auth group for the member based on the FAT threshold."""
    if not user or (not group_name and group_id is None):
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
        log_audit_event("group_add", user=user, character_name=getattr(user, 'username', ''),
                        details=f"Added to group '{group.name}'")
        if notify:
            notify_user_group_change(user, "add", group.name, scope=notify_scope or "FAT")
    elif action == "remove" and user.groups.filter(pk=group.pk).exists():
        user.groups.remove(group)
        log_audit_event("group_remove", user=user, character_name=getattr(user, 'username', ''),
                        details=f"Removed from group '{group.name}'")
        if notify:
            notify_user_group_change(user, "remove", group.name, scope=notify_scope or "FAT")
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


def _generate_payout_ref(character_name, import_record):
    """Generate a unique payout reference for in-game ISK transfer matching."""
    import hashlib
    raw = f"fat-{import_record.pk}-{character_name}-{import_record.imported_at.strftime('%Y%m%d%H%M%S')}"
    return "FAT-" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:12].upper()


def process_member_payout(user, character_name, strategic_fats, regular_fats, total_fats, settings_obj, import_record):
    """Create a ``FatPayoutRecord`` for a member based on the configured payout method.

    Returns the created ``FatPayoutRecord`` (or ``None`` when payouts are disabled or the
    calculated amount is zero). A unique ``payout_ref`` is always generated so the director
    can include it in the in-game ISK transfer reason for ESI auto-matching.
    ``invoice_deduction`` payouts are marked ``paid`` immediately when the invoice is created;
    ``withdrawal`` and ``manual`` payouts are ``pending`` for manual or ESI-auto-matched disbursement.
    """
    if not getattr(settings_obj, "payout_enabled", False):
        return None

    payout_method = getattr(settings_obj, "payout_method", "manual") or "manual"
    valid_methods = {"withdrawal", "invoice_deduction", "manual"}
    if payout_method not in valid_methods:
        payout_method = "manual"

    strategic_rate = getattr(settings_obj, "reward_for_strategic_fat", 0) or 0
    regular_rate = getattr(settings_obj, "reward_for_regular_fat", 0) or 0
    amount = calculate_member_payout(strategic_fats, regular_fats, strategic_rate, regular_rate)
    if amount <= 0:
        return None

    payout_ref = _generate_payout_ref(character_name, import_record)
    status = "pending"
    paid_at = None

    if payout_method == "invoice_deduction":
        reason = f"FAT reward {payout_ref} for {character_name}: {strategic_fats} strategic / {regular_fats} regular"
        invoice = create_invoice_deduction(user, amount, reason) if user is not None else None
        if invoice is not None:
            from django.utils import timezone
            status = "paid"
            paid_at = timezone.now()

    payout = FatPayoutRecord.objects.create(
        record=import_record,
        user=user,
        character_name=character_name,
        strategic_fats=strategic_fats,
        regular_fats=regular_fats,
        total_fats=total_fats,
        amount=amount,
        payout_method=payout_method,
        status=status,
        payout_ref=payout_ref,
        paid_at=paid_at,
    )
    return payout


def format_payout_summary_message(payouts) -> str:
    """Build a compact Discord-friendly payout report from a list of ``FatPayoutRecord``."""
    if not payouts:
        return ""

    total_amount = sum((p.amount for p in payouts), Decimal("0"))
    lines = [
        f"{index}. {p.character_name.title()} - {p.amount} ISK ({p.payout_method}, {p.status})"
        for index, p in enumerate(payouts, start=1)
    ]
    body = "\n".join(lines) or "No payouts."
    return (
        "```md\n"
        "FAT Payout Summary\n"
        "==================\n"
        f"Payouts: {len(payouts)}\n"
        f"Total: {total_amount} ISK\n"
        "\n"
        f"{body}\n"
        "```"
    )


def send_payout_summary_webhook(payouts) -> bool:
    """Send the payout summary to the admin-configured webhook, if any."""
    if not payouts:
        return False

    settings_for_summary, _ = _resolve_summary_config()
    if settings_for_summary is None:
        return False

    webhook_url = getattr(settings_for_summary, "webhook_url", "") or ""
    if not webhook_url:
        return False

    message = format_payout_summary_message(payouts)
    if not message:
        return False
    success = send_webhook_notification(webhook_url, message)
    if not success:
        try:
            from aa_fatimporter.tasks import send_webhook_with_retry
            send_webhook_with_retry.apply_async(args=[webhook_url, message])
        except Exception:
            pass
    return success


def send_webhook_notification(webhook_url: str, message: str):
    """Send a payout message to a configured webhook if provided."""
    if not webhook_url:
        return False

    try:
        import requests
    except ImportError:
        return False

    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code in {200, 201, 202, 204}
    except requests.RequestException:
        return False

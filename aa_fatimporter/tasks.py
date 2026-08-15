import logging
from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from aa_fatimporter.models import FatPayoutRecord

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def send_webhook_with_retry(self, webhook_url, message):
    """Send a webhook notification with exponential backoff retry.

    Retries up to 5 times with exponential backoff (60s, 120s, 240s, ...) and
    jitter to avoid thundering herd against Discord rate limits.
    """
    from aa_fatimporter.services import send_webhook_notification, log_audit_event

    success = send_webhook_notification(webhook_url, message)
    if success:
        log_audit_event("webhook_sent", details=f"URL: {webhook_url}")
        return True
    else:
        log_audit_event("webhook_failed", details=f"URL: {webhook_url}")
        raise self.retry()


def _resolve_member_character_id(payout):
    """Best-effort lookup of the member's main EVE character ID from the payout's user."""
    if payout.user is None:
        return None
    try:
        main = getattr(payout.user.profile, "main_character", None)
        if main is not None:
            return getattr(main, "character_id", None)
    except Exception:
        pass
    return None


def _match_corp_wallet_entries(payouts):
    """Check aa-ledger corp wallet journal entries for matching ISK transfers.

    A director sends ISK from the corp wallet to the member with the ``payout_ref``
    in the reason field. In the corp wallet journal this appears as a negative-amount
    entry whose ``reason`` or ``description`` contains the payout_ref. When the
    member's character ID can be resolved, the ``second_party_id`` is also verified
    to ensure the ISK went to the right person.
    """
    matched = []
    try:
        from ledger.models.corporationaudit import CorporationWalletJournalEntry
    except ImportError:
        return matched

    for payout in payouts:
        try:
            entry = CorporationWalletJournalEntry.objects.filter(
                reason__icontains=payout.payout_ref,
                amount__lt=0,
            ).first()
            if entry is None:
                entry = CorporationWalletJournalEntry.objects.filter(
                    description__icontains=payout.payout_ref,
                    amount__lt=0,
                ).first()
            if entry is None:
                continue

            # Verify the amount matches (absolute value of the negative entry).
            entry_amount = abs(Decimal(str(entry.amount)))
            if entry_amount != Decimal(str(payout.amount)):
                logger.info(
                    "Payout %s: corp wallet entry found but amount mismatch (%s vs %s)",
                    payout.payout_ref,
                    entry_amount,
                    payout.amount,
                )
                continue

            # When possible, verify the ISK went to the right member.
            expected_char_id = _resolve_member_character_id(payout)
            if expected_char_id is not None:
                second_party = getattr(entry, "second_party_id", None)
                if second_party is not None and int(second_party) != int(expected_char_id):
                    logger.info(
                        "Payout %s: corp wallet entry found but recipient mismatch "
                        "(second_party_id=%s, expected=%s)",
                        payout.payout_ref,
                        second_party,
                        expected_char_id,
                    )
                    continue

            matched.append(payout)
        except Exception:
            logger.exception("Error checking corp wallet for payout %s", payout.payout_ref)
    return matched


def _match_character_wallet_entries(payouts):
    """Check corptools character wallet journal entries for matching ISK transfers.

    If the member has their character wallet audited via corptools, the incoming ISK
    transfer appears as a positive-amount entry whose ``reason`` or ``description``
    contains the payout_ref.
    """
    matched = []
    try:
        from corptools.models import CharacterWalletJournalEntry
    except ImportError:
        return matched

    for payout in payouts:
        if payout.user is None:
            continue
        try:
            entry = CharacterWalletJournalEntry.objects.filter(
                reason__icontains=payout.payout_ref,
                amount__gt=0,
            ).first()
            if entry is None:
                entry = CharacterWalletJournalEntry.objects.filter(
                    description__icontains=payout.payout_ref,
                    amount__gt=0,
                ).first()
            if entry is None:
                continue

            entry_amount = Decimal(str(entry.amount))
            if entry_amount != Decimal(str(payout.amount)):
                logger.info(
                    "Payout %s: character wallet entry found but amount mismatch (%s vs %s)",
                    payout.payout_ref,
                    entry_amount,
                    payout.amount,
                )
                continue

            matched.append(payout)
        except Exception:
            logger.exception("Error checking character wallet for payout %s", payout.payout_ref)
    return matched


@shared_task
def match_pending_payouts(payout_refs=None):
    """Scan wallet journal entries for ISK transfers matching pending payout_refs.

    Can be called with a specific list of refs (from the admin action) or with no
    args (from the Celery beat schedule) to check all pending payouts.

    Matching priority:
    1. aa-ledger corp wallet journal (primary — withdrawals are paid from the corp wallet)
    2. corptools character wallet journal (fallback — if the member's wallet is audited)

    Matching payouts are marked as ``paid`` atomically.
    """
    queryset = FatPayoutRecord.objects.filter(
        status__in=["pending", "approved"], payout_ref__gt=""
    )
    if payout_refs:
        queryset = queryset.filter(payout_ref__in=payout_refs)

    payouts = list(queryset)
    if not payouts:
        logger.info("No pending payouts to match.")
        return 0

    matched = _match_corp_wallet_entries(payouts)
    unmatched_refs = {p.payout_ref for p in matched}
    still_pending = [p for p in payouts if p.payout_ref not in unmatched_refs]
    matched.extend(_match_character_wallet_entries(still_pending))

    if not matched:
        logger.info("No wallet matches found for %d pending payout(s).", len(payouts))
        return 0

    now = timezone.now()
    with transaction.atomic():
        updated = 0
        for payout in matched:
            updated += FatPayoutRecord.objects.filter(
                pk=payout.pk, status__in=["pending", "approved"]
            ).update(status="paid", paid_at=now)

    logger.info("Matched and marked %d payout(s) as paid via ESI wallet check.", updated)
    return updated

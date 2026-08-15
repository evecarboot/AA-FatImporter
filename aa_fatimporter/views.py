import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import FormView, View

from aa_fatimporter.forms import FatUploadForm
from aa_fatimporter.models import (
    FatImportMemberResult,
    FatImportRecord,
    FatImportSettings,
    FatImportSummarySettings,
    FatMemberComplianceState,
    FatPayoutRecord,
)
from aa_fatimporter.services import (
    afat_available,
    apply_member_fat_rules,
    apply_strategic_weighting,
    compute_csv_hash,
    evaluate_corp_compliance_for_user,
    is_user_exempt,
    log_audit_event,
    parse_fat_csv,
    process_member_payout,
    resolve_group_action,
    resolve_user_for_character_name,
    send_import_summary_webhook,
    send_payout_summary_webhook,
    sync_member_group,
)


class FatLeaderboardView(UserPassesTestMixin, View):
    def test_func(self):
        return (
            self.request.user.is_authenticated
            and self.request.user.has_perm("aa_fatimporter.basic_access")
        )

    def get(self, request):
        settings = FatImportSettings.objects.first()
        summary_settings = FatImportSummarySettings.objects.first()
        latest = FatImportRecord.objects.select_related("settings").first()
        members = []
        if latest:
            members = list(latest.member_results.all())

        context = {
            "settings": settings,
            "summary_settings": summary_settings,
            "latest_import": latest,
            "members": sorted(members, key=lambda item: (-item.total_fats, item.character_name)),
            "title": getattr(summary_settings or settings, "summary_title", "FAT Leaderboard"),
        }
        return render(request, "aa_fatimporter/leaderboard.html", context)

    def post(self, request):
        """Export leaderboard as CSV."""
        if not request.POST.get("action") == "export":
            return redirect("aa_fatimporter:aa_fatimport_dashboard")

        latest = FatImportRecord.objects.select_related("settings").first()
        if not latest:
            messages.error(request, "No import data to export.")
            return redirect("aa_fatimporter:aa_fatimport_dashboard")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="fat_leaderboard_{latest.imported_at:%Y%m%d}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Character", "Total FATs", "Alliance Action", "Corp Action", "Below Minimum", "Above Remove"])
        for member in latest.member_results.all().order_by("-total_fats", "character_name"):
            writer.writerow([
                member.character_name,
                member.total_fats,
                member.alliance_action,
                member.corp_action,
                member.below_alliance_minimum,
                member.above_remove_threshold,
            ])
        return response


class FatTrendsView(UserPassesTestMixin, View):
    def test_func(self):
        return (
            self.request.user.is_authenticated
            and self.request.user.has_perm("aa_fatimporter.basic_access")
        )

    def get(self, request):
        settings = FatImportSettings.objects.first()
        summary_settings = FatImportSummarySettings.objects.first()
        imports = list(
            FatImportRecord.objects.order_by("-imported_at")[:20]
        )

        import_history = []
        for record in reversed(imports):
            member_results = list(record.member_results.all())
            below_count = sum(1 for m in member_results if m.below_alliance_minimum)
            above_remove = sum(1 for m in member_results if m.above_remove_threshold)
            compliant = len(member_results) - below_count
            import_history.append({
                "date": record.imported_at.strftime("%Y-%m-%d %H:%M"),
                "total_members": record.total_members,
                "compliant": compliant,
                "below_minimum": below_count,
                "above_remove": above_remove,
                "required_fats": record.required_fats,
            })

        member_trends = {}
        for record in imports:
            for result in record.member_results.all():
                name = result.character_name
                if name not in member_trends:
                    member_trends[name] = []
                member_trends[name].append({
                    "date": record.imported_at.strftime("%Y-%m-%d"),
                    "fats": result.total_fats,
                })

        context = {
            "settings": settings,
            "summary_settings": summary_settings,
            "import_history": import_history,
            "member_trends": member_trends,
            "title": "FAT Trends",
        }
        return render(request, "aa_fatimporter/trends.html", context)


class FatWhatIfView(UserPassesTestMixin, View):
    """Threshold what-if simulator: show impact of changing thresholds on the latest import."""

    def test_func(self):
        return (
            self.request.user.is_authenticated
            and self.request.user.has_perm("aa_fatimporter.basic_access")
        )

    def get(self, request):
        settings = FatImportSettings.objects.first()
        latest = FatImportRecord.objects.select_related("settings").first()
        if not latest:
            return render(request, "aa_fatimporter/whatif.html", {
                "title": "What-If Simulator",
                "settings": settings,
                "results": None,
            })

        # Use current settings as defaults, allow query param overrides
        alliance_required = int(request.GET.get("alliance_required", getattr(settings, "alliance_required_fats_per_90_days", 10)))
        alliance_remove = int(request.GET.get("alliance_remove", getattr(settings, "alliance_remove_above_fats", 15)))
        corp_required = int(request.GET.get("corp_required", getattr(settings, "corp_required_fats_per_90_days", 10)))
        corp_remove = int(request.GET.get("corp_remove", getattr(settings, "corp_remove_group_above_fats", 15)))
        multiplier = request.GET.get("multiplier", getattr(settings, "strategic_fat_multiplier", 1))

        members = list(latest.member_results.all())
        results = []
        alliance_add = alliance_remove_count = corp_add = corp_remove_count = compliant = 0

        for m in members:
            strategic_fats = getattr(m, "strategic_fats", 0)
            weighted_total = apply_strategic_weighting(m.total_fats, strategic_fats, multiplier) if multiplier != 1 else m.total_fats

            a_action = "none"
            if weighted_total > alliance_remove:
                a_action = "remove"
                alliance_remove_count += 1
            elif weighted_total < alliance_required:
                a_action = "add"
                alliance_add += 1
            else:
                compliant += 1

            c_action = "none"
            if weighted_total > corp_remove:
                c_action = "remove"
                corp_remove_count += 1
            elif weighted_total < corp_required:
                c_action = "add"
                corp_add += 1

            results.append({
                "character_name": m.character_name,
                "total_fats": m.total_fats,
                "weighted_total": weighted_total,
                "alliance_action": a_action,
                "corp_action": c_action,
            })

        results.sort(key=lambda r: (-r["total_fats"], r["character_name"]))

        context = {
            "title": "What-If Simulator",
            "settings": settings,
            "results": results,
            "alliance_required": alliance_required,
            "alliance_remove": alliance_remove,
            "corp_required": corp_required,
            "corp_remove": corp_remove,
            "multiplier": multiplier,
            "alliance_add": alliance_add,
            "alliance_remove_count": alliance_remove_count,
            "corp_add": corp_add,
            "corp_remove_count": corp_remove_count,
            "compliant": compliant,
            "total_members": len(results),
        }
        return render(request, "aa_fatimporter/whatif.html", context)


class FatImportView(UserPassesTestMixin, FormView):
    template_name = "aa_fatimporter/upload.html"
    form_class = FatUploadForm
    success_url = "/"

    def test_func(self):
        return (
            self.request.user.is_authenticated
            and self.request.user.has_perm("aa_fatimporter.basic_access")
        )

    def _build_preview(self, records, settings):
        """Evaluate the import without applying any changes. Returns a preview dict."""
        result = apply_member_fat_rules(records, settings)
        member_details = result.get("members", {})
        corp_enforcement_active = afat_available()
        strategic_multiplier = getattr(settings, "strategic_fat_multiplier", 1)
        alliance_required = getattr(settings, "alliance_required_fats_per_90_days", 0)
        alliance_remove_above = getattr(settings, "alliance_remove_above_fats", None)

        preview_members = []
        alliance_add_count = 0
        alliance_remove_count = 0
        corp_add_count = 0
        corp_remove_count = 0
        exempt_count = 0
        total_payout = 0

        for name, details in member_details.items():
            user = resolve_user_for_character_name(name)
            total_fats = details.get("total_fats", 0)
            strategic_fats = details.get("strategic_fats", 0)

            # Apply strategic weighting for alliance action in preview
            weighted_total = apply_strategic_weighting(total_fats, strategic_fats, strategic_multiplier) if strategic_multiplier != 1 else total_fats
            alliance_action = resolve_group_action(weighted_total, alliance_required, alliance_remove_above)

            corp_action = "skipped"

            alliance_exempt = is_user_exempt(user, "alliance") if user else False
            corp_exempt = is_user_exempt(user, "corp") if user else False

            if alliance_exempt:
                if alliance_action in ("add", "remove"):
                    alliance_action = "exempt"

            if user and corp_enforcement_active:
                _, corp_action = evaluate_corp_compliance_for_user(user, settings)
                if corp_exempt and corp_action in ("add", "remove"):
                    corp_action = "exempt"

            if alliance_action == "add":
                alliance_add_count += 1
            elif alliance_action == "remove":
                alliance_remove_count += 1
            if corp_action == "add":
                corp_add_count += 1
            elif corp_action == "remove":
                corp_remove_count += 1
            if alliance_exempt or corp_exempt:
                exempt_count += 1

            if getattr(settings, "payout_enabled", False):
                from decimal import Decimal
                from aa_fatimporter.services import calculate_member_payout
                strategic_rate = getattr(settings, "reward_for_strategic_fat", 0) or 0
                regular_rate = getattr(settings, "reward_for_regular_fat", 0) or 0
                amount = calculate_member_payout(
                    details.get("strategic_fats", 0),
                    details.get("regular_fats", 0),
                    strategic_rate,
                    regular_rate,
                )
                if amount > 0:
                    total_payout += amount

            preview_members.append({
                "character_name": name,
                "total_fats": total_fats,
                "strategic_fats": details.get("strategic_fats", 0),
                "regular_fats": details.get("regular_fats", 0),
                "alliance_action": alliance_action,
                "corp_action": corp_action,
                "alliance_exempt": alliance_exempt,
                "corp_exempt": corp_exempt,
                "user_resolved": user is not None,
            })

        return {
            "total_records": len(records),
            "total_members": len(member_details),
            "members": sorted(preview_members, key=lambda m: (-m["total_fats"], m["character_name"])),
            "alliance_add_count": alliance_add_count,
            "alliance_remove_count": alliance_remove_count,
            "corp_add_count": corp_add_count,
            "corp_remove_count": corp_remove_count,
            "exempt_count": exempt_count,
            "total_payout": total_payout,
            "corp_enforcement_active": corp_enforcement_active,
        }

    def form_valid(self, form):
        uploaded_file = form.cleaned_data["csv_file"]
        data = uploaded_file.read().decode("utf-8", errors="replace")

        settings = FatImportSettings.objects.first()
        if settings is None:
            settings = FatImportSettings.objects.create(name="main")

        # Use configurable CSV column names (#4)
        records = parse_fat_csv(
            data,
            column_character=getattr(settings, "csv_column_character", "Main Character"),
            column_total_fats=getattr(settings, "csv_column_total_fats", "Total FATs"),
            column_strategic_fats=getattr(settings, "csv_column_strategic_fats", "Strategic & Deployment"),
        )

        if not records:
            messages.error(self.request, "No valid FAT rows were found in the uploaded CSV.")
            return redirect(self.success_url)

        # Dry-run preview mode
        if self.request.POST.get("action") == "preview":
            preview = self._build_preview(records, settings)
            # Store CSV data in session so the confirm step can retrieve it
            # without requiring a re-upload.
            self.request.session["aa_fatimporter_preview_csv"] = data
            return render(
                self.request,
                "aa_fatimporter/preview.html",
                {
                    "preview": preview,
                    "settings": settings,
                    "title": "Import Preview",
                },
            )

        # Confirm from preview: retrieve CSV from session
        if self.request.POST.get("action") == "confirm":
            session_data = self.request.session.pop("aa_fatimporter_preview_csv", "")
            if not session_data:
                messages.error(self.request, "Preview data expired. Please re-upload the CSV.")
                return redirect(self.success_url)
            records = parse_fat_csv(
                session_data,
                column_character=getattr(settings, "csv_column_character", "Main Character"),
                column_total_fats=getattr(settings, "csv_column_total_fats", "Total FATs"),
                column_strategic_fats=getattr(settings, "csv_column_strategic_fats", "Strategic & Deployment"),
            )
            if not records:
                messages.error(self.request, "No valid FAT rows found in the preview data.")
                return redirect(self.success_url)
            return self._apply_import(records, settings, session_data)

        return self._apply_import(records, settings, data)

    @transaction.atomic
    def _apply_import(self, records, settings, csv_data=""):
        result = apply_member_fat_rules(records, settings)
        member_details = result.get("members", {})

        # Multi-import deduplication (#14)
        csv_hash = compute_csv_hash(csv_data)
        if csv_hash:
            recent_dup = FatImportRecord.objects.filter(
                csv_hash=csv_hash,
                imported_at__gte=timezone.now() - timedelta(hours=24),
            ).first()
            if recent_dup:
                messages.warning(
                    self.request,
                    f"Warning: this CSV appears to be a duplicate of an import from {recent_dup.imported_at:%Y-%m-%d %H:%M}. Applying anyway.",
                )
                log_audit_event("duplicate_warning", user=self.request.user,
                                details=f"Duplicate of import {recent_dup.pk}")

        import_record = FatImportRecord.objects.create(
            settings=settings,
            total_records=len(records),
            total_members=len(member_details),
            required_fats=getattr(settings, "alliance_required_fats_per_90_days", 0),
            remove_above_fats=getattr(settings, "alliance_remove_above_fats", 0),
            csv_hash=csv_hash,
            imported_by=self.request.user,
        )

        log_audit_event("import", user=self.request.user,
                        details=f"Imported {len(records)} records, {len(member_details)} members")

        payouts = []
        corp_enforcement_active = afat_available()
        grace_period = getattr(settings, "grace_period_imports", 0)
        strategic_multiplier = getattr(settings, "strategic_fat_multiplier", 1)
        notify_enabled = getattr(settings, "notify_on_group_change", False)

        for name, details in member_details.items():
            user = resolve_user_for_character_name(name)
            total_fats = details.get("total_fats", 0)
            strategic_fats = details.get("strategic_fats", 0)

            # Apply strategic FAT weighting for compliance (#10)
            weighted_total = apply_strategic_weighting(total_fats, strategic_fats, strategic_multiplier) if strategic_multiplier != 1 else total_fats

            below_minimum = weighted_total < getattr(settings, "alliance_required_fats_per_90_days", 0)
            above_remove = weighted_total > getattr(settings, "alliance_remove_above_fats", 0)

            corp_action = "skipped"
            corp_total = 0
            if user is not None and corp_enforcement_active:
                corp_total, corp_action = evaluate_corp_compliance_for_user(user, settings)

            # Check exemptions
            alliance_exempt = is_user_exempt(user, "alliance") if user else False
            corp_exempt = is_user_exempt(user, "corp") if user else False

            # Grace period check (#7) — compute final alliance action before storing
            alliance_action_final = details.get("alliance_action", "none")
            if user is not None and grace_period > 0 and alliance_action_final == "remove" and not alliance_exempt:
                state, _ = FatMemberComplianceState.objects.get_or_create(
                    user=user, character_name=name,
                    defaults={"alliance_consecutive_below": 0},
                )
                if below_minimum:
                    state.alliance_consecutive_below += 1
                    if state.alliance_first_below_at is None:
                        state.alliance_first_below_at = timezone.now()
                else:
                    state.alliance_consecutive_below = 0
                    state.alliance_first_below_at = None
                state.save()

                if state.alliance_consecutive_below <= grace_period:
                    alliance_action_final = "none"
                    log_audit_event("group_skip_grace", user=user, character_name=name,
                                    details=f"Grace period: {state.alliance_consecutive_below}/{grace_period}")

            # Store the member result with the FINAL action (after grace period)
            FatImportMemberResult.objects.create(
                record=import_record,
                character_name=name,
                total_fats=total_fats,
                strategic_fats=strategic_fats,
                regular_fats=details.get("regular_fats", 0),
                alliance_action=alliance_action_final,
                corp_action=corp_action,
                below_alliance_minimum=below_minimum,
                above_remove_threshold=above_remove,
            )

            if user is None:
                continue

            alliance_group = getattr(settings, "alliance_group", None)
            corp_group = getattr(settings, "corp_group", None)

            if getattr(settings, "same_group_for_both", False):
                alliance_group = alliance_group or corp_group
                corp_group = alliance_group

            if (
                getattr(settings, "alliance_group_enabled", False)
                and alliance_group is not None
                and not alliance_exempt
                and alliance_action_final != "none"
            ):
                alliance_threshold = getattr(settings, "alliance_required_fats_per_90_days", 0)
                alliance_remove_above = getattr(settings, "alliance_remove_above_fats", None)
                sync_member_group(
                    user,
                    weighted_total,
                    alliance_threshold,
                    group_id=alliance_group.pk,
                    remove_above_fats=alliance_remove_above,
                    notify_scope="alliance",
                    notify=notify_enabled,
                )
            elif alliance_exempt:
                log_audit_event("group_skip_exempt", user=user, character_name=name,
                                details="Alliance exemption active")

            if (
                getattr(settings, "corp_group_enabled", False)
                and corp_group is not None
                and corp_action != "skipped"
                and not corp_exempt
            ):
                corp_threshold = getattr(settings, "corp_required_fats_per_90_days", 0)
                corp_remove_above = getattr(settings, "corp_remove_group_above_fats", None)
                sync_member_group(
                    user,
                    corp_total,
                    corp_threshold,
                    group_id=corp_group.pk,
                    remove_above_fats=corp_remove_above,
                    notify_scope="corp",
                    notify=notify_enabled,
                )
            elif corp_exempt:
                log_audit_event("group_skip_exempt", user=user, character_name=name,
                                details="Corp exemption active")

            payout = process_member_payout(
                user,
                name,
                details.get("strategic_fats", 0),
                details.get("regular_fats", 0),
                total_fats,
                settings,
                import_record,
            )
            if payout is not None:
                payouts.append(payout)
                log_audit_event("payout_created", user=user, character_name=name,
                                details=f"{payout.amount} ISK via {payout.payout_method}")

        settings.last_imported_at = timezone.now()
        settings.save(update_fields=["last_imported_at"])

        send_import_summary_webhook(records)
        if payouts:
            send_payout_summary_webhook(payouts)

        summary_note = "" if corp_enforcement_active else " (corp enforcement skipped: AFAT not installed)"
        messages.success(
            self.request,
            f"Imported {len(records)} FAT entries and evaluated {len(member_details)} member totals"
            f"{summary_note}.",
        )
        return redirect(self.success_url)


class FatLeaderboardAPI(UserPassesTestMixin, View):
    """Simple JSON API endpoint for the latest leaderboard data (#13)."""

    def test_func(self):
        return (
            self.request.user.is_authenticated
            and self.request.user.has_perm("aa_fatimporter.basic_access")
        )

    def get(self, request):
        latest = FatImportRecord.objects.select_related("settings").first()
        if not latest:
            return JsonResponse({"results": [], "import_date": None})

        members = []
        for m in latest.member_results.all().order_by("-total_fats", "character_name"):
            members.append({
                "character_name": m.character_name,
                "total_fats": m.total_fats,
                "alliance_action": m.alliance_action,
                "corp_action": m.corp_action,
                "below_alliance_minimum": m.below_alliance_minimum,
                "above_remove_threshold": m.above_remove_threshold,
            })

        return JsonResponse({
            "import_date": latest.imported_at.isoformat(),
            "total_members": latest.total_members,
            "required_fats": latest.required_fats,
            "results": members,
        })


class FatPayoutsAPI(UserPassesTestMixin, View):
    """Simple JSON API endpoint for payout records (#13)."""

    def test_func(self):
        return (
            self.request.user.is_authenticated
            and self.request.user.has_perm("aa_fatimporter.basic_access")
        )

    def get(self, request):
        status_filter = request.GET.get("status", "")
        queryset = FatPayoutRecord.objects.select_related("user", "record").order_by("-created_at")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        payouts = []
        for p in queryset[:100]:
            payouts.append({
                "character_name": p.character_name,
                "amount": str(p.amount),
                "payout_method": p.payout_method,
                "status": p.status,
                "payout_ref": p.payout_ref,
                "created_at": p.created_at.isoformat(),
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            })

        return JsonResponse({"payouts": payouts, "count": len(payouts)})

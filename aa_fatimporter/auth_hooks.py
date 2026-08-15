"""Hook into Alliance Auth"""

from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class FatImportMenuItem(MenuItemHook):
    """Menu item for the FAT import view."""

    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("Import FATs"),
            "fas fa-file-csv fa-fw",
            "aa_fatimporter:aa_fatimport_upload",
            navactive=["aa_fatimporter:"],
            order=1001,
        )

    def render(self, request):
        if request.user.has_perm("aa_fatimporter.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


class FatDashboardMenuItem(MenuItemHook):
    """Menu item for the FAT dashboard/leaderboard view."""

    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("FAT Dashboard"),
            "fas fa-chart-line fa-fw",
            "aa_fatimporter:aa_fatimport_dashboard",
            navactive=["aa_fatimporter:"],
            order=1002,
        )

    def render(self, request):
        if request.user.has_perm("aa_fatimporter.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


class FatTrendsMenuItem(MenuItemHook):
    """Menu item for the FAT trends view."""

    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("FAT Trends"),
            "fas fa-chart-bar fa-fw",
            "aa_fatimporter:aa_fatimport_trends",
            navactive=["aa_fatimporter:"],
            order=1003,
        )

    def render(self, request):
        if request.user.has_perm("aa_fatimporter.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


class FatWhatIfMenuItem(MenuItemHook):
    """Menu item for the FAT what-if simulator view."""

    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("FAT What-If"),
            "fas fa-sliders-h fa-fw",
            "aa_fatimporter:aa_fatimport_whatif",
            navactive=["aa_fatimporter:"],
            order=1004,
        )

    def render(self, request):
        if request.user.has_perm("aa_fatimporter.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_import_menu():
    return FatImportMenuItem()


@hooks.register("menu_item_hook")
def register_dashboard_menu():
    return FatDashboardMenuItem()


@hooks.register("menu_item_hook")
def register_trends_menu():
    return FatTrendsMenuItem()


@hooks.register("menu_item_hook")
def register_whatif_menu():
    return FatWhatIfMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "aa_fatimporter", r"^fat-importer/")

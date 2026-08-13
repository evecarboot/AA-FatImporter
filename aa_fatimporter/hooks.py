from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class FatImportMenuItem(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("Import FATs"),
            "fas fa-file-csv",
            "aa_fatimport_upload",
            navactive=["aa_fatimport_upload"],
        )


class FatDashboardMenuItem(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            _("FAT Dashboard"),
            "fas fa-chart-line",
            "aa_fatimport_dashboard",
            navactive=["aa_fatimport_dashboard"],
        )


@hooks.register("menu_item_hook")
def register_import_menu():
    return FatImportMenuItem()


@hooks.register("menu_item_hook")
def register_dashboard_menu():
    return FatDashboardMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "aa_fatimporter", r"^fat-importer/")
from allianceauth import hooks
from allianceauth.menu.hooks import MenuItemHook


@hooks.register("menu_item_hook")
def register_menu():
    return [
        MenuItemHook(
            "Import FATs",
            "fas fa-file-csv",
            "aa_fatimport_upload",
            100,
            ["aa_fatimport_upload"],
        ),
        MenuItemHook(
            "FAT Dashboard",
            "fas fa-chart-line",
            "aa_fatimport_dashboard",
            101,
            ["aa_fatimport_dashboard"],
        ),
    ]
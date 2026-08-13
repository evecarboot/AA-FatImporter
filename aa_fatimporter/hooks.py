from allianceauth import hooks
from allianceauth.menu.hooks import MenuItemHook


@hooks.register("menu_item_hook")
def register_menu():
    return [
        MenuItemHook(
            text="Import FATs",
            classes="fas fa-file-csv",
            url_name="aa_fatimport_upload",
            order=100,
        ),
        MenuItemHook(
            text="FAT Dashboard",
            classes="fas fa-chart-line",
            url_name="aa_fatimport_dashboard",
            order=101,
        ),
    ]
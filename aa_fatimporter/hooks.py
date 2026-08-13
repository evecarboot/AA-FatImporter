from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook


@hooks.register("menu_item_hook")
def register_menu():
    admin_access = ["auth.change_user"]
    return [
        MenuItemHook(
            text="Import FATs",
            classes="fas fa-file-csv",
            url_name="aa_fatimport_upload",
            navactive=["aa_fatimport_upload"],
            access_perms=admin_access,
        ),
        MenuItemHook(
            text="FAT Dashboard",
            classes="fas fa-chart-line",
            url_name="aa_fatimport_dashboard",
            navactive=["aa_fatimport_dashboard"],
            access_perms=admin_access,
        ),
    ]

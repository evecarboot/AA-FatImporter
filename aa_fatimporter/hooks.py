from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook


@hooks.register("menu_item_hook")
def register_menu():
    return MenuItemHook(
        text="FAT Importer",
        classes="fas fa-file-csv",
        url_name="aa_fatimport_upload",
        navactive=["aa_fatimport_upload"],
    )

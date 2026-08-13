@hooks.register("menu_item_hook")
def register_import_menu():
    return MenuItemHook(
        "Import FATs",
        "fas fa-file-csv",
        "aa_fatimport_upload",
        100,
        ["aa_fatimport_upload"],
    )


@hooks.register("menu_item_hook")
def register_dashboard_menu():
    return MenuItemHook(
        "FAT Dashboard",
        "fas fa-chart-line",
        "aa_fatimport_dashboard",
        101,
        ["aa_fatimport_dashboard"],
    )
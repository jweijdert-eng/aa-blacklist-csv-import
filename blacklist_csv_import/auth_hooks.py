from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class BlacklistCsvImportMenu(MenuItemHook):
    def __init__(self):
        MenuItemHook.__init__(
            self,
            "Blacklist CSV Import",
            "fas fa-file-import fa-fw",
            "blacklist_csv_import:upload",
            navactive=[
                "blacklist_csv_import:upload",
                "blacklist_csv_import:add_names",
            ],
        )

    def render(self, request):
        if request.user.has_perm("blacklist.add_new_eve_notes"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return BlacklistCsvImportMenu()


@hooks.register("url_hook")
def register_url():
    return UrlHook(urls, "blacklist_csv_import", r"^blacklist-csv-import/")

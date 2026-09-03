"""Ophalen van de gedeelde blacklist-Google-sheet.

De sheet is publiek te lezen, dus de CSV-export-URL is genoeg -- geen
Google-API-sleutel nodig. De opgehaalde tekst gaat door dezelfde parser als een
handmatige upload (`parser.read_rows_from_text`).

De URL is te overschrijven in `local.py` met::

    BLACKLIST_CSV_IMPORT_SHEET_URL = "https://docs.google.com/spreadsheets/d/.../edit?gid=0"
"""

import logging
import re

import requests

logger = logging.getLogger(__name__)

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1nKtgFowqPEI7I1qzuXnKIFtNZurpKw7K5mZmCY4AHFg/edit?gid=0#gid=0"
)
# Naam van het document en van het tabblad waar gid=0 naar wijst; puur om op de
# pagina te tonen welke lijst er gecontroleerd wordt.
DEFAULT_SHEET_NAME = "2026 WinterCo (EN) Blacklist/Banned"
DEFAULT_SHEET_TAB = "The List"

USER_AGENT = "aa-blacklist-csv-import (contact: j.weijdert@gmail.com)"
REQUEST_TIMEOUT = 60

_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
_GID_RE = re.compile(r"[#&?]gid=(\d+)")


class SheetError(Exception):
    """De sheet kon niet opgehaald worden (netwerk, rechten, verkeerde URL)."""


def sheet_url():
    from django.conf import settings

    return getattr(settings, "BLACKLIST_CSV_IMPORT_SHEET_URL", DEFAULT_SHEET_URL)


def sheet_name():
    from django.conf import settings

    return getattr(settings, "BLACKLIST_CSV_IMPORT_SHEET_NAME", DEFAULT_SHEET_NAME)


def sheet_tab():
    from django.conf import settings

    return getattr(settings, "BLACKLIST_CSV_IMPORT_SHEET_TAB", DEFAULT_SHEET_TAB)


def csv_export_url(url=None):
    """Zet een gewone sheet-URL om naar de CSV-export-URL van dat tabblad."""
    url = url or sheet_url()
    match = _SHEET_ID_RE.search(url)
    if not match:
        raise SheetError(f"Geen geldige Google-sheet-URL: {url}")
    gid_match = _GID_RE.search(url)
    gid = gid_match.group(1) if gid_match else "0"
    return (
        f"https://docs.google.com/spreadsheets/d/{match.group(1)}"
        f"/export?format=csv&gid={gid}"
    )


def fetch_sheet_text(url=None):
    """Haal de sheet op als CSV-tekst.

    Gooit `SheetError` bij netwerkproblemen of als Google iets anders dan CSV
    teruggeeft (meestal een inlogpagina: de sheet staat dan niet op 'iedereen
    met de link mag lezen').
    """
    export_url = csv_export_url(url)
    try:
        response = requests.get(
            export_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        logger.warning("Sheet ophalen mislukt: %s", exc)
        raise SheetError(f"Sheet ophalen mislukt: {exc}") from exc

    if response.status_code != 200:
        raise SheetError(
            f"Google gaf status {response.status_code} terug voor {export_url}"
        )

    content_type = (response.headers.get("Content-Type") or "").lower()
    if "text/csv" not in content_type:
        raise SheetError(
            "Google gaf geen CSV terug (content-type: "
            f"{content_type or 'onbekend'}). Staat de sheet op 'iedereen met "
            "de link mag lezen'?"
        )

    response.encoding = "utf-8-sig"
    return response.text

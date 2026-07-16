"""ESI-lookups voor het toevoegen van namen aan de blacklist.

Gebaseerd op de officiële ESI-API (https://esi.evetech.net). Stuurt altijd
een duidelijke User-Agent en Content-Type header mee (voorkomt 403-fouten)
en respecteert de ESI error-rate-limit headers (X-Esi-Error-Limit-Remain /
-Reset) plus Retry-After bij 420/429/5xx responses.
"""

import logging
import random
import time

import requests

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
USER_AGENT = "aa-blacklist-csv-import/0.3.0 (contact: j.weijdert@gmail.com)"

MAX_NAMES_PER_REQUEST = 500  # limiet van /universe/ids/
MAX_IDS_PER_REQUEST = 1000
MAX_RETRIES = 4
REQUEST_TIMEOUT = 20
ERROR_LIMIT_SAFETY_THRESHOLD = 5


def _session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    )
    return session


def _respect_error_limit(response):
    """Pauzeer preventief als de ESI error-limit bijna bereikt is."""
    remain = response.headers.get("X-Esi-Error-Limit-Remain")
    reset = response.headers.get("X-Esi-Error-Limit-Reset")
    if remain is None or reset is None:
        return
    try:
        if int(remain) <= ERROR_LIMIT_SAFETY_THRESHOLD:
            wait = max(int(reset), 1)
            logger.warning("ESI error-limit bijna bereikt, wacht %ds.", wait)
            time.sleep(wait)
    except ValueError:
        pass


def _post(session, path, payload):
    """POST naar ESI met retries, backoff en rate-limit-afhandeling."""
    backoff = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.post(
                f"{ESI_BASE}{path}",
                params={"datasource": "tranquility"},
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.warning(
                "Netwerkfout bij ESI %s (poging %d/%d): %s",
                path, attempt, MAX_RETRIES, exc,
            )
            time.sleep(backoff)
            backoff *= 2
            continue

        if response.status_code == 200:
            _respect_error_limit(response)
            try:
                return response.json()
            except ValueError:
                logger.error("ESI %s gaf ongeldige JSON terug.", path)
                return None

        if response.status_code in (420, 429):
            retry_after = response.headers.get("Retry-After")
            _respect_error_limit(response)
            wait = float(retry_after) if retry_after else backoff
            logger.warning(
                "ESI rate limit (status %d), wacht %.1fs (poging %d/%d).",
                response.status_code, wait, attempt, MAX_RETRIES,
            )
            time.sleep(wait)
            backoff *= 2
            continue

        if response.status_code == 403 or 500 <= response.status_code < 600:
            wait = backoff + random.uniform(0, 0.5)
            logger.warning(
                "ESI %s status %d, wacht %.1fs (poging %d/%d).",
                path, response.status_code, wait, attempt, MAX_RETRIES,
            )
            time.sleep(wait)
            backoff *= 2
            continue

        logger.error(
            "ESI %s gaf status %d: %s",
            path, response.status_code, response.text[:200],
        )
        return None

    logger.error("Max. retries bereikt voor ESI %s.", path)
    return None


def _chunked(items, size):
    return [items[i : i + size] for i in range(0, len(items), size)]


def lookup_names(names):
    """Zoekt namen (karakters, corporaties, allianties) op via ESI.

    Geeft (records, not_found) terug. Elk record bevat: eve_id, eve_name,
    eve_catagory, corporation_id/name en alliance_id/name (voor karakters
    via /characters/affiliation/, voor corps/allianties de eigen naam).
    """
    session = _session()
    records = []
    matched_lower = set()

    for batch in _chunked(names, MAX_NAMES_PER_REQUEST):
        data = _post(session, "/universe/ids/", batch)
        if not data:
            continue
        for key, category in (
            ("characters", "character"),
            ("corporations", "corporation"),
            ("alliances", "alliance"),
        ):
            for entry in data.get(key) or []:
                if "id" not in entry or "name" not in entry:
                    continue
                records.append(
                    {
                        "eve_id": entry["id"],
                        "eve_name": entry["name"],
                        "eve_catagory": category,
                    }
                )
                matched_lower.add(entry["name"].lower())

    not_found = [n for n in names if n.lower() not in matched_lower]

    # Corp/alliantie van gevonden karakters opzoeken.
    char_ids = [r["eve_id"] for r in records if r["eve_catagory"] == "character"]
    affiliations = {}
    for batch in _chunked(char_ids, MAX_IDS_PER_REQUEST):
        data = _post(session, "/characters/affiliation/", batch)
        for entry in data or []:
            affiliations[entry.get("character_id")] = entry

    # Namen van de corp-/alliantie-IDs ophalen.
    id_set = set()
    for aff in affiliations.values():
        if aff.get("corporation_id"):
            id_set.add(aff["corporation_id"])
        if aff.get("alliance_id"):
            id_set.add(aff["alliance_id"])
    id_names = {}
    for batch in _chunked(sorted(id_set), MAX_IDS_PER_REQUEST):
        data = _post(session, "/universe/names/", batch)
        for entry in data or []:
            id_names[entry.get("id")] = entry.get("name")

    for rec in records:
        if rec["eve_catagory"] == "character":
            aff = affiliations.get(rec["eve_id"]) or {}
            corp_id = aff.get("corporation_id")
            alliance_id = aff.get("alliance_id")
            rec["corporation_id"] = corp_id
            rec["corporation_name"] = id_names.get(corp_id)
            rec["alliance_id"] = alliance_id
            rec["alliance_name"] = id_names.get(alliance_id)
        elif rec["eve_catagory"] == "corporation":
            rec["corporation_id"] = rec["eve_id"]
            rec["corporation_name"] = rec["eve_name"]
            rec["alliance_id"] = None
            rec["alliance_name"] = None
        else:  # alliance
            rec["corporation_id"] = None
            rec["corporation_name"] = None
            rec["alliance_id"] = rec["eve_id"]
            rec["alliance_name"] = rec["eve_name"]

    return records, not_found

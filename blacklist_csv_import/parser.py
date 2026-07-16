"""Gedeelde CSV-parselogica voor de blacklist-import."""

import csv
import io
import re

CATEGORY_MAP = {
    "characters": "character",
    "corporations": "corporation",
    "alliances": "alliance",
    "character": "character",
    "corporation": "corporation",
    "alliance": "alliance",
}

OLD_ID_RE = re.compile(r"old id (\d+)")


def _int(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def read_rows_from_text(text):
    """Parse CSV-tekst met automatische delimiter-detectie (komma/puntkomma)."""
    # eventuele BOM verwijderen
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    reader.fieldnames = [(fn or "").strip() for fn in reader.fieldnames or []]
    return list(reader)


def read_rows_from_file(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return read_rows_from_text(f.read())


def build_records(rows, default_added_by="CSV import"):
    """Zet CSV-rijen om naar EveNote-velden. Geeft (records, skipped) terug."""
    records = []
    skipped = []
    for row in rows:
        name = (row.get("Main") or "").strip()
        if not name:
            continue

        esi_type = (row.get("esi_type") or "").strip().lower()
        esi_id = _int(row.get("esi_id"))
        zkill_note = (row.get("zkill_note") or "").strip()

        category = CATEGORY_MAP.get(esi_type)
        eve_id = esi_id if (esi_id and category) else None

        if eve_id is None:
            m = OLD_ID_RE.search(zkill_note)
            if m:
                eve_id = int(m.group(1))
                category = "character"

        if eve_id is None or category is None:
            skipped.append(name)
            continue

        reason = (row.get("Reason") or "").strip()
        if zkill_note:
            reason = (reason + " | " if reason else "") + f"[import note: {zkill_note}]"

        records.append({
            "eve_id": eve_id,
            "eve_name": name[:500],
            "eve_catagory": category,
            "blacklisted": True,
            "added_by": ((row.get("Added By") or "").strip() or default_added_by)[:500],
            "reason": reason,
            "corporation_id": _int(row.get("Corporation id")),
            "corporation_name": ((row.get("Corporation name") or "").strip() or None),
            "alliance_id": _int(row.get("Alliance id")),
            "alliance_name": ((row.get("Alliance name") or "").strip() or None),
        })
    return records, skipped


def import_records(records):
    """Sla records op als EveNote. Geeft (created, existing) terug.

    Koppelt tijdens de import de post_save-signal los zodat er geen storm aan
    celery-taken ontstaat (zelfde aanpak als de toolbox-import van de plugin).
    """
    from django.db.models.signals import post_save

    from blacklist.models import EveNote
    from blacklist.signals import process_eve_note

    post_save.disconnect(process_eve_note, sender=EveNote)
    created = 0
    existing = 0
    try:
        for rec in records:
            if EveNote.objects.filter(
                eve_id=rec["eve_id"],
                eve_catagory=rec["eve_catagory"],
                reason=rec["reason"],
            ).exists():
                existing += 1
                continue
            EveNote.objects.create(**rec)
            created += 1
    finally:
        post_save.connect(process_eve_note, sender=EveNote)
    return created, existing

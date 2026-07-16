"""Gedeelde CSV-parselogica voor de blacklist-import.

Accepteert zowel de vóórbewerkte CSV (met een `esi_id`/`eve_id`-kolom) als de
rúwe Google-sheet-export (instructieregels bovenaan, meertalige koppen zoals
`Main/主角色`, en alléén namen). Rijen zonder ID worden live via ESI opgezocht.
"""

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
ALT_SPLIT_RE = re.compile(r"[;,\r\n]+")

# Genormaliseerde kolomnaam -> canonieke sleutel.
_HEADER_ALIASES = {
    "main": "main",
    "eve_name": "main",
    "name": "main",
    "reason": "reason",
    "esi_type": "esi_type",
    "type": "esi_type",
    "category": "esi_type",
    "esi_id": "esi_id",
    "eve_id": "esi_id",
    "id": "esi_id",
    "zkill_note": "zkill_note",
    "zkill note": "zkill_note",
    "corporation id": "corporation_id",
    "corp id": "corporation_id",
    "corporation name": "corporation_name",
    "corp name": "corporation_name",
    "alliance id": "alliance_id",
    "alliance name": "alliance_name",
}


def _int(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _norm_header(header):
    """Normaliseer een kolomkop: eerste regel, deel vóór '/', lowercased."""
    header = (header or "").split("\n")[0].split("/")[0]
    return re.sub(r"\s+", " ", header.strip().lower())


def _canonical(header):
    """Map een (meertalige) kolomkop naar een canonieke sleutel."""
    norm = _norm_header(header)
    if norm in _HEADER_ALIASES:
        return _HEADER_ALIASES[norm]
    if norm.startswith("added by"):
        return "added_by"
    if norm.startswith("known alt") or norm in ("known_alts", "alts", "alt"):
        return "__alt__"
    return norm


def _find_header_row(rows):
    """Vind de index van de echte kop-rij: de eerste rij met een 'Main'-kolom.

    De Google-sheet heeft een paar instructie-/rommelregels bovenaan; die slaan
    we zo automatisch over. Valt terug op rij 0 als er geen 'Main' te vinden is.
    """
    for i, row in enumerate(rows[:15]):
        if any(_canonical(cell) == "main" for cell in row):
            return i
    return 0


def read_rows_from_text(text):
    """Parse CSV-tekst naar een lijst dicts met canonieke sleutels.

    - detecteert de delimiter (komma/puntkomma) automatisch;
    - slaat instructie-/koprommel bovenaan de sheet automatisch over;
    - normaliseert kolomnamen (`Main/主角色` -> ``main``, `eve_id`/`esi_id` -> ``esi_id``);
    - verzamelt alle `known alt`-kolommen in een lijst onder ``known_alts``.
    """
    if text.startswith("﻿"):
        text = text.lstrip("﻿")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    all_rows = list(csv.reader(io.StringIO(text), dialect=dialect))
    if not all_rows:
        return []

    header_i = _find_header_row(all_rows)
    keys = [_canonical(cell) for cell in all_rows[header_i]]

    rows = []
    for raw in all_rows[header_i + 1:]:
        row = {}
        alts = []
        for key, value in zip(keys, raw):
            if key == "__alt__":
                value = (value or "").strip()
                if value:
                    alts.extend(a.strip() for a in ALT_SPLIT_RE.split(value) if a.strip())
            elif key and key not in row:
                row[key] = value
        row["known_alts"] = alts
        rows.append(row)
    return rows


def read_rows_from_file(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return read_rows_from_text(f.read())


def build_records(rows, default_added_by="Dutch Legions", resolve=False):
    """Zet rijen om naar EveNote-velden.

    Geeft ``(records, skipped, not_found)`` terug:
    - rijen met een geldig ID/categorie (of een oud ID in de zkill-note) gaan
      direct mee;
    - rijen met alleen een naam worden, als ``resolve=True``, in één batch live
      via ESI opgezocht; wat ESI niet vindt komt in ``not_found``;
    - zonder ``resolve`` belanden ID-loze rijen in ``skipped``.

    Elk record kan een ``known_alts``-lijst dragen die bij de import als comment
    op de note wordt gezet.
    """
    records = []
    skipped = []
    pending = []  # (naam, basis-record) die nog een ESI-lookup nodig hebben

    for row in rows:
        name = (row.get("main") or "").strip()
        if not name:
            continue

        reason = (row.get("reason") or "").strip()
        zkill_note = (row.get("zkill_note") or "").strip()
        if zkill_note:
            reason = (reason + " | " if reason else "") + f"[import note: {zkill_note}]"

        base = {
            "eve_name": name[:500],
            "blacklisted": True,
            "added_by": ((row.get("added_by") or "").strip() or default_added_by)[:500],
            "reason": reason,
            "known_alts": row.get("known_alts") or [],
        }

        esi_type = (row.get("esi_type") or "").strip().lower()
        esi_id = _int(row.get("esi_id"))
        category = CATEGORY_MAP.get(esi_type)
        eve_id = esi_id if (esi_id and category) else None

        # Recycled character: pak het oude ID uit de zkill-note.
        if eve_id is None and zkill_note:
            m = OLD_ID_RE.search(zkill_note)
            if m:
                eve_id = int(m.group(1))
                category = "character"

        if eve_id is not None and category is not None:
            record = dict(base)
            record.update({
                "eve_id": eve_id,
                "eve_catagory": category,
                "corporation_id": _int(row.get("corporation_id")),
                "corporation_name": ((row.get("corporation_name") or "").strip() or None),
                "alliance_id": _int(row.get("alliance_id")),
                "alliance_name": ((row.get("alliance_name") or "").strip() or None),
            })
            records.append(record)
        elif resolve:
            pending.append((name, base))
        else:
            skipped.append(name)

    not_found = []
    if resolve and pending:
        from .esi import lookup_names

        found, _missing = lookup_names([name for name, _ in pending])
        found_map = {rec["eve_name"].lower(): rec for rec in found}
        for name, base in pending:
            match = found_map.get(name.lower())
            if match:
                record = dict(base)
                record.update({
                    "eve_id": match["eve_id"],
                    "eve_catagory": match["eve_catagory"],
                    "corporation_id": match.get("corporation_id"),
                    "corporation_name": match.get("corporation_name"),
                    "alliance_id": match.get("alliance_id"),
                    "alliance_name": match.get("alliance_name"),
                })
                records.append(record)
            else:
                not_found.append(name)

    return records, skipped, not_found


def existing_keys(records):
    """Geef de set ``(eve_id, eve_catagory)`` terug die al als EveNote bestaat.

    Eén bulk-query op alle IDs uit ``records`` — zo weet je vóór de import
    (ook in dry-run) welke namen al op de blacklist staan.
    """
    from blacklist.models import EveNote

    ids = {r["eve_id"] for r in records if r.get("eve_id") is not None}
    if not ids:
        return set()
    return set(
        EveNote.objects.filter(eve_id__in=ids).values_list("eve_id", "eve_catagory")
    )


def split_new_existing(records):
    """Splits ``records`` in (nieuw, bestaat_al) op ID+categorie-niveau.

    Ontdubbelt óók binnen dezelfde lijst (dezelfde naam twee keer in het bestand
    telt maar één keer als 'nieuw').
    """
    present = existing_keys(records)
    seen = set()
    new, already = [], []
    for rec in records:
        key = (rec.get("eve_id"), rec.get("eve_catagory"))
        if key in present or key in seen:
            already.append(rec)
        else:
            seen.add(key)
            new.append(rec)
    return new, already


def import_records(records):
    """Sla records op als EveNote (+ bekende alts als comment).

    Geeft ``(created, existing)`` terug. Een character/ID dat al op de blacklist
    staat wordt overgeslagen (dubbelcheck op ``eve_id`` + ``eve_catagory``,
    ongeacht de reden), net als dubbele rijen binnen hetzelfde bestand. Koppelt
    tijdens de import de post_save-signal los zodat er geen storm aan
    celery-taken ontstaat (zelfde aanpak als de toolbox-import van de plugin).
    """
    from django.db.models.signals import post_save

    from blacklist.models import EveNote, EveNoteComment
    from blacklist.signals import process_eve_note

    new, already = split_new_existing(records)

    post_save.disconnect(process_eve_note, sender=EveNote)
    created = 0
    try:
        for rec in new:
            alts = rec.get("known_alts") or []
            fields = {k: v for k, v in rec.items() if k != "known_alts"}
            note = EveNote.objects.create(**fields)
            created += 1
            if alts:
                EveNoteComment.objects.create(
                    eve_note=note,
                    added_by=fields["added_by"],
                    comment="Bekende alts: " + "; ".join(alts[:100]),
                )
    finally:
        post_save.connect(process_eve_note, sender=EveNote)
    return created, len(already)

import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from .esi import lookup_names
from .forms import AddNamesForm, UploadCsvForm
from .parser import (
    build_records,
    import_records,
    read_rows_from_text,
    split_new_existing,
)


@login_required
@permission_required("blacklist.add_new_eve_notes")
def upload_csv(request):
    result = None
    form = UploadCsvForm()

    if request.method == "POST":
        form = UploadCsvForm(request.POST, request.FILES)
        if form.is_valid():
            raw = request.FILES["csv_file"].read()
            text = raw.decode("utf-8-sig", errors="replace")
            rows = read_rows_from_text(text)

            if rows and "main" not in rows[0]:
                messages.error(
                    request,
                    "Geen naam-kolom gevonden. Verwacht een kolom 'Main' of "
                    "'eve_name'. Gebruik de rauwe blacklist-sheet of de "
                    f"bewerkte CSV. Gevonden kolommen: {', '.join(k for k in rows[0] if k != 'known_alts')}",
                )
            else:
                added_by = form.cleaned_data["added_by"] or "Dutch Legions"
                records, skipped, not_found = build_records(rows, added_by, resolve=True)

                if form.cleaned_data["dry_run"]:
                    new, already = split_new_existing(records)
                    result = {
                        "dry_run": True,
                        "ready": len(records),
                        "skipped": skipped,
                        "not_found": not_found,
                        "new_count": len(new),
                        "already": [r["eve_name"] for r in already],
                        "created": None,
                        "existing": None,
                    }
                    messages.info(
                        request,
                        f"Dry-run: {len(new)} nieuw, {len(already)} staan al op de "
                        f"blacklist, {len(not_found)} niet gevonden via ESI. Er is "
                        "niets opgeslagen.",
                    )
                else:
                    created, existing = import_records(records)
                    result = {
                        "dry_run": False,
                        "ready": len(records),
                        "skipped": skipped,
                        "not_found": not_found,
                        "created": created,
                        "existing": existing,
                    }
                    messages.success(
                        request,
                        f"Import klaar: {created} aangemaakt, {existing} bestonden al, "
                        f"{len(not_found)} niet gevonden via ESI.",
                    )

    return render(
        request,
        "blacklist_csv_import/upload.html",
        {"form": form, "result": result},
    )


@login_required
@permission_required("blacklist.add_new_eve_notes")
def add_names(request):
    result = None
    form = AddNamesForm()

    if request.method == "POST":
        form = AddNamesForm(request.POST)
        if form.is_valid():
            names = []
            seen = set()
            # splits op nieuwe regels, komma's en puntkomma's
            for part in re.split(r"[\n\r,;]+", form.cleaned_data["names"]):
                name = part.strip()
                if name and name.lower() not in seen:
                    seen.add(name.lower())
                    names.append(name)

            if not names:
                messages.error(request, "Geen namen opgegeven.")
            else:
                found, not_found = lookup_names(names)
                reason = (form.cleaned_data["reason"] or "").strip()
                added_by = form.cleaned_data["added_by"] or "Dutch Legions"

                records = []
                for rec in found:
                    record = dict(rec)
                    record["eve_name"] = record["eve_name"][:500]
                    record.update(
                        {
                            "blacklisted": True,
                            "added_by": added_by[:500],
                            "reason": reason,
                        }
                    )
                    records.append(record)

                if form.cleaned_data["dry_run"]:
                    new, already = split_new_existing(records)
                    already_names = {r["eve_id"] for r in already}
                    for rec in records:
                        rec["already"] = rec["eve_id"] in already_names
                    result = {
                        "dry_run": True,
                        "found": records,
                        "not_found": not_found,
                        "new_count": len(new),
                        "already": [r["eve_name"] for r in already],
                        "created": None,
                        "existing": None,
                    }
                    messages.info(
                        request,
                        f"Dry-run: {len(new)} nieuw, {len(already)} staan al op de "
                        f"blacklist, {len(not_found)} niet gevonden. Er is niets opgeslagen.",
                    )
                else:
                    created, existing = import_records(records)
                    result = {
                        "dry_run": False,
                        "found": records,
                        "not_found": not_found,
                        "created": created,
                        "existing": existing,
                    }
                    messages.success(
                        request,
                        f"Klaar: {created} toegevoegd, {existing} bestonden al, "
                        f"{len(not_found)} niet gevonden.",
                    )

    return render(
        request,
        "blacklist_csv_import/add_names.html",
        {"form": form, "result": result},
    )

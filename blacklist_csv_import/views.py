import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from .esi import lookup_names
from .forms import AddNamesForm, UploadCsvForm
from .parser import build_records, import_records, read_rows_from_text


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

            if rows and "esi_id" not in rows[0]:
                messages.error(
                    request,
                    "Kolom 'esi_id' niet gevonden in dit bestand. Gebruik de "
                    "CSV met de kolommen esi_type/esi_id/Corporation id/... "
                    f"Gevonden kolommen: {', '.join(rows[0].keys())}",
                )
            else:
                added_by = form.cleaned_data["added_by"] or "Dutch Legions"
                records, skipped = build_records(rows, added_by)

                if form.cleaned_data["dry_run"]:
                    result = {
                        "dry_run": True,
                        "ready": len(records),
                        "skipped": skipped,
                        "created": None,
                        "existing": None,
                    }
                    messages.info(
                        request,
                        f"Dry-run: {len(records)} rijen klaar voor import, "
                        f"{len(skipped)} overgeslagen. Er is niets opgeslagen.",
                    )
                else:
                    created, existing = import_records(records)
                    result = {
                        "dry_run": False,
                        "ready": len(records),
                        "skipped": skipped,
                        "created": created,
                        "existing": existing,
                    }
                    messages.success(
                        request,
                        f"Import klaar: {created} aangemaakt, "
                        f"{existing} bestonden al, {len(skipped)} overgeslagen.",
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
                    result = {
                        "dry_run": True,
                        "found": records,
                        "not_found": not_found,
                        "created": None,
                        "existing": None,
                    }
                    messages.info(
                        request,
                        f"Dry-run: {len(records)} van {len(names)} namen gevonden, "
                        f"{len(not_found)} niet gevonden. Er is niets opgeslagen.",
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

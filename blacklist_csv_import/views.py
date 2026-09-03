import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from .esi import lookup_names
from .forms import AddNamesForm, SheetSyncForm, UploadCsvForm
from .parser import (
    build_records,
    import_records,
    read_rows_from_text,
    split_new_existing,
    split_rows_by_known_name,
)
from .sheet import (
    SheetError,
    csv_export_url,
    fetch_sheet_text,
    sheet_name,
    sheet_tab,
    sheet_url,
)


def _process_rows(rows, added_by, dry_run, skip_known_names=False):
    """Rijen -> records -> dry-run-overzicht of echte import.

    Gedeeld door de CSV-upload en de sheet-controle: beide leveren dezelfde
    rijen op, dus ook hetzelfde resultaat-woordenboek voor de templates.

    Met ``skip_known_names`` gaan namen die al als EveNote bestaan er meteen
    uit, nog vóór de ESI-lookup -- dat scheelt bij de sheet (1500+ rijen) ruim
    een minuut wachten.
    """
    known_names = []
    if skip_known_names:
        rows, known_names = split_rows_by_known_name(rows)

    records, skipped, not_found = build_records(rows, added_by, resolve=True)
    new, already = split_new_existing(records)
    result = {
        "dry_run": dry_run,
        "ready": len(records),
        "skipped": skipped,
        "not_found": not_found,
        "new": new,
        "new_count": len(new),
        "already": known_names + [r["eve_name"] for r in already],
        "created": None,
        "existing": None,
    }
    if not dry_run:
        created, existing = import_records(records)
        result["created"] = created
        # de vooraf gefilterde namen stonden er ook al op
        result["existing"] = existing + len(known_names)
    return result


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
                result = _process_rows(rows, added_by, form.cleaned_data["dry_run"])

                if result["dry_run"]:
                    messages.info(
                        request,
                        f"Dry-run: {result['new_count']} nieuw, "
                        f"{len(result['already'])} staan al op de blacklist, "
                        f"{len(result['not_found'])} niet gevonden via ESI. Er is "
                        "niets opgeslagen.",
                    )
                else:
                    messages.success(
                        request,
                        f"Import klaar: {result['created']} aangemaakt, "
                        f"{result['existing']} bestonden al, "
                        f"{len(result['not_found'])} niet gevonden via ESI.",
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
                        "already": known_names + [r["eve_name"] for r in already],
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


@login_required
@permission_required("blacklist.add_new_eve_notes")
def sheet(request):
    """Haalt de gedeelde Google-sheet op en kijkt of er namen bij zijn gekomen.

    Knop 'Controleren' draait altijd als dry-run; pas met 'Toevoegen' worden de
    nieuwe namen echt weggeschreven.
    """
    result = None
    form = SheetSyncForm()

    if request.method == "POST":
        form = SheetSyncForm(request.POST)
        if form.is_valid():
            added_by = form.cleaned_data["added_by"] or "Dutch Legions"
            dry_run = request.POST.get("action") != "import"
            try:
                text = fetch_sheet_text()
            except SheetError as exc:
                messages.error(request, str(exc))
            else:
                rows = read_rows_from_text(text)
                if not rows or "main" not in rows[0]:
                    messages.error(
                        request,
                        "Geen naam-kolom ('Main') in de sheet gevonden - is het "
                        "tabblad of de kop-rij veranderd?",
                    )
                else:
                    result = _process_rows(
                        rows, added_by, dry_run, skip_known_names=True
                    )
                    result["rows"] = len(rows)
                    if dry_run:
                        if result["new_count"]:
                            messages.info(
                                request,
                                f"{result['new_count']} nieuwe naam/namen in de sheet "
                                f"({len(result['already'])} stonden er al op). Er is "
                                "nog niets opgeslagen.",
                            )
                        else:
                            messages.success(
                                request,
                                "Geen nieuwe namen: de blacklist is bij met de sheet.",
                            )
                    else:
                        messages.success(
                            request,
                            f"{result['created']} toegevoegd, {result['existing']} "
                            f"stonden er al op, {len(result['not_found'])} niet "
                            "gevonden via ESI.",
                        )

    try:
        export_url = csv_export_url()
    except SheetError:
        export_url = None

    return render(
        request,
        "blacklist_csv_import/sheet.html",
        {
            "form": form,
            "result": result,
            "sheet_url": sheet_url(),
            "sheet_name": sheet_name(),
            "sheet_tab": sheet_tab(),
            "export_url": export_url,
        },
    )

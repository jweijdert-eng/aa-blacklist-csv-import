from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from .forms import UploadCsvForm
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

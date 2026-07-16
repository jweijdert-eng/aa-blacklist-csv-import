from django import forms


class UploadCsvForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV-bestand",
        help_text="Bijv. Blacklist_met_character_ids.csv (komma of puntkomma, UTF-8)",
    )
    added_by = forms.CharField(
        label="Standaard 'added by'",
        required=False,
        initial="CSV import",
        help_text="Wordt gebruikt voor rijen zonder eigen 'Added By'-waarde",
    )
    dry_run = forms.BooleanField(
        label="Dry-run (alleen controleren, niets opslaan)",
        required=False,
        initial=True,
    )

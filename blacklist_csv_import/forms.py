from django import forms


class UploadCsvForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV-bestand",
        help_text="Bijv. Blacklist_met_character_ids.csv (komma of puntkomma, UTF-8)",
    )
    added_by = forms.CharField(
        label="Standaard 'added by'",
        required=False,
        initial="Dutch Legions",
        help_text="Wordt gebruikt voor rijen zonder eigen 'Added By'-waarde",
    )
    dry_run = forms.BooleanField(
        label="Dry-run (alleen controleren, niets opslaan)",
        required=False,
        initial=True,
    )


class AddNamesForm(forms.Form):
    names = forms.CharField(
        label="Namen",
        widget=forms.Textarea(attrs={"rows": 8}),
        help_text="Eén naam per regel — karakters, corporaties of allianties",
    )
    reason = forms.CharField(
        label="Reden",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Wordt bij alle opgegeven namen gezet",
    )
    added_by = forms.CharField(
        label="Added by",
        required=False,
        initial="Dutch Legions",
    )
    dry_run = forms.BooleanField(
        label="Dry-run (alleen controleren, niets opslaan)",
        required=False,
        initial=True,
    )

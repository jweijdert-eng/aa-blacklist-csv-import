"""Management-commando: importeer een blacklist-CSV in allianceauth-blacklist.

Gebruik:
    python manage.py blacklist_import_csv Blacklist_met_character_ids.csv
    python manage.py blacklist_import_csv lijst.csv --dry-run
    python manage.py blacklist_import_csv lijst.csv --added-by "j.weijdert"
"""

from django.core.management.base import BaseCommand, CommandError

from blacklist_csv_import.parser import build_records, import_records, read_rows_from_file


class Command(BaseCommand):
    help = "Importeer blacklist-entries uit een CSV-bestand in allianceauth-blacklist."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Pad naar het CSV-bestand")
        parser.add_argument(
            "--added-by",
            default="Dutch Legions",
            help="Naam voor 'added_by' als de CSV geen 'Added By'-waarde heeft",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Alleen tonen wat er zou gebeuren, niets opslaan",
        )

    def handle(self, *args, **options):
        path = options["csv_file"]
        try:
            rows = read_rows_from_file(path)
        except FileNotFoundError:
            raise CommandError(f"Bestand niet gevonden: {path}")

        if rows and "esi_id" not in rows[0]:
            raise CommandError(
                "Kolom 'esi_id' niet gevonden. Gebruik de nieuwste versie van "
                "de CSV (met kolommen esi_type/esi_id/Corporation id/...). "
                f"Gevonden kolommen: {', '.join(rows[0].keys())}"
            )

        records, skipped = build_records(rows, options["added_by"])
        self.stdout.write(
            f"{len(records)} rijen klaar voor import, {len(skipped)} overgeslagen (geen ID)."
        )
        if skipped:
            preview = ", ".join(skipped[:15])
            more = " ..." if len(skipped) > 15 else ""
            self.stdout.write(f"Overgeslagen: {preview}{more}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry-run: er is niets opgeslagen."))
            return

        created, existing = import_records(records)
        self.stdout.write(
            self.style.SUCCESS(f"Klaar: {created} aangemaakt, {existing} bestonden al.")
        )

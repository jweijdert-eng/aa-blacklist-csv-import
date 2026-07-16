# AA Blacklist CSV Import

Uitbreiding voor [allianceauth-blacklist](https://github.com/Solar-Helix-Independent-Transport/allianceauth-blacklist):
importeer blacklist-entries vanuit een CSV-bestand, via een uploadpagina in
Alliance Auth of via een management-commando.

## Installatie

1. Activeer je Alliance Auth virtualenv en installeer het wheel-bestand:

   ```
   pip install aa_blacklist_csv_import-0.1.0-py3-none-any.whl
   ```

2. Voeg `'blacklist_csv_import',` toe aan `INSTALLED_APPS` in
   `myauth/settings/local.py` (onder `'blacklist',`).

3. Herstart Alliance Auth (of je runserver).

Er zijn geen migraties nodig (de app heeft geen eigen database-modellen).

## Gebruik — webpagina

In het zijmenu verschijnt **Blacklist CSV Import** (zichtbaar voor iedereen met
de permissie `blacklist | add_new_eve_notes`). Upload daar je CSV:

- **Dry-run** staat standaard aan: je ziet eerst hoeveel rijen er geïmporteerd
  zouden worden zonder dat er iets wordt opgeslagen.
- Vink dry-run uit en klik opnieuw op Importeren om echt te importeren.
- Bestaande entries (zelfde ID, categorie en reden) worden overgeslagen, dus
  hetzelfde bestand nogmaals uploaden is veilig.

## Gebruik — command line

```
python manage.py blacklist_import_csv Blacklist_met_character_ids.csv
python manage.py blacklist_import_csv lijst.csv --dry-run
python manage.py blacklist_import_csv lijst.csv --added-by "naam"
```

## CSV-formaat

Verwachte kolommen (extra kolommen worden genegeerd):

| Kolom | Verplicht | Betekenis |
|---|---|---|
| `Main` | ja | Naam van karakter/corp/alliantie |
| `esi_type` | ja* | `characters`, `corporations` of `alliances` |
| `esi_id` | ja* | EVE ID (via ESI `universe/ids`) |
| `Added By` | nee | Wie de entry heeft toegevoegd |
| `Reason` | nee | Reden van blacklisting |
| `zkill_note` | nee | Notitie; voor recycled karakters wordt hier `old id <ID>` uit gelezen |
| `Corporation id` / `Corporation name` | nee | Huidige corporatie |
| `Alliance id` / `Alliance name` | nee | Huidige alliantie |

\* Rijen zonder `esi_id` maar met `old id <ID>` in `zkill_note` (recycled
karakters) worden als karakter geïmporteerd met dat oude ID.

Zowel komma- als puntkomma-gescheiden bestanden werken (dus ook CSV's die door
Excel opnieuw zijn opgeslagen), met of zonder UTF-8 BOM.

## Namen toevoegen (zonder CSV)

Naast de CSV-import heeft de plugin een pagina **Namen toevoegen**
(`/blacklist-csv-import/names/`): plak namen van karakters, corporaties of
allianties (een per regel), en de plugin zoekt de IDs, corporatie en
alliantie automatisch op via de EVE ESI-API (met nette User-Agent headers,
batching en rate-limit-afhandeling). Dry-run toont eerst een preview-tabel;
daarna kun je de namen definitief aan de blacklist toevoegen.

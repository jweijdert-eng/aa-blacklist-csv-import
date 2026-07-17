# AA Blacklist CSV Import

Uitbreiding voor [allianceauth-blacklist](https://github.com/Solar-Helix-Independent-Transport/allianceauth-blacklist):
importeer blacklist-entries vanuit een CSV/TSV, via een uploadpagina in Alliance
Auth of via een management-commando. Werkt zowel met de **rauwe Google-sheet**
(alleen namen) als met een al bewerkte CSV mét IDs.

## Features

- **Rauwe blacklist-sheet direct importeerbaar** — instructieregels bovenaan
  worden overgeslagen, meertalige/variant-kolomnamen (`Main/主角色`,
  `eve_id`/`esi_id`, `category`/`esi_type`) worden herkend, en namen zonder ID
  worden **live via ESI opgezocht** (nette User-Agent, batching en
  rate-limit-afhandeling). Een al bewerkte CSV mét `esi_id`/`eve_id` werkt ook
  (dan zonder ESI-calls).
- **Dubbelcheck op ID + categorie** — een character/corp/alliance die al op de
  blacklist staat wordt overgeslagen (ongeacht de reden), net als dubbele rijen
  in hetzelfde bestand. De dry-run toont vooraf hoeveel er **nieuw** zijn en
  hoeveel er **al op de blacklist** staan.
- **Bekende alts** — `known alt`-kolommen (ook meerdere per cel) worden als
  comment bij de entry gezet.
- **Namen toevoegen** — een aparte pagina om losse namen te plakken en via ESI
  op te zoeken.

## Installatie

1. Installeer in je Alliance Auth virtualenv:

   ```
   pip install git+https://github.com/jweijdert-eng/aa-blacklist-csv-import.git
   ```

2. Voeg `'blacklist_csv_import',` toe aan `INSTALLED_APPS` in
   `myauth/settings/local.py` (onder `'blacklist',`).

3. Herstart Alliance Auth (web + workers).

Er zijn geen migraties nodig (de app heeft geen eigen database-modellen).

## Gebruik — webpagina

In het zijmenu verschijnt **Blacklist CSV Import** (zichtbaar met de permissie
`blacklist | add_new_eve_notes`). Upload daar je CSV/TSV:

- **Dry-run** staat standaard aan: je ziet eerst hoeveel rijen nieuw zijn, hoeveel
  er al op de blacklist staan en hoeveel namen via ESI niet gevonden werden —
  zonder dat er iets wordt opgeslagen.
- Vink dry-run uit en klik opnieuw om echt te importeren.
- Hetzelfde bestand nogmaals uploaden is veilig (bestaande entries worden
  overgeslagen).

## Gebruik — command line

```
python manage.py blacklist_import_csv blacklist_sheet.csv
python manage.py blacklist_import_csv lijst.csv --dry-run
python manage.py blacklist_import_csv lijst.csv --added-by "naam"
python manage.py blacklist_import_csv lijst.csv --no-resolve   # namen niet via ESI opzoeken
```

## CSV-formaat

De plugin herkent zowel de rauwe sheet als een bewerkte CSV. Extra kolommen
worden genegeerd; kolomnamen zijn niet hoofdlettergevoelig en meertalige
varianten (bijv. `Main/主角色`) worden herkend.

| Kolom | Verplicht | Betekenis |
|---|---|---|
| `Main` (of `eve_name`) | ja | Naam van karakter/corp/alliantie |
| `esi_id` (of `eve_id`) | nee | EVE ID — ontbreekt 'ie, dan wordt 'm via ESI op de naam opgezocht |
| `esi_type` (of `category`) | nee | `characters`/`corporations`/`alliances` (enkelvoud mag ook) |
| `Added By` | nee | Wie de entry toevoegde (standaard "Dutch Legions") |
| `Reason` | nee | Reden van blacklisting |
| `zkill_note` | nee | Notitie; voor recycled karakters wordt hier `old id <ID>` uit gelezen |
| `Corporation id` / `Corporation name` | nee | Huidige corporatie |
| `Alliance id` / `Alliance name` | nee | Huidige alliantie |
| `known alt1/2/3` | nee | Bekende alts (ook meerdere per cel) → als comment op de entry |

Komma-, puntkomma- én tab-gescheiden bestanden werken (met of zonder UTF-8 BOM).

## Namen toevoegen (zonder CSV)

Naast de CSV-import heeft de plugin een pagina **Namen toevoegen**
(`/blacklist-csv-import/names/`): plak namen (een per regel of komma/puntkomma-
gescheiden), en de plugin zoekt de IDs, corporatie en alliantie op via ESI.
Dry-run toont eerst een preview met per naam of 'ie al op de blacklist staat.

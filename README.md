# AA FAT Importer

Alliance Auth plugin for importing alliance FAT exports, reviewing member FAT totals, and enforcing configurable Alliance Auth group rules for members below or above FAT thresholds.

## Features

- Imports the alliance FAT CSV export and ignores blank or invalid member rows.
- Aggregates duplicate character rows case-insensitively.
- Stores every import and its per-member results in the database.
- Shows the latest import as a ranked FAT leaderboard.
- Configures separate alliance and corp minimums and removal thresholds.
- Adds members below a configured minimum to an Alliance Auth group.
- Removes members above a configured removal threshold from an Alliance Auth group.
- Uses one shared group for both checks or separate alliance and corp groups.
- Resolves imported character names to Alliance Auth users before changing group membership.
- Optionally posts a Discord-friendly import summary through a webhook.
- Includes optional payout and invoice/webhook service helpers for integrations that use them.

## Requirements

- Python 3.10 or newer
- Alliance Auth 5.2 or newer, and below version 6
- A Django/Alliance Auth installation with database and static files configured

The package declares Alliance Auth as its only runtime dependency. The optional AFAT and invoice integrations are detected at runtime and do not need to be installed for CSV imports or group synchronization.

## Installation

Install the package from the repository using the Alliance Auth package installer or pip. Replace the placeholder URL with the URL of this repository:

```text
https://github.com/<your-github-user>/aa-fatimporter.git
```

For a local Alliance Auth checkout, the equivalent command is:

```bash
pip install -e path/to/aa-fatimporter
```

Add the app to the Alliance Auth project's `local.py`:

```python
INSTALLED_APPS += [
    "aa_fatimporter",
]
```

Run the database migration and collect static files:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

Restart the Alliance Auth service after installation so the app, hooks, and menu entries are loaded.

## Configuration

Configuration is available in Django admin under **FAT import settings**. The importer uses the first settings record, so keep one active record named `main` unless your deployment has a specific reason to manage records differently.

### FAT rules

The **Alliance FAT reporting** section controls the imported CSV totals:

- `Alliance required fats per 90 days`: members below this value receive the `add` action.
- `Alliance remove above fats`: members strictly above this value receive the `remove` action.
- `Alliance group`: the Alliance Auth group to update.
- `Alliance group enabled`: enables group synchronization for this check.

The **Corp FAT compliance** section provides an independent threshold and group configuration:

- `Corp required fats per 90 days`
- `Corp remove group above fats`
- `Corp group`
- `Corp group enabled`

The current upload workflow evaluates both checks from the imported member totals. The corp-side service layer also contains an optional AFAT lookup helper for integrations that supply corp FAT data separately, but no corp data-source selector is exposed in the current admin form.

### Shared group mode

Enable `Same group for both` when alliance and corp checks should target one group. In that mode, the alliance group is preferred; if it is empty, the configured corp group is used. Disable it and configure both group fields when the checks should manage separate groups.

### Discord import summaries

Configure **FAT import summary settings** in Django admin:

- `Webhook enabled`: enables summary delivery.
- `Webhook URL`: the Discord webhook endpoint.
- `Post import summary`: requests a summary after a successful import.
- `Summary title`: heading used in the generated message.
- `Dashboard top count`: number of members shown in the top and bottom sections.

The summary includes the number of processed members, members at or above the alliance minimum, members below that minimum, and ranked top/bottom lists. A webhook URL in the main FAT settings is also supported for backward-compatible configuration, but the dedicated summary settings should be preferred.

### Payout fields

The main settings model includes payout rates, payout method, payout enablement, and a webhook URL. The service layer provides payout calculation, invoice deduction, and webhook helpers. The current CSV upload view does not automatically calculate or issue payouts, invoices, or payout notifications; configure these fields only when another integration in your deployment consumes them.

## Using the plugin

Both pages require an authenticated Alliance Auth staff user. The plugin registers these menu items automatically:

| Page | Route | Purpose |
| --- | --- | --- |
| Import FATs | `/fat-importer/fat-import/` | Upload and process the latest alliance FAT CSV |
| FAT Dashboard | `/fat-importer/fat-leaderboard/` | View the latest ranked import and member status |

The route prefix comes from the Alliance Auth URL hook. If you include `aa_fatimporter.urls` manually instead of using the hook, the paths will be `/fat-import/` and `/fat-leaderboard/` under the prefix you choose.

### Import workflow

1. Export the alliance FAT report as CSV.
2. Open **Import FATs** and upload the file.
3. The importer parses member names and FAT totals, then aggregates duplicate names.
4. The import and member results are saved.
5. Configured group rules are applied to users matched by main-character name.
6. An optional Discord summary is sent.
7. Review the results on **FAT Dashboard**.

If the file contains no valid rows, the import is rejected with an error message and no import record is created.

## CSV format

The parser expects a header row containing at least these columns:

```csv
Main Character,Total FATs,Strategic & Deployment
Example Pilot,42,12
```

Additional columns from the normal alliance export are allowed and ignored. `Main Character` is required. Missing, blank, non-numeric, or `N/A` numeric values are treated as zero. Regular FATs are calculated as `Total FATs - Strategic & Deployment`.

## Group action rules

For each enabled group check, the importer applies these rules in order:

| Member total | Action |
| --- | --- |
| Greater than the removal threshold | Remove from the configured group |
| Less than the required minimum | Add to the configured group |
| At the minimum, or at the removal threshold | Leave unchanged |

The removal comparison is strictly greater than the configured value. A member exactly at either cutoff is therefore left unchanged. Members that cannot be matched to an Alliance Auth user are still recorded in the import results, but no group change is attempted.

## Data retained

The app stores:

- Import timestamp and source label
- Number of CSV records and unique members
- Threshold values used by the import
- Character name and total FATs for each member
- Alliance and corp actions returned by the rule evaluation
- Below-minimum and above-removal-threshold status flags

## Development

Create or activate a virtual environment, install the package and test dependencies used by your project, then run the test suite from the repository root:

```bash
python -m pytest
```

The tests cover CSV parsing, duplicate aggregation, threshold boundaries, group selection, summary formatting, AFAT fallback behavior, and the upload view's enabled-group handling.

## License

This project is distributed under the MIT License. See the project metadata in `pyproject.toml` for the package license declaration.

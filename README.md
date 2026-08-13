# AA FAT Importer

Alliance Auth plugin for tracking FAT compliance, importing alliance FAT CSV data, and syncing group membership based on 90-day FAT activity.

## What it does

- Imports alliance FAT CSV data as a reporting dataset
- Tracks alliance and corp FAT compliance separately
- Supports independent minimum FAT thresholds for alliance and corp checks
- Supports a single shared group option when both types should use the same group
- Automatically adds members to the configured group when they fall below the compliance threshold
- Removes members from the configured group when they exceed the remove-above threshold
- Supports AFAT as the corp-side FAT data source when available
- Stores each import and per-member results for later review
- Provides a FAT leaderboard dashboard for recent compliance status
- Sends a Discord summary webhook after CSV import when configured
- Supports optional payout configuration for FAT reward logic

## Install

### 1. Add the GitHub URL in Alliance Auth

Use this in the +git import / package installer:

```text
https://github.com/<your-github-user>/aa-fatimporter.git
```

Example:

```text
https://github.com/YourUsername/aa-fatimporter.git
```

### 2. Add the app to local.py

Add the app to your Alliance Auth project `local.py`:

```python
INSTALLED_APPS += [
    "afat",
    "aa_fatimporter",
]
```

Then include the plugin URLs in your main `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # existing patterns...
    path("", include("aa_fatimporter.urls")),
]
```

### 3. Run migrations and static collection

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 4. Configure in admin

In Django admin, configure:

- alliance FAT requirements
- corp FAT requirements
- alliance group
- corp group
- shared-group toggle if both checks should use one group
- import summary webhook settings
- optional payout configuration

### 5. Use the plugin

Open:

```text
/fat-import/
```

Upload the alliance FAT CSV export.

The dashboard is available at:

```text
/fat-leaderboard/
```

## Notes

- The alliance CSV is the main import/reporting source.
- Corp FAT compliance can use AFAT data as a separate source.
- The plugin is designed for Alliance Auth 5.x and uses the AA 5 hook and URL registration patterns.
- The import summary Discord webhook is configured via the dedicated FAT import summary settings model.
- The payout webhook is kept separate from the import summary webhook.

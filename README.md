# AA FAT Importer

Simple Alliance Auth plugin for importing alliance FAT CSVs and applying group-based FAT compliance rules.

## What it does

- Imports alliance FAT CSV data
- Aggregates totals per character
- Supports alliance and corp FAT thresholds
- Optionally uses the same AA group for both checks
- Adds or removes the configured group based on FAT counts
- Uses AFAT as the corp-side FAT source when available

## Install

### 1. Add the GitHub URL in Alliance Auth

Use this in the +git import / package installer:

```text
https://github.com/<your-github-user>/<your-repo-name>.git
```

Example:

```text
https://github.com/YourUsername/aa-fatimporter.git
```

### 2. Add the app to local.py

Copy this into your Alliance Auth project `local.py`:

```python
INSTALLED_APPS += [
    "afat",
    "aa_fatimporter",
]
```

Then include the app URLs in your main `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # existing patterns...
    path("", include("aa_fatimporter.urls")),
]
```

### 3. Run migrations

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 4. Configure in admin

Create your AA groups, then in the Django admin set:

- alliance FAT threshold
- corp FAT threshold
- alliance group
- corp group
- same-group toggle if you want one group for both checks

### 5. Use the page

Open:

```text
/fat-import/
```

Upload the alliance FAT CSV export.

## Notes

- The alliance CSV is used as a reporting/import source.
- Corp FAT compliance is intended to use AFAT as the corp-side source.
- Do not paste Python examples directly into `local.py` at module level; Django runs that file on startup.

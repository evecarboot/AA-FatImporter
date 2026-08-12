# AA FAT Importer

This project is a starting point for an Alliance Auth 5.x plugin that separates alliance FAT reporting from corp FAT compliance.

## Overview

The plugin is designed around two different data sources:

- Alliance FATs: imported manually from the alliance CSV export for reporting and alliance-level tracking
- Corp FATs: tracked from the corp-side AA data source, with AFAT as the intended corp FAT source of truth

This keeps the corp compliance rule separate from the alliance import and avoids using the alliance CSV as the corp threshold source.

## Features

- Import alliance FAT CSV files manually for alliance reporting
- Parse the export format from the supplied CSV sample
- Keep alliance FAT totals separate from corp FAT compliance checks
- Use AFAT as the corp FAT data source when available
- Support independent alliance and corp FAT threshold checks
- Add or remove an Alliance Auth group based on the configured fat threshold
- Allow the same AA group to be used for both alliance and corp compliance if the admin wants
- Calculate member ISK rewards from strategic and regular FAT counts
- Support payout modes:
  - member withdrawal via webhook notification
  - deduction from corp tax / invoice obligations

## Settings

Admins should configure:

- alliance_required_fats_per_90_days
- alliance_remove_above_fats
- alliance_group
- corp_required_fats_per_90_days
- corp_remove_group_above_fats
- corp_group
- same_group_for_both
- payout_enabled
- reward_for_strategic_fat
- reward_for_regular_fat
- payout_method
- webhook_url

The admin interface uses dropdowns rather than free-text group names. In practice:

- if `same_group_for_both` is checked, you select one group only
- if it is unchecked, you select an alliance group and a corp group separately

## Installation in Alliance Auth

This plugin needs to be installed into an existing Alliance Auth 5.x project and then wired into the Django app and URL config before it will work.

### 1. Install the package

Install it into the same Python environment as your Alliance Auth project.

Using GitHub +git import in AA:

```text
https://github.com/<your-github-user>/<your-repo-name>.git
```

Example:

```text
https://github.com/YourUsername/aa-fatimporter.git
```

Or manually in the project venv:

```bash
pip install git+https://github.com/YourUsername/aa-fatimporter.git
```

### 2. Add the app to the Django settings

Add the app to `INSTALLED_APPS` in your Alliance Auth project settings, usually in `local.py` or the app's settings module:

```python
INSTALLED_APPS += [
    "aa_fatimporter",
]
```

If you are also using AFAT as the corp FAT source, install and add it as well:

```python
INSTALLED_APPS += [
    "afat",
    "aa_fatimporter",
]
```

### 3. Include the plugin URLs

Add the app URLs into your main Alliance Auth `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # ... existing url patterns ...
    path("", include("aa_fatimporter.urls")),
]
```

This exposes the FAT import page at the route created by the app, which is currently:

```text
/fat-import/
```

### 4. Run migrations

From your Alliance Auth project root:

```bash
python manage.py migrate
```

### 5. Create the required AA groups

Create the groups you want to use for:

- alliance FAT compliance
- corp FAT compliance

Then open the plugin admin and select them from the dropdowns. This is safer than entering a raw group name manually.

### 6. Configure the plugin in the admin

Open the Alliance Auth admin and configure:

- alliance FAT threshold
- corp FAT threshold
- alliance group dropdown
- corp group dropdown
- same-group toggle
- payout settings
- payout method
- webhook URL

Recommended admin UX:

- check `same_group_for_both` if you want one group to handle both checks
- leave it unchecked if the alliance and corp checks should be different groups

### 7. Test the upload flow

Go to the FAT import URL in your dev AA install and upload a sample alliance FAT CSV.

## AFAT as corp FAT source

This plugin is designed to treat AFAT as the corp FAT source of truth for corp compliance checks. The alliance import remains a separate reporting dataset and is not used as the corp threshold source.

When AFAT is installed, the plugin can read corp FAT data from the AFAT app. If AFAT is not installed or unavailable, the source lookup safely resolves to zero instead of crashing.

## Invoice / payout integration notes

The payout logic is scaffolded and can hook into a corp tax/invoice plugin, but the exact invoice integration depends on the billing plugin actually installed in your Alliance Auth environment.

Before using payout mode in production, ensure the invoice plugin used by your corp is the one your Alliance Auth deployment actually exposes and that the expected invoice APIs or deduction hooks are available.

## GitHub +git import URL

Use this repository URL in the Alliance Auth +git import / plugin installer when installing directly from GitHub:

```text
https://github.com/<your-github-user>/<your-repo-name>.git
```

For example, if your repo is named `aa-fatimporter` and your GitHub username is `YourUsername`, use:

```text
https://github.com/YourUsername/aa-fatimporter.git
```

If you are using a private repo, make sure the install user has access to that repository.

## Example CSV structure

The alliance importer expects the same columns as the provided export, including:

- `Main Character`
- `Total FATs`
- `Strategic & Deployment`

## Payout model

To calculate rewards, the service uses the configured values per FAT type:

```python
amount = calculate_member_payout(
    strategic_fats=3,
    regular_fats=2,
    strategic_rate=500000,
    regular_rate=250000,
)
# => 2000000
```

This is a plugin scaffold: the invoice / tax integration must be implemented against the specific corp billing plugin used in your Alliance Auth install.

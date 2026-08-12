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
- alliance_compliance_group_name
- corp_required_fats_per_90_days
- corp_remove_group_above_fats
- corp_compliance_group_name
- same_group_for_both
- payout_enabled
- reward_for_strategic_fat
- reward_for_regular_fat
- payout_method
- webhook_url

## Installation in Alliance Auth

1. Place this app in your Alliance Auth project under a Python package path.
2. Add `aa_fatimporter` to `INSTALLED_APPS`.
3. Run migrations.
4. Import the alliance CSV from the admin or a custom web view for alliance reporting.
5. Configure the corp FAT source, corp target, and group names.
6. Configure the corp payout settings if payouts are enabled.

## AFAT as corp FAT source

This plugin is designed to treat AFAT as the corp FAT source of truth for corp compliance checks. The alliance import remains a separate reporting dataset and is not used as the corp threshold source.

When AFAT is installed, the plugin can read corp FAT data from the AFAT app. If AFAT is not installed or unavailable, the source lookup safely resolves to zero instead of crashing.

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

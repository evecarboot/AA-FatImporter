# AA FAT Importer

This project is a starting point for an Alliance Auth 5.x plugin that imports alliance FAT CSV exports, enforces corp FAT thresholds, and optionally pays members in ISK or credits their corp tax bills.

## Features

- Import alliance FAT CSV files manually from a corp admin view
- Parse the export format from the supplied CSV sample
- Compare each member against a per-90-day FAT target
- Automatically assign a configured corp role when a member falls below the target
- Calculate member ISK rewards from strategic and regular FAT counts
- Support payout modes:
  - member withdrawal via webhook notification
  - deduction from corp tax / invoice obligations

## Typical settings

Admins should configure:

- required_fats_per_90_days
- below_threshold_role_id
- payout_enabled
- reward_for_strategic_fat
- reward_for_regular_fat
- payout_method
- webhook_url

## Installation in Alliance Auth

1. Place this app in your Alliance Auth project under a Python package path.
2. Add `aa_fatimporter` to `INSTALLED_APPS`.
3. Run migrations.
4. Import the CSV from the admin or a custom web view.
5. Configure the corp threshold and payout settings.

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

The importer expects the same columns as the provided export, including:

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

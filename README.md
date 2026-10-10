# My-meta-ads

A small command-line tool for the Meta Marketing API (Python 3, standard library only).

## Setup

Set these in your environment's settings. Never commit them.

- `META_ACCESS_TOKEN`: your Meta access token (required)
- `META_AD_ACCOUNT_ID`: ad account ID (defaults to `1391867070674546`)
- `META_API_VERSION`: Graph API version (defaults to `v23.0`)

Your network settings must allow `graph.facebook.com`.

## Usage

```bash
python3 meta_ads.py account                      # account details
python3 meta_ads.py campaigns                    # list campaigns
python3 meta_ads.py insights --level campaign --date-preset last_7d
python3 meta_ads.py insights --level ad --since 2026-10-01 --until 2026-10-07 --csv report.csv

python3 meta_ads.py pause <id>                   # pause a campaign, ad set or ad
python3 meta_ads.py activate <id>                # turn it on (starts spending)
python3 meta_ads.py budget <id> --daily 50       # set daily budget to 50.00
python3 meta_ads.py create-campaign --name "Fall Sale" --objective OUTCOME_SALES --daily-budget 25
```

Commands that change things show the change and ask for confirmation (`--yes` skips the prompt).
New campaigns are always created paused. Budgets are in your account currency.
Making changes needs a token with the `ads_management` permission.

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
```

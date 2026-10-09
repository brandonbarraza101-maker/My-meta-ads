#!/usr/bin/env python3
"""Small CLI for the Meta Marketing API.

The access token is read from the META_ACCESS_TOKEN environment variable and
is never stored in this repo.

Examples:
    python3 meta_ads.py account
    python3 meta_ads.py campaigns
    python3 meta_ads.py insights --level campaign --date-preset last_7d
    python3 meta_ads.py insights --level ad --since 2026-10-01 --until 2026-10-07 --csv report.csv
"""

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = os.environ.get("META_API_VERSION", "v23.0")
AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID", "1391867070674546")
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

INSIGHT_FIELDS = [
    "campaign_name",
    "adset_name",
    "ad_name",
    "spend",
    "impressions",
    "reach",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "actions",
]


def account_path():
    acct = AD_ACCOUNT_ID
    return acct if acct.startswith("act_") else f"act_{acct}"


def get_token():
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        sys.exit("META_ACCESS_TOKEN is not set. Add it to your environment's secrets.")
    return token


def api_get(path, params=None):
    """GET a Graph API path, following pagination, and return all data rows."""
    params = dict(params or {})
    params["access_token"] = get_token()
    url = f"{BASE_URL}/{path}?{urllib.parse.urlencode(params)}"
    rows = []
    while url:
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as e:
            err = json.load(e).get("error", {})
            sys.exit(f"Meta API error {e.code}: {err.get('message', e.reason)}")
        if "data" not in body:
            return body
        rows.extend(body["data"])
        url = body.get("paging", {}).get("next")
    return rows


def cmd_account(_args):
    info = api_get(account_path(), {
        "fields": "name,account_status,currency,timezone_name,amount_spent",
    })
    print(json.dumps(info, indent=2))


def cmd_campaigns(_args):
    rows = api_get(f"{account_path()}/campaigns", {
        "fields": "id,name,status,objective,daily_budget,lifetime_budget",
        "limit": 100,
    })
    print_table(rows, ["id", "name", "status", "objective", "daily_budget", "lifetime_budget"])


def cmd_insights(args):
    params = {
        "level": args.level,
        "fields": ",".join(INSIGHT_FIELDS),
        "limit": 500,
    }
    if args.since and args.until:
        params["time_range"] = json.dumps({"since": args.since, "until": args.until})
    else:
        params["date_preset"] = args.date_preset
    rows = api_get(f"{account_path()}/insights", params)

    # Flatten the "actions" list into one column per action type.
    for row in rows:
        for action in row.pop("actions", []) or []:
            row[f"action:{action['action_type']}"] = action["value"]

    name_col = {"campaign": "campaign_name", "adset": "adset_name", "ad": "ad_name"}.get(args.level)
    cols = ([name_col] if name_col else []) + ["spend", "impressions", "clicks", "ctr", "cpc", "cpm"]
    print_table(rows, cols)

    if args.csv:
        all_cols = sorted({k for r in rows for k in r}, key=lambda k: (k.startswith("action:"), k))
        with open(args.csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_cols)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nWrote {len(rows)} rows to {args.csv}")


def print_table(rows, cols):
    if not rows:
        print("No results.")
        return
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    print("  ".join("-" * widths[c] for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("account", help="Show ad account details").set_defaults(func=cmd_account)
    sub.add_parser("campaigns", help="List campaigns").set_defaults(func=cmd_campaigns)

    p = sub.add_parser("insights", help="Show performance metrics")
    p.add_argument("--level", choices=["account", "campaign", "adset", "ad"], default="campaign")
    p.add_argument("--date-preset", default="last_7d",
                   help="e.g. today, yesterday, last_7d, last_30d, this_month")
    p.add_argument("--since", help="Start date YYYY-MM-DD (use with --until)")
    p.add_argument("--until", help="End date YYYY-MM-DD (use with --since)")
    p.add_argument("--csv", help="Also write all fields to this CSV file")
    p.set_defaults(func=cmd_insights)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

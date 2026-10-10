#!/usr/bin/env python3
"""Small CLI for the Meta Marketing API.

The access token is read from the META_ACCESS_TOKEN environment variable and
is never stored in this repo.

Examples:
    python3 meta_ads.py account
    python3 meta_ads.py campaigns
    python3 meta_ads.py insights --level campaign --date-preset last_7d
    python3 meta_ads.py insights --level ad --since 2026-10-01 --until 2026-10-07 --csv report.csv
    python3 meta_ads.py pause 120200000000000000
    python3 meta_ads.py activate 120200000000000000
    python3 meta_ads.py budget 120200000000000000 --daily 50
    python3 meta_ads.py create-campaign --name "Fall Sale" --objective OUTCOME_SALES --daily-budget 25

Commands that change things show the change and ask for confirmation first.
Pass --yes to skip the prompt. New campaigns are always created PAUSED.
Budgets are entered in your account currency (e.g. 50 = $50.00).
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


def api_request(url, data=None):
    try:
        with urllib.request.urlopen(url, data=data, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", {})
        except ValueError:
            err = {}
        msg = err.get("error_user_msg") or err.get("message") or e.reason
        sys.exit(f"Meta API error {e.code}: {msg}")


def api_get(path, params=None):
    """GET a Graph API path, following pagination, and return all data rows."""
    params = dict(params or {})
    params["access_token"] = get_token()
    url = f"{BASE_URL}/{path}?{urllib.parse.urlencode(params)}"
    rows = []
    while url:
        body = api_request(url)
        if "data" not in body:
            return body
        rows.extend(body["data"])
        url = body.get("paging", {}).get("next")
    return rows


def api_post(path, params):
    params = dict(params)
    params["access_token"] = get_token()
    data = urllib.parse.urlencode(params).encode()
    return api_request(f"{BASE_URL}/{path}", data=data)


def to_minor_units(amount):
    """Meta budgets are in the currency's minor unit (cents for USD)."""
    return str(round(float(amount) * 100))


def fmt_money(minor):
    return "-" if minor in (None, "", "0") else f"{int(minor) / 100:.2f}"


def confirm(args, message):
    print(message)
    if args.yes:
        return
    if input("Proceed? [y/N] ").strip().lower() not in ("y", "yes"):
        sys.exit("Cancelled.")


def get_object(obj_id):
    return api_get(obj_id, {"fields": "name,status,daily_budget,lifetime_budget"})


def set_status(args, status):
    obj = get_object(args.id)
    confirm(args, f"{obj.get('name', args.id)} ({args.id}): {obj.get('status')} -> {status}")
    api_post(args.id, {"status": status})
    print(f"Done. Status is now {get_object(args.id).get('status')}.")


def cmd_pause(args):
    set_status(args, "PAUSED")


def cmd_activate(args):
    set_status(args, "ACTIVE")


def cmd_budget(args):
    if (args.daily is None) == (args.lifetime is None):
        sys.exit("Give exactly one of --daily or --lifetime.")
    field = "daily_budget" if args.daily is not None else "lifetime_budget"
    new = to_minor_units(args.daily if args.daily is not None else args.lifetime)
    obj = get_object(args.id)
    confirm(args, f"{obj.get('name', args.id)} ({args.id}) {field}: "
                  f"{fmt_money(obj.get(field))} -> {fmt_money(new)}")
    api_post(args.id, {field: new})
    print(f"Done. {field} is now {fmt_money(get_object(args.id).get(field))}.")


def cmd_create_campaign(args):
    params = {
        "name": args.name,
        "objective": args.objective,
        "status": "PAUSED",
        "special_ad_categories": json.dumps(args.special_ad_category or []),
    }
    if args.daily_budget is not None:
        params["daily_budget"] = to_minor_units(args.daily_budget)
        params["bid_strategy"] = "LOWEST_COST_WITHOUT_CAP"
        budget_note = f"daily budget {fmt_money(params['daily_budget'])} (set at campaign level)"
    else:
        params["is_adset_budget_sharing_enabled"] = "false"
        budget_note = "no campaign budget (set budgets on ad sets)"
    confirm(args, f"Create PAUSED campaign '{args.name}', objective {args.objective}, {budget_note}")
    result = api_post(f"{account_path()}/campaigns", params)
    print(f"Created campaign {result.get('id')} (PAUSED). Use 'activate' to turn it on.")


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

    for name, func, help_text in [
        ("pause", cmd_pause, "Pause a campaign, ad set or ad"),
        ("activate", cmd_activate, "Turn on a campaign, ad set or ad (starts spending)"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("id", help="Campaign, ad set or ad ID")
        p.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
        p.set_defaults(func=func)

    p = sub.add_parser("budget", help="Change the budget of a campaign or ad set")
    p.add_argument("id", help="Campaign or ad set ID")
    p.add_argument("--daily", type=float, help="New daily budget, e.g. 50 for $50.00")
    p.add_argument("--lifetime", type=float, help="New lifetime budget")
    p.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    p.set_defaults(func=cmd_budget)

    p = sub.add_parser("create-campaign", help="Create a new campaign (always PAUSED)")
    p.add_argument("--name", required=True)
    p.add_argument("--objective", required=True, choices=[
        "OUTCOME_AWARENESS", "OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT",
        "OUTCOME_LEADS", "OUTCOME_APP_PROMOTION", "OUTCOME_SALES",
    ])
    p.add_argument("--daily-budget", type=float,
                   help="Campaign-level daily budget; omit to set budgets on ad sets instead")
    p.add_argument("--special-ad-category", action="append",
                   choices=["HOUSING", "EMPLOYMENT", "CREDIT", "ISSUES_ELECTIONS_POLITICS"],
                   help="Required if ads are about housing, jobs, credit or politics")
    p.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    p.set_defaults(func=cmd_create_campaign)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

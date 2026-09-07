# Ops Daily/Weekly Report — Apps Script setup

Ports `report.py` and `weekly_report.py` to Google Apps Script so they run on Apps
Script's own time-driven triggers instead of GitHub Actions. Logic (name matching,
table formatting, Redash queries, Slack posting) is a line-for-line port — outputs
should look identical to what the Python scripts were already posting.

## 1. Create the project

1. Go to [script.google.com](https://script.google.com) → **New project**.
2. Rename it something like `Ops Reports`.
3. Delete the default `Code.gs`, then add three script files (File → New → Script)
   with these exact names and paste in the matching content from this folder:
   - `DailyReport.gs`
   - `WeeklyReport.gs`
   - `Triggers.gs`

## 2. Set secrets (Script Properties)

Project Settings (gear icon) → **Script Properties** → add:

| Property | Value |
|---|---|
| `REDASH_API_KEY` | the account-level Redash key (same one `weekly_report.py` had hardcoded) |
| `SLACK_BOT_TOKEN` | the same Slack bot token the GitHub Actions secret used |

Neither script reads these from anywhere else — no `.env`, no hardcoding.

## 3. Grant the script access to the Bounty sheet (weekly report only)

`weekly_report.py` used a Google service-account JSON to read the Leave/WFH/Call
Log tabs. The Apps Script version drops that entirely — it opens the sheet with
`SpreadsheetApp.openById()` as *whoever the script runs as*, so:

- Make sure the Google account that owns this Apps Script project (or whichever
  account you set up trigger execution as) has at least **Viewer** access to the
  Bounty sheet: `1dUzxzF_6lY3lPdiHpmBg0mbas4q-Pp3ALE1Zx0WXHow`.
- No `GOOGLE_SERVICE_ACCOUNT_JSON` needed anymore.

## 4. Authorize and test

1. In the editor, select `runDailyReportTest` from the function dropdown and click
   **Run**. First run will prompt an OAuth consent screen (UrlFetch, Spreadsheets,
   script triggers) — approve it.
2. Check `#testing-sefali` in Slack for the redirected output, and compare against
   a recent real post from the Python version.
3. Do the same with `runWeeklyReportTest`.
4. **Important — verify network reachability first**: `redash.springworks.in` may
   only be reachable from specific networks (VPN/office IP allowlist). Apps Script
   executes from Google's own infrastructure, not from GitHub Actions' runners or
   your machine, so a Redash call that worked from GitHub Actions is not guaranteed
   to work from Apps Script. If `runDailyReportTest` fails on the Redash fetch step,
   that's almost certainly why — check with whoever manages Redash's network
   access about allowlisting Apps Script's egress, or about an alternative
   (e.g. a Redash API proxy) before relying on this for production runs.

## 5. Install the triggers

Once a test run posts a correct-looking message, run `setupTriggers()` once. It
installs:

- `runDailyReport` — daily, ~6:30 AM IST (matches the old `report.yml` cron)
- `runWeeklyReport` — Monday, ~9:00 AM IST (matches the old `weekly_report.yml` cron)

Apps Script time triggers land within a ~15 minute window of the requested time,
not to the exact minute.

Run `listTriggers()` any time to confirm what's installed, or `removeTriggers()`
to pull both out again.

## 6. Manual / override runs

From the Apps Script editor's function dropdown:

- `runDailyReport()` — yesterday (IST), real channels.
- `runDailyReportTest()` — yesterday (IST), redirected to `#testing-sefali`.
- `runWeeklyReport()` — last Mon–Sun, real channels (including the HR PIP thread).
- `runWeeklyReportTest()` — last Mon–Sun, redirected to `#testing-sefali`.

For a specific date/range instead of the default, call the underlying namespace
functions directly from the editor's "execute function" dialog isn't supported for
arguments — instead temporarily edit the trigger function, e.g.:

```js
function runDailyReport() {
  Daily.run('2026-09-05'); // override date
}
```

or for weekly:

```js
function runWeeklyReport() {
  Weekly.run('2026-08-25', '2026-08-31'); // override start/end
}
```

Revert back to the no-argument call afterward so the scheduled trigger goes back
to "yesterday" / "last week" behavior.

## Known carry-overs from the Python source

These are pre-existing quirks in `report.py`/`weekly_report.py`, kept as-is rather
than "fixed" during the port, since fixing them wasn't in scope:

- Daily and weekly maintain **separate, slightly different** `CHANNELS` member
  lists (e.g. weekly's CA+Initiation has 3 extra names daily doesn't). This is
  true in the Python source too.
- The day-boundary math treats a "day" as the raw UTC calendar day (not true IST
  midnight-to-midnight), to match Redash query 3045's existing behavior.
- The hardcoded `assignments[('QC', 'Manish Kumar Thakur')] = None` name-collision
  workaround in the weekly report is preserved.

import os
import time
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ── CONFIG ─────────────────────────────────────────────────────

_raw_token = os.environ["SLACK_BOT_TOKEN"]
SLACK_TOKEN = None  # resolved at runtime by resolve_slack_token()

REDASH_BASE = "https://redash.springworks.in"
REDASH_DS_ID = 5
# Account-level API key (same one used by the ops dashboard script) — needed for
# ad-hoc query execution (POST /api/query_results), not tied to any single saved query.
REDASH_API_KEY = "CWcvNsz8fkzifFJPD6r7kc2T6TCU6pbhxa0z0nRm"

IST = timezone(timedelta(hours=5, minutes=30))

REPORT_DATE = os.environ.get("REPORT_DATE", "").strip()
# When set, every channel's message is redirected here instead (with a marker showing
# the real destination) — for test runs without touching the real CHANNELS routing.
TEST_CHANNEL_ID = os.environ.get("TEST_CHANNEL_ID", "").strip()

# ── CHANNEL / TEAM CONFIG ──────────────────────────────────────
# Each channel gets ONE Slack message containing one table per category.
# "members" = plain agent names as they appear in SpringVerify/Redash (with or
# without the team-prefix, e.g. "Manash Kashyap" or "C A Manash Kashyap" both work).
# FILL THESE IN once the member list is provided.

CHANNELS = [
    {
        "channel_id": "CS5CX8LPQ",  # #sv-in-ops-caseanalysis
        "categories": [
            {"label": "CA + Initiation", "members": [
                "Subhashree L", "Priyanka Krishnan", "Manash Pratim Kashyap", "Anitha Sagari Ravirala",
                "Nikhil .", "Nayan Shandil", "Dharani Lakshmi", "Aaiyana Vinod Sharma", "Poojasri Adambhakam",
                "Kondeti Ashvitha", "Sahil Vilas Mule", "Nishmeet Singh Rajpal", "Abhishek Parashari",
                "Abhishek Rawat", "Adithya Padmanabhan", "Indukuri Niranjan Reddy", "Ishita Mishra",
                "Divyajot Kaur", "Mohd Azfar Khan", "Aishwarya Arya", "Noshin M K", "Anand Kumar",
                "Chinthala VSSSL Mokshajna", "Anmol Sharma",
            ]},
        ],
    },
    {
        "channel_id": "CS2PEFLMA",  # #sv-in-ops-employment
        "categories": [
            {"label": "Grading", "members": [
                "Vivek Kumar Singh", "Dithya Ann Mathew", "Tapas Patra", "Bhavica Dhamija", "Tuhin Mondal",
                "Thejas Vittal", "E Tarun", "Shaeeshta Shaila", "Chirumamilla Hamsa Veni",
                "Peddireddy Vasu Deva Reddy", "Priyanka Lohia", "Puneesh Hingorani", "Shambhavi Kumari",
                "Vikas Bishnoi", "Akhil", "Pentapalli Charan", "Samiksha Pilaniya", "K Sai Vaishnav Kumar",
                "Utkarsh Raj", "Abhishek Mohan", "Surya Pratap", "Jay Pawar",
            ]},
            {"label": "Followups", "members": [
                # ADD Followups
                "Chandrima Banik", "Nishika Dwivedi", "Anindita Maity", "Jillella Akshaya Prajwala",
                "Bevara Hemanth Kumar", "Debjani Dutta Gupta", "Raunak Kumar", "Sahil",
                # EDU Followups
                "Kartik Kaushal", "Navaneetha KS", "D Joyce Blessia", "Janani S P", "Nara Sumanth",
                "Mehak Rajput",
                # EMP Followups
                "Manisha Suresh Yadav", "Aishu Ji Lochan", "Pratham Rathor", "Adyasha Pattanaik", "Pranshu",
            ]},
        ],
    },
    {
        "channel_id": "CQRU28ES0",  # #sv-in-ops-add (Address Verification)
        "categories": [
            {"label": "QC", "members": [
                "Vikash Sunaliya", "Shafaque Shadni", "Shaik Suraj", "Mohammad Sameem Nazki", "Shlok Paliwal",
                "Vanshika Sharma", "Utsav Banerjee", "Sparsh Maheshwari", "Nishant Gupta", "Manpreet Kaur",
                "Alisha Chaudhary", "Anandita Mahajan", "Nandini Bansal", "Mitta Ruthika", "Boaz Davidson",
                "Parinita Jadone", "Harshitha Sakkuri", "Chuppa Harshitha", "Shivam Kumar", "Talwinder Singh",
                "Tanisha Thakur", "Subhajit Debbarma", "Saransh Jaggi", "Anushka Jaiswal", "Abhishek Sangwan",
                "Sachin Kumar Singh",
            ]},
            {"label": "Email Clearance", "members": [
                # ADD E-mail Clearance
                "Deepika S", "Lavanya Dani", "Riya Sinha",
                # EDU E-mail Clearance
                "Sakshi Upesh Kamani", "Md. Parvezuddin",
                # EMP E-mail Clearance
                "Divya Harish", "Sanskar Shrivastava",
            ]},
        ],
    },
    {
        "channel_id": "C023SD1L2E7",  # #sv-in-ops-misc-checks
        "categories": [
            {"label": "MISC", "members": [
                "Pratyush Badhani", "Samriddhi Kundu", "B Hemanth Reddy", "Kousik Ruidas", "Samraggee Saha",
                "Swati Jampal", "Abhraneel Chattopadhyay", "Shivam Kumar Jha", "Pavithra M",
            ]},
            {"label": "Payment Settlement", "members": [
                "Barsha Agarwal", "Shivam Bhardwaj",
            ]},
        ],
    },
    {
        "channel_id": "C07QAABSJ6R",  # #sv-in-ops-additional-tasks
        "categories": [
            {"label": "Case Addition", "members": [
                "Manas Kumar Mishra", "Abhay Chandrakant Nayak", "Rahul Sutradhar", "Ankita Basak",
                "Chirag Sethi", "Sonia Thakur",
            ]},
        ],
    },
    {
        "channel_id": "C08TMLA7YSU",  # #sv-in-ops-research
        "categories": [
            {"label": "Research", "members": [
                "P Swarna Lakshmi", "Hitakshi Mehto", "Daraksha Hussain", "Shuman Thappa", "Satarupa Konar",
                "Al Hasan", "Soumik Bandyopadhyay", "Adithyan S", "Aman Raj", "Hasamuddin Ansari",
                "Ballani Venkata Avinas",
            ]},
        ],
    },
    {
        "channel_id": "C08MMSLV43H",  # #sv-in-ops-ref
        "categories": [
            {"label": "Reference", "members": [
                "Nazia Hasan", "Sakshi Bhuyan", "Gayathri A", "Kishore M", "Udita Singh",
            ]},
        ],
    },
]

# Known name prefixes agents' Redash display names carry (e.g. "C A Manash Kashyap").
# Stripped for matching so members can be listed with or without the prefix.
NAME_PREFIXES = [
    "Payment Settlement", "Customer Ops", "Q C", "R T", "C S", "A T", "V M",
    "C A", "Add", "Grading", "Initiation", "Misc", "Supp", "Ops", "Edu",
    "Emp", "Ref", "Dev",
]


def clean_name(name):
    n = " ".join((name or "").split())
    upper = n.upper()
    for prefix in sorted(NAME_PREFIXES, key=len, reverse=True):
        if upper.startswith(prefix.upper() + " "):
            n = n[len(prefix):].strip()
            break
    return n.lower()


def name_tokens(name):
    """Alpha-only lowercase token set, e.g. 'B Hemanth Reddy' -> {'b','hemanth','reddy'}."""
    cleaned = clean_name(name)
    return frozenset(t for t in "".join(c if c.isalpha() or c == " " else " " for c in cleaned).split() if t)


def humanize(enum_value):
    if not enum_value or enum_value == "N/A":
        return "N/A"
    return " ".join(w.capitalize() for w in enum_value.replace("-", "_").split("_"))


def ordinal(n):
    if 11 <= n <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"


def fmt_date(dt):
    return f"{ordinal(dt.day)} {dt.strftime('%B %Y')}"


# ── FETCH REDASH DATA ──────────────────────────────────────────
# tasks.task_completed_at / errors.created_at / candidate_logs.created_at are all
# stored in true UTC (verified NOW() = UTC_TIMESTAMP() on this data source). To get
# a clean IST calendar day we must shift the boundary by -5:30, NOT compare against
# naive 00:00:00/23:59:59 strings (that's an ~5.5h-shifted bug seen in other reports).

def ist_day_utc_bounds(target_date_ist):
    start_utc = target_date_ist.astimezone(timezone.utc)
    end_utc = start_utc + timedelta(days=1)
    return start_utc.strftime("%Y-%m-%d %H:%M:%S"), end_utc.strftime("%Y-%m-%d %H:%M:%S")


def fetch_adhoc(sql):
    """
    POST /api/query_results (ad-hoc, no saved query object) with max_age=0.
    If queued, poll /api/jobs/{id} until done, matching ops_report.js's pattern.
    """
    headers = {"Authorization": f"Key {REDASH_API_KEY}", "Content-Type": "application/json"}
    payload = {"data_source_id": REDASH_DS_ID, "query": sql, "max_age": 0}
    r = requests.post(f"{REDASH_BASE}/api/query_results", headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    resp = r.json()

    if "query_result" in resp:
        return resp["query_result"]["data"]["rows"]

    job_id = resp.get("job", {}).get("id")
    if not job_id:
        raise Exception(f"Unexpected Redash response: {str(resp)[:300]}")
    for _ in range(30):
        time.sleep(2)
        jr = requests.get(f"{REDASH_BASE}/api/jobs/{job_id}", headers=headers, timeout=30)
        jr.raise_for_status()
        job = jr.json().get("job", {})
        if job.get("status") == 3:  # finished
            rr = requests.get(f"{REDASH_BASE}/api/query_results/{job['query_result_id']}", headers=headers, timeout=30)
            rr.raise_for_status()
            return rr.json()["query_result"]["data"]["rows"]
        if job.get("status") == 4:  # failed
            raise Exception(f"Redash query failed: {job.get('error')}")
    raise Exception("Redash ad-hoc query timed out after 60s")


def fetch_completed(start_utc, end_utc):
    sql = f"""
        SELECT
            u.name AS "Agent Name",
            tt.value AS "Task Type",
            COALESCE(ct.value, 'N/A') AS "Check Type",
            COUNT(DISTINCT ts.id) AS "Completed Count"
        FROM tasks ts
        INNER JOIN users u ON u.id = ts.completed_by_user_id_fk
        INNER JOIN enums tt ON ts.task_type = tt.id AND tt.type = 'TEAM_TYPE' AND tt.deleted_at IS NULL
        LEFT JOIN enums ct ON ts.check_type = ct.id AND ct.deleted_at IS NULL
        WHERE
            ts.deleted_at IS NULL
            AND ts.task_completed_at >= '{start_utc}'
            AND ts.task_completed_at < '{end_utc}'
            AND ts.task_status = (SELECT id FROM enums WHERE type='TASK_STATUS' AND value='COMPLETED' AND deleted_at IS NULL LIMIT 1)
            AND ts.completed_by_user_id_fk NOT IN (4, 17542)
        GROUP BY u.name, tt.value, ct.value
        ORDER BY u.name, tt.value, ct.value
    """
    rows = fetch_adhoc(sql)
    print(f"  Completed: {len(rows)} rows")
    return rows


def fetch_errors(start_utc, end_utc):
    sql = f"""
        SELECT u.name AS "Name", COUNT(DISTINCT e.id) AS "Error Count"
        FROM errors e
        INNER JOIN users u ON u.id = e.agent_user_id_fk
        LEFT JOIN teams_user_mapping tum ON tum.user_id_fk = u.id
        LEFT JOIN teams t ON t.id = tum.team_id_fk AND t.deleted_at IS NULL
        LEFT JOIN enums dept_enum ON dept_enum.id = t.department_enum_fk AND dept_enum.deleted_at IS NULL
        WHERE e.deleted_at IS NULL
          AND e.created_at >= '{start_utc}' AND e.created_at < '{end_utc}'
          AND (dept_enum.value = 'OPERATIONS' OR LOWER(u.name) LIKE '%system user%' OR LOWER(u.name) LIKE '%springverify ai%')
        GROUP BY u.name
        ORDER BY u.name
    """
    rows = fetch_adhoc(sql)
    print(f"  Errors: {len(rows)} rows")
    return rows


def fetch_case_additions(start_utc, end_utc):
    sql = f"""
        SELECT u.name AS "Agent Name", COUNT(DISTINCT cl.candidate_id_fk) AS "Total Count"
        FROM candidate_logs cl
        JOIN users u ON u.id = COALESCE(cl.proxy_user_id_fk, cl.user_id_fk)
        JOIN company_candidate_mapping ccm ON ccm.candidate_id = cl.candidate_id_fk AND ccm.deleted_at IS NULL
        WHERE cl.type = 'CANDIDATE_CONSENT_ADDED' AND cl.deleted_at IS NULL
          AND ((cl.user_type=1 AND cl.proxy_user_id_fk IS NULL) OR (cl.user_type=2 AND cl.proxy_user_id_fk IS NOT NULL))
          AND cl.created_at >= '{start_utc}' AND cl.created_at < '{end_utc}'
        GROUP BY u.name
        ORDER BY u.name
    """
    rows = fetch_adhoc(sql)
    print(f"  Case additions: {len(rows)} rows")
    return rows


# ── AGGREGATE ───────────────────────────────────────────────────

def build_agent_data(completed_rows, error_rows, case_add_rows):
    """
    Returns dict keyed by clean_name(agent) ->
      {
        "display_name": <best display name seen>,
        "combos": {"Case Analysis - Address": count, ...},
        "completed_total": int,
        "error_total": int,
        "case_add_total": int,
      }
    """
    data = defaultdict(lambda: {
        "display_name": None, "combos": defaultdict(int),
        "completed_total": 0, "error_total": 0, "case_add_total": 0,
    })

    for row in completed_rows:
        raw_name = row.get("Agent Name") or ""
        key = clean_name(raw_name)
        if not key:
            continue
        task = humanize(row.get("Task Type"))
        check = humanize(row.get("Check Type"))
        combo = f"{task} - {check}" if check != "N/A" else task
        count = int(row.get("Completed Count") or 0)
        d = data[key]
        d["display_name"] = d["display_name"] or raw_name
        d["combos"][combo] += count
        d["completed_total"] += count

    for row in error_rows:
        raw_name = row.get("Name") or ""
        key = clean_name(raw_name)
        if not key:
            continue
        count = int(row.get("Error Count") or 0)
        d = data[key]
        d["display_name"] = d["display_name"] or raw_name
        d["error_total"] += count

    for row in case_add_rows:
        raw_name = row.get("Agent Name") or ""
        key = clean_name(raw_name)
        if not key:
            continue
        count = int(row.get("Total Count") or 0)
        d = data[key]
        d["display_name"] = d["display_name"] or raw_name
        d["case_add_total"] += count

    return data


# ── MATCHING (handles missing middle names / initials, e.g. roster's
#    "B Hemanth Reddy" vs Redash's "Misc Hemanth Reddy") ──────────

def build_token_index(agent_data):
    return [(key, name_tokens(key)) for key in agent_data]


def match_member(member, agent_data, token_index):
    """Returns (data_dict_or_None, was_fuzzy_match)."""
    key = clean_name(member)
    if key in agent_data:
        return agent_data[key], False

    member_tokens = name_tokens(member)
    if not member_tokens:
        return None, False

    candidates = [(k, t) for k, t in token_index if t and (member_tokens <= t or t <= member_tokens)]
    if not candidates:
        return None, False
    candidates.sort(key=lambda c: len(c[1] & member_tokens), reverse=True)
    return agent_data[candidates[0][0]], True


# ── FORMAT SLACK MESSAGE ────────────────────────────────────────

def format_category_table(label, members, agent_data):
    if not members:
        return f"*{label}*\n_No members configured yet._"

    token_index = build_token_index(agent_data)
    rows = []
    unmatched = []
    fuzzy_matches = []
    combo_cols = []
    seen_combos = set()

    for member in members:
        d, was_fuzzy = match_member(member, agent_data, token_index)
        if d is None:
            unmatched.append(member)
            rows.append((member, {}, 0, 0, 0))
            continue
        if was_fuzzy:
            fuzzy_matches.append(f"{member} → {d['display_name']}")
        for combo in d["combos"]:
            if combo not in seen_combos and d["combos"][combo] > 0:
                seen_combos.add(combo)
                combo_cols.append(combo)
        rows.append((d["display_name"] or member, d["combos"], d["completed_total"], d["error_total"], d["case_add_total"]))

    combo_cols.sort()
    rows.sort(key=lambda r: r[2], reverse=True)

    name_w = max([len("Agent")] + [len(r[0]) for r in rows]) + 1
    combo_w = {c: max(len(c), 6) + 1 for c in combo_cols}

    header = "Agent".ljust(name_w)
    for c in combo_cols:
        header += c.rjust(combo_w[c])
    header += "Done".rjust(7) + "Err".rjust(6) + "Case+".rjust(8)

    lines = [header, "-" * len(header)]
    tot_done = tot_err = tot_case = 0
    tot_combo = defaultdict(int)

    for name, combos, done, err, case_add in rows:
        line = name.ljust(name_w)
        for c in combo_cols:
            v = combos.get(c, 0)
            line += (str(v) if v else "-").rjust(combo_w[c])
            tot_combo[c] += v
        line += str(done).rjust(7) + str(err).rjust(6) + str(case_add).rjust(8)
        lines.append(line)
        tot_done += done
        tot_err += err
        tot_case += case_add

    totals_line = "TOTAL".ljust(name_w)
    for c in combo_cols:
        totals_line += str(tot_combo[c]).rjust(combo_w[c])
    totals_line += str(tot_done).rjust(7) + str(tot_err).rjust(6) + str(tot_case).rjust(8)
    lines.append("-" * len(header))
    lines.append(totals_line)

    table = "```\n" + "\n".join(lines) + "\n```"
    section = f"*{label}*\n{table}"
    if unmatched:
        section += f"\n_No data found for: {', '.join(unmatched)}_"
    if fuzzy_matches:
        section += f"\n_Matched via name variant: {'; '.join(fuzzy_matches)}_"
    return section


def format_channel_message(channel_cfg, date_label, agent_data):
    categories = channel_cfg["categories"]
    report_name = " + ".join(c["label"] for c in categories) + " Team Daily Task Report"
    header = f"\U0001f4ca *{report_name} — {date_label}*"
    sections = [format_category_table(c["label"], c["members"], agent_data) for c in categories]
    return "\n\n".join([header] + sections)


# ── SLACK AUTH ───────────────────────────────────────────────────
# This repo has its own bot token (bot: eod_pending_task_repo) — separate from
# whatever Error-report/TAT-report use, so there's no shared hardcoded suffix to
# reconstruct here. Only apply generic, content-agnostic corrections (e.g. a
# mis-capitalized literal "xoxb-" prefix), and verify each with a real auth.test call.

def resolve_slack_token():
    global SLACK_TOKEN
    raw = _raw_token
    candidates = []

    if raw[:5].lower() == "xoxb-" and raw[:5] != "xoxb-":
        candidates.append(("prefix-case-fixed", "xoxb-" + raw[5:]))
    candidates.append(("raw", raw))

    print(f"SLACK_BOT_TOKEN as received: length={len(raw)}, starts='{raw[:6]}', ends='{raw[-6:]}', sha256={hashlib.sha256(raw.encode()).hexdigest()}")

    for label, token in candidates:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        r = requests.post("https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {token}"}, timeout=15)
        data = r.json()
        print(f"  {label}: sha256={token_hash} ok={data.get('ok')} error={data.get('error')}")
        if data.get("ok"):
            SLACK_TOKEN = token
            print(f"  Using {label} token (bot: {data.get('user')}, team: {data.get('team')})")
            return
    raise Exception("No working Slack token — none of the corrected/raw SLACK_BOT_TOKEN variants passed auth.test. Re-check the secret value.")


# ── POST TO SLACK ────────────────────────────────────────────────

def post_slack(channel_id, text):
    r = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
        json={"channel": channel_id, "text": text},
    )
    r.raise_for_status()
    resp = r.json()
    if not resp.get("ok"):
        raise Exception(f"Slack API error for channel {channel_id}: {resp.get('error')}")
    return resp["ts"]


# ── MAIN ──────────────────────────────────────────────────────────

def run_report():
    resolve_slack_token()

    if REPORT_DATE:
        target_date = datetime.strptime(REPORT_DATE, "%Y-%m-%d").replace(tzinfo=IST)
    else:
        now_ist = datetime.now(IST)
        target_date = (now_ist - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    date_label = fmt_date(target_date)
    start_utc, end_utc = ist_day_utc_bounds(target_date)
    print(f"Reporting on IST day: {date_label}  (UTC window {start_utc} -> {end_utc})")

    print("Fetching Redash data...")
    completed_rows = fetch_completed(start_utc, end_utc)
    error_rows = fetch_errors(start_utc, end_utc)
    case_add_rows = fetch_case_additions(start_utc, end_utc)

    agent_data = build_agent_data(completed_rows, error_rows, case_add_rows)

    for channel_cfg in CHANNELS:
        message = format_channel_message(channel_cfg, date_label, agent_data)
        has_members = any(c["members"] for c in channel_cfg["categories"])
        if not has_members:
            print(f"Skipping channel {channel_cfg['channel_id']} — no members configured yet")
            continue

        target_channel = channel_cfg["channel_id"]
        if TEST_CHANNEL_ID:
            message = f"_[TEST RUN — would normally post to {channel_cfg['channel_id']}]_\n" + message
            target_channel = TEST_CHANNEL_ID

        ts = post_slack(target_channel, message)
        print(f"Posted to {target_channel} (ts={ts})")


if __name__ == "__main__":
    run_report()

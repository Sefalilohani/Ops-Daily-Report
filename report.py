import os
import time
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

# When set (via a dropdown choice, not free text — Slack channel IDs are case-sensitive
# and free-text GitHub Actions inputs have been getting mangled by something upstream),
# every channel's message is redirected here instead — for test runs without touching
# the real CHANNELS routing.
TEST_CHANNEL_ALIASES = {
    "testing-sefali": "C0AGRE19V6U",
}
TEST_CHANNEL_ID = TEST_CHANNEL_ALIASES.get(os.environ.get("TEST_CHANNEL", "").strip(), "")

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

# Each category's Slack user group (for @-mention) and lead (for direct @-mention).
# IDs resolved from the workspace directly, not typed as free text (Slack IDs are
# case-sensitive and this environment's text fields have been auto-mangling case).
CATEGORY_TAGS = {
    "Grading":            {"usergroup": "S0BKVL7E0SH", "lead": "UN1E2L4G0"},    # ops-grading, Selva
    "QC":                 {"usergroup": "S046ESUQLS1", "lead": "U03BUG17X54"},  # svin-qc, Ramya
    "CA + Initiation":    {"usergroup": "S046WGXTBED", "lead": "U017K6KQT2A"},  # opsinitiation, Thanveer
    "Research":           {"usergroup": "S08VARCA849", "lead": "UN1E2L4G0"},    # svin-emp-research, Selva
    "Reference":          {"usergroup": "S04K6P0CYES", "lead": "UN1E2L4G0"},    # svin-ref, Selva
    "Email Clearance":    {"usergroup": "S0BKZ13RE82", "lead": "U03BUG17X54"},  # opsemailtriage, Ramya
    "Followups":          {"usergroup": "S0BLTALCZA4", "lead": "UURRMS3MG"},    # opsfollowup, Shalini
    "Case Addition":      {"usergroup": "S086WH7H6A0", "lead": "UURRMS3MG"},    # svin-caseaddition, Shalini
    "Payment Settlement": {"usergroup": "S0BKX213HFG", "lead": "U017K6KQT2A"},  # paymentsettlement, Thanveer
    "MISC":               {"usergroup": "S05BY1H4HJ5", "lead": "U017K6KQT2A"},  # svin-misc, Thanveer
}

# Short column headers for Task Type in the main table (mirrors the style of the
# existing "Intern Daily Task Report" bot — QC / GRD / INIT as columns, not sub-rows).
TASK_TYPE_INFO = {
    "CASE_ANALYSIS": ("CA", "Case Analysis"),
    "INITIATION": ("INIT", "Initiation"),
    "QC": ("QC", "QC"),
    "GRADING": ("GRD", "Grading"),
    "FOLLOW_UP": ("FU", "Follow Up"),
    "EMAIL_CLEARANCE": ("EC", "Email Clearance"),
    "PAYMENTS_SETTLEMENT": ("PS", "Payment Settlement"),
    "ADDITIONAL_TASKS": ("AT", "Additional Tasks"),
    "RESEARCH": ("RES", "Research"),
    "RESEARCH_FOLLOW_UP": ("RFU", "Research Follow Up"),
    "INSUFFICIENCY_CLEARANCE": ("IC", "Insufficiency Clearance"),
    "VENDOR_MANAGEMENT": ("VM", "Vendor Management"),
    "CONSENT_REVIEW": ("CR", "Consent Review"),
    "DOCUMENTS_CROPPING": ("DC", "Documents Cropping"),
    "WHATSAPP_CLEARANCE": ("WC", "WhatsApp Clearance"),
    "WHATSAPP_FOLLOW_UP": ("WFU", "WhatsApp Follow Up"),
}


def task_type_info(raw_task_type):
    if raw_task_type in TASK_TYPE_INFO:
        return TASK_TYPE_INFO[raw_task_type]
    label = humanize(raw_task_type)
    return label[:4].upper(), label


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
        "task_totals": {"QC": 178, "GRD": 32, ...},        # Task Type -> completed count
        "task_labels": {"QC": "QC", "GRD": "Grading", ...},  # Task Type abbr -> full label
        "task_check": {"QC": {"Address": 10, "Court": 10, ...}, ...},  # per Task Type, Check Type breakdown
        "completed_total": int,
        "error_total": int,
        "case_add_total": int,
      }
    """
    data = defaultdict(lambda: {
        "display_name": None,
        "task_totals": defaultdict(int),
        "task_labels": {},
        "task_check": defaultdict(lambda: defaultdict(int)),
        "completed_total": 0, "error_total": 0, "case_add_total": 0,
    })

    for row in completed_rows:
        raw_name = row.get("Agent Name") or ""
        key = clean_name(raw_name)
        if not key:
            continue
        abbr, full_label = task_type_info(row.get("Task Type") or "")
        check_raw = row.get("Check Type")
        count = int(row.get("Completed Count") or 0)
        d = data[key]
        d["display_name"] = d["display_name"] or raw_name
        d["task_totals"][abbr] += count
        d["task_labels"][abbr] = full_label
        if check_raw and check_raw != "N/A":
            d["task_check"][abbr][humanize(check_raw)] += count
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
# Main message: one row per agent, Task Type as columns (like the existing "Intern
# Daily Task Report" bot: QC / GRD / INIT columns), plus Total/Errors/Case Addition.
# Thread reply: Check Type breakdown per agent per Task Type, as small column tables —
# full detail stays available, but tucked into the thread instead of the main channel.

def format_category_section(label, members, agent_data):
    """Returns (main_text, thread_text_or_None, completed_total, error_total, case_add_total)."""
    tag = CATEGORY_TAGS.get(label)
    tag_line = f"cc: <!subteam^{tag['usergroup']}> <@{tag['lead']}>" if tag else ""

    if not members:
        text = f"*{label}*\n_No members configured yet._"
        return (text + (f"\n{tag_line}" if tag_line else "")), None, 0, 0, 0

    token_index = build_token_index(agent_data)
    idle_names = []
    unmatched = []

    matched_rows = []
    for member in members:
        d, _was_fuzzy = match_member(member, agent_data, token_index)
        if d is None:
            unmatched.append(member)
            continue
        matched_rows.append((d["display_name"] or member, d))

    matched_rows.sort(key=lambda r: r[1]["completed_total"], reverse=True)

    # Only show Case Addition at all for teams where it's actually relevant that day —
    # most teams (QC, Grading, Research, ...) never touch case additions, so a
    # constant "Case Addition: 0" on every line is pure noise for them.
    show_case_addition = any(d["case_add_total"] > 0 for _, d in matched_rows)

    active = []
    tot_done = tot_err = tot_case = 0
    for name, d in matched_rows:
        tot_done += d["completed_total"]
        tot_err += d["error_total"]
        tot_case += d["case_add_total"]
        if d["completed_total"] == 0 and d["error_total"] == 0 and d["case_add_total"] == 0:
            idle_names.append(name)
            continue
        active.append((name, d))

    thread_text = None
    if not active:
        main_lines = ["_No activity today._"]
    else:
        # Task Type columns actually used by this team today, ordered by team-wide volume.
        task_col_totals = defaultdict(int)
        for _, d in active:
            for abbr, cnt in d["task_totals"].items():
                task_col_totals[abbr] += cnt
        task_cols = sorted(task_col_totals, key=lambda a: task_col_totals[a], reverse=True)

        name_w = max([len("Agent")] + [len(n) for n, _ in active] + [len("TEAM TOTAL")]) + 2
        col_w = {a: max(len(a), 5) + 2 for a in task_cols}
        done_w = max(len("Total"), len(str(tot_done))) + 2
        err_w = max(len("Err"), len(str(tot_err))) + 2
        case_w = max(len("Case+"), len(str(tot_case))) + 2 if show_case_addition else 0

        header = "Agent".ljust(name_w)
        for a in task_cols:
            header += a.rjust(col_w[a])
        header += "Total".rjust(done_w) + "Err".rjust(err_w)
        if show_case_addition:
            header += "Case+".rjust(case_w)
        sep = "-" * len(header)

        table_lines = [header, sep]
        for name, d in active:
            row = name.ljust(name_w)
            for a in task_cols:
                v = d["task_totals"].get(a, 0)
                row += (str(v) if v else "-").rjust(col_w[a])
            row += str(d["completed_total"]).rjust(done_w) + str(d["error_total"]).rjust(err_w)
            if show_case_addition:
                row += str(d["case_add_total"]).rjust(case_w)
            table_lines.append(row)
        table_lines.append(sep)

        total_row = "TEAM TOTAL".ljust(name_w)
        for a in task_cols:
            total_row += str(task_col_totals[a]).rjust(col_w[a])
        total_row += str(tot_done).rjust(done_w) + str(tot_err).rjust(err_w)
        if show_case_addition:
            total_row += str(tot_case).rjust(case_w)
        table_lines.append(total_row)

        main_lines = ["```\n" + "\n".join(table_lines) + "\n```"]

        # Thread: Check Type breakdown, one numbered block per agent, per Task Type
        # they touched — blank line between agents so it stays scannable, not a wall.
        thread_blocks = [f":clipboard: *{label} — Check Type Breakdown*"]
        for i, (name, d) in enumerate(active, 1):
            sorted_tasks = sorted(d["task_check"].items(), key=lambda kv: sum(kv[1].values()), reverse=True)
            if not sorted_tasks:
                continue
            agent_blocks = [f"*{i}. {name}*"]
            for abbr, checks in sorted_tasks:
                check_items = sorted(checks.items(), key=lambda kv: kv[1], reverse=True)
                if not check_items:
                    continue
                full_label = d["task_labels"].get(abbr, abbr)
                c_w = {c: max(len(c), len(str(v))) + 2 for c, v in check_items}
                c_header = "".join(c.ljust(c_w[c]) for c, _ in check_items)
                c_values = "".join(str(v).ljust(c_w[c]) for c, v in check_items)
                agent_blocks.append(f"_{full_label}_\n```\n{c_header}\n{c_values}\n```")
            thread_blocks.append("\n".join(agent_blocks))
        thread_text = "\n\n".join(thread_blocks) if len(thread_blocks) > 1 else None

    lines = main_lines
    if idle_names:
        lines.append(f"_No activity: {', '.join(idle_names)}_")
    if unmatched:
        lines.append(f"_No data found for: {', '.join(unmatched)}_")
    if tag_line:
        lines.append(tag_line)

    return "\n".join(lines), thread_text, tot_done, tot_err, tot_case


def format_channel_messages(channel_cfg, date_label, agent_data):
    """
    Returns a list of (main_text, thread_text) tuples — one per category, plus a
    trailing grand-total message (no thread) if the channel combines more than one
    category. Posting each category separately (rather than joining into one giant
    string) is what actually fixes the "Slack splits it mid-sentence" problem.
    """
    categories = channel_cfg["categories"]

    # Each category is its own team with its own report name — "CA + Initiation" is
    # the one genuine combined team (one roster group); Grading/Followups, QC/Email
    # Clearance, and MISC/Payment Settlement are distinct teams that just share a
    # Slack channel, so they get separate headers, not a merged "X + Y" name.
    messages = []
    grand_done = grand_err = grand_case = 0
    for c in categories:
        text, thread_text, done, err, case_add = format_category_section(c["label"], c["members"], agent_data)
        header = f"\U0001f4ca *{c['label']} Team Daily Task Report — {date_label}*"
        messages.append((f"{header}\n\n{text}", thread_text))
        grand_done += done
        grand_err += err
        grand_case += case_add

    if len(categories) > 1:
        combined_name = " + ".join(c["label"] for c in categories)
        grand_line = f"Completed: *{grand_done}* · Errors: *{grand_err}*"
        if grand_case > 0:
            grand_line += f" · Case Addition: *{grand_case}*"
        messages.append((
            f":bar_chart: *{combined_name} — Combined Channel Total — {date_label}*\n\n{grand_line}",
            None
        ))

    return messages


# ── SLACK AUTH ───────────────────────────────────────────────────

def resolve_slack_token():
    global SLACK_TOKEN
    SLACK_TOKEN = _raw_token
    r = requests.post("https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {SLACK_TOKEN}"}, timeout=15)
    data = r.json()
    if not data.get("ok"):
        raise Exception(f"SLACK_BOT_TOKEN failed auth.test: {data.get('error')}. Re-check the secret in repo settings.")
    print(f"Slack auth OK — bot: {data.get('user')}, team: {data.get('team')}")


# ── POST TO SLACK ────────────────────────────────────────────────

MAX_MESSAGE_CHARS = 3500  # conservative — this workspace has been observed fragmenting
                          # single posts somewhere well under Slack's documented 40,000


def chunk_message(text, max_len=MAX_MESSAGE_CHARS):
    """Split text into pieces on line boundaries, never mid-line, each under max_len."""
    if len(text) <= max_len:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_len and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def post_slack_message(channel_id, text, thread_ts=None):
    for chunk in chunk_message(text):
        payload = {"channel": channel_id, "text": chunk}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        resp = r.json()
        if not resp.get("ok"):
            raise Exception(f"Slack API error for channel {channel_id}: {resp.get('error')}")
        yield resp["ts"]


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
        has_members = any(c["members"] for c in channel_cfg["categories"])
        if not has_members:
            print(f"Skipping channel {channel_cfg['channel_id']} — no members configured yet")
            continue

        messages = format_channel_messages(channel_cfg, date_label, agent_data)
        target_channel = TEST_CHANNEL_ID or channel_cfg["channel_id"]

        for main_text, thread_text in messages:
            if TEST_CHANNEL_ID:
                main_text = f"_[TEST RUN — would normally post to {channel_cfg['channel_id']}]_\n" + main_text

            main_ts = None
            for ts in post_slack_message(target_channel, main_text):
                main_ts = main_ts or ts
                print(f"Posted to {target_channel} (ts={ts})")

            if thread_text and main_ts:
                for ts in post_slack_message(target_channel, thread_text, thread_ts=main_ts):
                    print(f"  Thread reply posted (ts={ts})")


if __name__ == "__main__":
    run_report()

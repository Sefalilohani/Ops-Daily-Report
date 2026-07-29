import os
import time
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from itertools import permutations

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
# Deliberately matches Redash query 3045's logic (confirmed as the team's intended
# behavior): a "day" is the raw UTC calendar day, NOT an IST-midnight-to-midnight day.
# The standard shift is 9 AM-7 PM IST, which sits well inside this window either way;
# for the few agents who occasionally run late into the early hours, the raw-UTC-day
# cutover falls at 5:30 AM IST (a naturally quiet time) instead of at IST midnight —
# so one continuous overnight shift stays together in a single day's report instead
# of being split across two days' reports.

def ist_day_utc_bounds(target_date_ist):
    start_utc = datetime(target_date_ist.year, target_date_ist.month, target_date_ist.day, tzinfo=timezone.utc)
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
    # 4-way, non-overlapping breakdown of case-addition work, matching Redash query 1997.
    # The "who filled the form" signal comes from company_candidate_mapping.form_filled_by /
    # form_filled_by_user_id / proxy_user_id — the same data the SV admin UI's Verification
    # Details -> Form Status section shows — not just candidate_logs, which misses cases
    # where one agent adds the candidate and a different agent fills the form.
    #   1. Added & Filled     — same agent both added (directly) and filled the form.
    #   2. Added, Not Filled  — agent added (directly) but the form is still unfilled.
    #   3. Filled Only        — a different agent (or no logged adder) filled the form.
    #   4. Proxy Added        — agent added the candidate as proxy via the CA portal.
    # The 30-day lookback lets an add and a later fill (or vice versa) be matched even
    # when they land on different days, while staying sargable on created_at.
    sql = f"""
        WITH add_events AS (
            SELECT
                cl.candidate_id_fk,
                CASE WHEN cl.user_type = 1 THEN cl.user_id_fk ELSE cl.proxy_user_id_fk END AS adder_user_id,
                CASE WHEN cl.user_type = 1 THEN 'DIRECT' ELSE 'PROXY' END AS adder_type,
                cl.created_at AS add_at,
                ROW_NUMBER() OVER (PARTITION BY cl.candidate_id_fk ORDER BY cl.created_at ASC) AS rn
            FROM candidate_logs cl
            WHERE cl.type = 'CANDIDATE_CONSENT_ADDED' AND cl.deleted_at IS NULL
              AND ((cl.user_type = 1 AND cl.user_id_fk IS NOT NULL)
                OR (cl.user_type = 2 AND cl.proxy_user_id_fk IS NOT NULL))
              AND cl.created_at >= DATE_SUB('{start_utc}', INTERVAL 30 DAY)
              AND cl.created_at < '{end_utc}'
        ),
        canonical_add AS (
            SELECT candidate_id_fk, adder_user_id, adder_type, add_at FROM add_events WHERE rn = 1
        ),
        fills AS (
            SELECT
                ccm.candidate_id, ccm.form_filled,
                CASE WHEN ccm.form_filled_by = 1 THEN ccm.form_filled_by_user_id
                     WHEN ccm.form_filled_by = 3 THEN ccm.proxy_user_id
                     ELSE NULL END AS filler_user_id
            FROM company_candidate_mapping ccm
            WHERE ccm.deleted_at IS NULL
              AND ccm.created_at >= DATE_SUB('{start_utc}', INTERVAL 30 DAY)
              AND ccm.created_at < '{end_utc}'
        ),
        combined AS (
            SELECT ca.candidate_id_fk, ca.adder_user_id, ca.adder_type, ca.add_at, f.form_filled, f.filler_user_id
            FROM canonical_add ca
            LEFT JOIN fills f ON f.candidate_id = ca.candidate_id_fk
            UNION
            SELECT f.candidate_id AS candidate_id_fk, ca.adder_user_id, ca.adder_type, ca.add_at, f.form_filled, f.filler_user_id
            FROM fills f
            LEFT JOIN canonical_add ca ON ca.candidate_id_fk = f.candidate_id
            WHERE ca.candidate_id_fk IS NULL AND f.filler_user_id IS NOT NULL
        ),
        tagged AS (
            SELECT candidate_id_fk,
                CASE WHEN adder_type = 'PROXY' THEN adder_user_id END AS b4_user, add_at AS b4_date,
                CASE WHEN adder_type = 'DIRECT' AND filler_user_id IS NOT NULL AND filler_user_id = adder_user_id THEN adder_user_id END AS b1_user, add_at AS b1_date,
                CASE WHEN adder_type = 'DIRECT' AND form_filled IS NULL THEN adder_user_id END AS b2_user, add_at AS b2_date,
                CASE WHEN filler_user_id IS NOT NULL AND filler_user_id <> COALESCE(adder_user_id, -1) THEN filler_user_id END AS b3_user, form_filled AS b3_date
            FROM combined
        ),
        per_agent_candidate AS (
            SELECT candidate_id_fk, b1_user AS agent_user_id, 1 AS added_and_filled, 0 AS added_not_filled, 0 AS filled_only, 0 AS proxy_added, b1_date AS credit_date FROM tagged WHERE b1_user IS NOT NULL
            UNION ALL
            SELECT candidate_id_fk, b2_user, 0, 1, 0, 0, b2_date FROM tagged WHERE b2_user IS NOT NULL
            UNION ALL
            SELECT candidate_id_fk, b3_user, 0, 0, 1, 0, b3_date FROM tagged WHERE b3_user IS NOT NULL
            UNION ALL
            SELECT candidate_id_fk, b4_user, 0, 0, 0, 1, b4_date FROM tagged WHERE b4_user IS NOT NULL
        )
        SELECT
            u.name AS "Agent Name",
            SUM(pac.added_and_filled) AS "Added & Filled",
            SUM(pac.added_not_filled) AS "Added, Not Filled",
            SUM(pac.filled_only) AS "Filled Only",
            SUM(pac.proxy_added) AS "Proxy Added"
        FROM per_agent_candidate pac
        JOIN users u ON u.id = pac.agent_user_id
        WHERE pac.credit_date >= '{start_utc}' AND pac.credit_date < '{end_utc}'
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
        "case_add_added_filled": 0, "case_add_added_not_filled": 0,
        "case_add_filled_only": 0, "case_add_proxy_added": 0,
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
        af = int(row.get("Added & Filled") or 0)
        anf = int(row.get("Added, Not Filled") or 0)
        fo = int(row.get("Filled Only") or 0)
        pa = int(row.get("Proxy Added") or 0)
        d = data[key]
        d["display_name"] = d["display_name"] or raw_name
        d["case_add_added_filled"] += af
        d["case_add_added_not_filled"] += anf
        d["case_add_filled_only"] += fo
        d["case_add_proxy_added"] += pa
        d["case_add_total"] += af + anf + fo + pa

    return data


# ── MATCHING (handles missing middle names / initials, e.g. roster's
#    "B Hemanth Reddy" vs Redash's "Misc Hemanth Reddy") ──────────

def build_token_index(agent_data):
    return [(key, name_tokens(key)) for key in agent_data]


def _token_compat(t1, t2):
    """Two tokens are compatible if equal, or one is a single-letter initial of the other
    (e.g. 'k' vs 'krishnan') — SpringVerify abbreviates some surnames to an initial in
    Redash's display name (e.g. roster's 'Priyanka Krishnan' shows there as 'Priyanka K')."""
    return t1 == t2 or (len(t1) == 1 and t2.startswith(t1)) or (len(t2) == 1 and t1.startswith(t2))


def _core_tokens(tokens):
    """Drop bare single-letter initials, keeping only real (multi-letter) name tokens —
    e.g. roster's 'Janani S P' -> just {'janani'}, so it still lines up with Redash's
    'Janani Pugalenthi' (S/P are initials for names Redash doesn't show at all)."""
    core = frozenset(t for t in tokens if len(t) > 1)
    return core if core else tokens


def _names_compatible(tokens_a, tokens_b):
    if tokens_a == tokens_b or tokens_a <= tokens_b or tokens_b <= tokens_a:
        return True
    # Same token count, different content — check for an abbreviation-tolerant pairing
    # (e.g. {priyanka, krishnan} vs {priyanka, k}), not just a same/subset match.
    if len(tokens_a) == len(tokens_b) and any(
        all(_token_compat(x, y) for x, y in zip(tokens_a, perm)) for perm in permutations(tokens_b)
    ):
        return True
    # Ignore bare initials on both sides and compare what's left (handles differing
    # token counts, e.g. 'Janani S P' vs 'Janani Pugalenthi').
    core_a, core_b = _core_tokens(tokens_a), _core_tokens(tokens_b)
    return bool(core_a and core_b and (core_a <= core_b or core_b <= core_a))


def resolve_member_assignments(agent_data):
    """
    Resolves every configured member, across ALL categories/channels at once, to at
    most one Redash record — {(category_label, member_name): data_dict_or_None}.
    This has to be global, not per-member: a generic roster entry like Followups'
    "Sahil" and CA+Initiation's real "Sahil Vilas Mule" can BOTH look like a fuzzy
    match for the same Redash record ("Sahil Mule") in isolation, but only one of
    them should actually win it. An exact match always wins outright; otherwise the
    claimant with the highest token overlap wins, and a genuine tie is left
    unassigned (shows as "no data") rather than guessed.
    """
    token_index = build_token_index(agent_data)

    all_members = [
        (category["label"], member)
        for channel in CHANNELS
        for category in channel["categories"]
        for member in category["members"]
    ]

    exact_owner = {}     # candidate_key -> (label, member)
    claims = defaultdict(list)  # candidate_key -> [(overlap_score, label, member)]

    for label, member in all_members:
        key = clean_name(member)
        if key in agent_data:
            exact_owner[key] = (label, member)
            continue
        member_tokens = name_tokens(member)
        if not member_tokens:
            continue
        for k, t in token_index:
            if t and _names_compatible(member_tokens, t):
                claims[k].append((len(t & member_tokens), label, member))

    assignments = {(label, member): None for label, member in all_members}

    for key, (label, member) in exact_owner.items():
        assignments[(label, member)] = agent_data[key]

    for key, claimants in claims.items():
        if key in exact_owner:
            continue  # already exclusively owned by an exact match
        claimants.sort(key=lambda c: c[0], reverse=True)
        top_score = claimants[0][0]
        winners = [c for c in claimants if c[0] == top_score]
        if len(winners) == 1:
            _, label, member = winners[0]
            assignments[(label, member)] = agent_data[key]
        # else: genuine tie between two members for the same record — leave both
        # unassigned rather than guess which one it really belongs to.

    return assignments


# ── FORMAT SLACK MESSAGE ────────────────────────────────────────
# One message per team, two agent-wise tables — same rows (agents), same
# Total/Errors/Case Addition, just bifurcated two different ways: Task Type as
# columns in the first table, Check Type as columns in the second.

def agent_check_totals(d):
    """Flatten a per-agent task_check breakdown into Check Type -> count, across all task types."""
    totals = defaultdict(int)
    for checks in d["task_check"].values():
        for check_label, cnt in checks.items():
            totals[check_label] += cnt
    return totals


CASE_ADD_SUBCOLS = [
    ("Add&Fill", "case_add_added_filled"),
    ("AddOnly", "case_add_added_not_filled"),
    ("FillOnly", "case_add_filled_only"),
    ("Proxy", "case_add_proxy_added"),
]


def build_agent_col_table(active, tot_done, tot_err, tot_case, show_case_addition, col_getter):
    """Agent-wise table: rows=agents, columns=whatever col_getter(d) returns, plus Total/Err and,
    when relevant, the 4-way non-overlapping case-addition breakdown (Add&Fill/AddOnly/FillOnly/Proxy)."""
    col_totals = defaultdict(int)
    for _, d in active:
        for col, cnt in col_getter(d).items():
            col_totals[col] += cnt
    cols = sorted(col_totals, key=lambda c: col_totals[c], reverse=True)

    case_totals = {}
    if show_case_addition:
        for _, key in CASE_ADD_SUBCOLS:
            case_totals[key] = sum(d[key] for _, d in active)

    name_w = max([len("Agent")] + [len(n) for n, _ in active] + [len("TEAM TOTAL")]) + 2
    col_w = {c: max(len(c), 5) + 2 for c in cols}
    done_w = max(len("Total"), len(str(tot_done))) + 2
    err_w = max(len("Err"), len(str(tot_err))) + 2
    case_w = {}
    if show_case_addition:
        for label, key in CASE_ADD_SUBCOLS:
            case_w[label] = max(len(label), len(str(case_totals[key]))) + 2

    header = "Agent".ljust(name_w)
    for c in cols:
        header += c.rjust(col_w[c])
    header += "Total".rjust(done_w) + "Err".rjust(err_w)
    if show_case_addition:
        for label, _ in CASE_ADD_SUBCOLS:
            header += label.rjust(case_w[label])
    sep = "-" * len(header)

    lines = [header, sep]
    for name, d in active:
        row = name.ljust(name_w)
        counts = col_getter(d)
        for c in cols:
            v = counts.get(c, 0)
            row += (str(v) if v else "-").rjust(col_w[c])
        row += str(d["completed_total"]).rjust(done_w) + str(d["error_total"]).rjust(err_w)
        if show_case_addition:
            for label, key in CASE_ADD_SUBCOLS:
                v = d[key]
                row += (str(v) if v else "-").rjust(case_w[label])
        lines.append(row)
    lines.append(sep)

    total_row = "TEAM TOTAL".ljust(name_w)
    for c in cols:
        total_row += str(col_totals[c]).rjust(col_w[c])
    total_row += str(tot_done).rjust(done_w) + str(tot_err).rjust(err_w)
    if show_case_addition:
        for label, key in CASE_ADD_SUBCOLS:
            total_row += str(case_totals[key]).rjust(case_w[label])
    lines.append(total_row)

    return "\n".join(lines)


def format_category_section(label, members, agent_data, assignments):
    """
    Returns (list_of_message_bodies, completed_total, error_total, case_add_total).
    A category can span two Slack messages — Task Type table, then Check Type table —
    since combining both in one message got long enough (teams like QC/MISC have up
    to 12 Check Type columns) to hit this workspace's apparent per-message length
    limit. Posting them separately keeps each one self-contained and well under it.
    """
    tag = CATEGORY_TAGS.get(label)
    tag_line = f"cc: <!subteam^{tag['usergroup']}> <@{tag['lead']}>" if tag else ""

    if not members:
        text = f"*{label}*\n_No members configured yet._"
        return [text + (f"\n{tag_line}" if tag_line else "")], 0, 0, 0

    idle_names = []
    unmatched = []

    matched_rows = []
    for member in members:
        d = assignments.get((label, member))
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

    if not active:
        body = "_No activity today._"
        if idle_names:
            body += f"\n_No activity: {', '.join(idle_names)}_"
        if unmatched:
            body += f"\n_No data found for: {', '.join(unmatched)}_"
        if tag_line:
            body += f"\n{tag_line}"
        return [body], tot_done, tot_err, tot_case

    # Table 1: agent-wise, Task Type as columns.
    task_table = build_agent_col_table(
        active, tot_done, tot_err, tot_case, show_case_addition,
        col_getter=lambda d: d["task_totals"],
    )
    msg1 = "*By Task Type*\n```\n" + task_table + "\n```"
    if idle_names:
        msg1 += f"\n_No activity: {', '.join(idle_names)}_"
    if unmatched:
        msg1 += f"\n_No data found for: {', '.join(unmatched)}_"

    # Table 2: same agent-wise layout, Check Type as columns instead (flattened
    # across all task types per agent) — same Total/Err/Case+, different bifurcation.
    check_table = build_agent_col_table(
        active, tot_done, tot_err, tot_case, show_case_addition,
        col_getter=agent_check_totals,
    )
    msg2 = "*By Check Type*\n```\n" + check_table + "\n```"
    if tag_line:
        msg2 += f"\n{tag_line}"

    return [msg1, msg2], tot_done, tot_err, tot_case


def format_channel_messages(channel_cfg, date_label, agent_data, assignments):
    """
    Returns a list of message strings — every category posts fully independently
    (its own header, its own tables, its own tag). No combined/cross-team summary —
    "Grading" and "Followups" (etc.) sharing a Slack channel is just where they're
    posted, not a reason to merge their numbers into a joint total.
    """
    categories = channel_cfg["categories"]
    messages = []
    for c in categories:
        bodies, _done, _err, _case_add = format_category_section(c["label"], c["members"], agent_data, assignments)
        header = f"\U0001f4ca *{c['label']} Team Daily Task Report — {date_label}*"
        messages.append(f"{header}\n\n{bodies[0]}")
        messages.extend(bodies[1:])

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
    """
    Split text into pieces on line boundaries, never mid-line, each under max_len.
    Fence-aware: if a split lands inside a ``` code block, closes it at the end of
    the outgoing chunk and reopens it at the start of the next, so a forced split
    never leaves a chunk with an unbalanced/broken code block.
    """
    if len(text) <= max_len:
        return [text]
    chunks, current = [], ""
    in_code_block = False
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_len and current:
            if in_code_block:
                chunks.append(current + "\n```")
                current = "```\n" + line
            else:
                chunks.append(current)
                current = line
        else:
            current = candidate
        if line.strip() == "```":
            in_code_block = not in_code_block
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
    print(f"Reporting on: {date_label}  (raw UTC calendar-day window {start_utc} -> {end_utc}, matches Redash Q3045)")

    print("Fetching Redash data...")
    completed_rows = fetch_completed(start_utc, end_utc)
    error_rows = fetch_errors(start_utc, end_utc)
    case_add_rows = fetch_case_additions(start_utc, end_utc)

    agent_data = build_agent_data(completed_rows, error_rows, case_add_rows)
    assignments = resolve_member_assignments(agent_data)

    for channel_cfg in CHANNELS:
        has_members = any(c["members"] for c in channel_cfg["categories"])
        if not has_members:
            print(f"Skipping channel {channel_cfg['channel_id']} — no members configured yet")
            continue

        messages = format_channel_messages(channel_cfg, date_label, agent_data, assignments)
        target_channel = TEST_CHANNEL_ID or channel_cfg["channel_id"]

        for message in messages:
            if TEST_CHANNEL_ID:
                message = f"_[TEST RUN — would normally post to {channel_cfg['channel_id']}]_\n" + message
            for ts in post_slack_message(target_channel, message):
                print(f"Posted to {target_channel} (ts={ts})")


if __name__ == "__main__":
    run_report()

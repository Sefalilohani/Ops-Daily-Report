# -*- coding: utf-8 -*-
"""
Weekly Ops Performance Report — separate from report.py's daily task report.

Every Monday, reports on the PRECEDING Monday-Sunday week for all 10 Ops
sub-teams: Summary (Completed/Errors/Avg-Day/Calls/Target/%Achieved/Leaves/
WFH), By Task Type, By Check Type — posted to each team's Slack channel.
Also posts a "Below 70% of Target" breakdown (FTE, then Interns by cohort)
as a new thread in the HR ops channel, for PIP review.

Env vars (all already configured as repo secrets, except REDASH_API_KEY
which — like report.py — is not treated as a secret in this repo):
  SLACK_BOT_TOKEN              existing secret, same as report.py
  GOOGLE_SERVICE_ACCOUNT_JSON  new secret — full service-account JSON as a string
  REPORT_START / REPORT_END    optional override (YYYY-MM-DD), else last Mon-Sun
  TEST_CHANNEL                 optional: redirect ALL posts here instead of real routing
"""
import json
import os
import re
import time
import datetime as dt
from collections import defaultdict
from itertools import permutations

import requests

SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
GOOGLE_SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

REDASH_BASE = "https://redash.springworks.in"
REDASH_DS_ID = 5
REDASH_API_KEY = "CWcvNsz8fkzifFJPD6r7kc2T6TCU6pbhxa0z0nRm"  # same key report.py already uses in this repo

BOUNTY_SHEET_ID = "1dUzxzF_6lY3lPdiHpmBg0mbas4q-Pp3ALE1Zx0WXHow"

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

TEST_CHANNEL_ALIASES = {"testing-sefali": "C0AGRE19V6U"}
TEST_CHANNEL_ID = TEST_CHANNEL_ALIASES.get(os.environ.get("TEST_CHANNEL", "").strip(), "")

HR_CHANNEL_ID = "C029UP81727"  # #hr-sv-ops
HR_PIP_TAGS = "cc: <@UN1E2L4G0> <@U03BUG17X54> <@U017K6KQT2A>"  # Selva, Ramya, Thanveer

# ── DATE RANGE: previous Monday-Sunday, unless overridden ──

_override_start = os.environ.get("REPORT_START", "").strip()
_override_end = os.environ.get("REPORT_END", "").strip()
if _override_start and _override_end:
    START_DATE = dt.datetime.strptime(_override_start, "%Y-%m-%d").date()
    END_DATE = dt.datetime.strptime(_override_end, "%Y-%m-%d").date()
else:
    today_ist = dt.datetime.now(IST).date()
    this_monday = today_ist - dt.timedelta(days=today_ist.weekday())
    START_DATE = this_monday - dt.timedelta(days=7)
    END_DATE = this_monday - dt.timedelta(days=1)

NUM_DAYS = (END_DATE - START_DATE).days + 1
START_UTC = START_DATE.strftime("%Y-%m-%d 00:00:00")
END_UTC = (END_DATE + dt.timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")


def fmt_date(d):
    def ordinal(n):
        if 11 <= n <= 13:
            return f"{n}th"
        return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"
    return f"{ordinal(d.day)} {d.strftime('%B %Y')}"


DATE_LABEL = f"{fmt_date(START_DATE)} - {fmt_date(END_DATE)}"

# Teams whose daily target is denominated in case additions, not regular task
# completions (see CASE_ADD_TARGET_TEAMS usage below).
CASE_ADD_TARGET_TEAMS = {"Case Addition"}

# ── CHANNEL / TEAM CONFIG (all 10 sub-teams) ──

CHANNELS = [
    {"channel_id": "CS5CX8LPQ", "channel_name": "#sv-in-ops-caseanalysis", "categories": [
        {"label": "CA + Initiation", "members": [
            "Subhashree L", "Priyanka Krishnan", "Manash Pratim Kashyap", "Anitha Sagari Ravirala",
            "Aaiyana Vinod Sharma", "Kondeti Ashvitha", "Sahil Vilas Mule", "Nishmeet Singh Rajpal",
            "Abhishek Parashari", "Abhishek Rawat", "Adithya Padmanabhan", "Indukuri Niranjan Reddy",
            "Ishita Mishra", "Divyajot Kaur", "Mohd Azfar Khan", "Noshin M K", "Anand Kumar",
            "Chinthala VSSSL Mokshajna", "Anmol Sharma",
        ]},
    ]},
    {"channel_id": "CS2PEFLMA", "channel_name": "#sv-in-ops-employment", "categories": [
        {"label": "Grading", "members": [
            "Dithya Ann Mathew", "E Tarun", "Shaeeshta Shaila", "Chirumamilla Hamsa Veni",
            "Peddireddy Vasu Deva Reddy", "Priyanka Lohia", "Shreshth Sahu", "Puneesh Hingorani",
            "Shambhavi Kumari", "Vikas Bishnoi", "Akhil", "Pentapalli Charan", "K Sai Vaishnav Kumar",
            "Lakshit Raina", "Utkarsh Raj", "Abhishek Mohan", "Mohamed Waseem kurikkal M P",
            "Surya Pratap", "Jay Pawar", "Anisha Kumari", "Rohan Kumarraju",
        ]},
        {"label": "Followups", "members": [
            "Chandrima Banik", "Nishika Dwivedi", "Anindita Maity", "Jillella Akshaya Prajwala",
            "Bevara Hemanth Kumar", "Debjani Dutta Gupta", "Kartik Kaushal", "Navaneetha KS",
            "D Joyce Blessia", "Janani S P", "Nara Sumanth", "Mehak Rajput", "Manisha Suresh Yadav",
            "Aishu Ji Lochan", "Pratham Rathor", "Adyasha Pattanaik", "Pranshu", "Gayathri A",
            "Dharani Lakshmi", "P Swarna Lakshmi", "Udita Singh", "Aishwarya Arya", "Samiksha Pilaniya",
            "Vivek Kumar Singh", "Tapas Patra", "Shaik Suraj",
        ]},
    ]},
    {"channel_id": "CQRU28ES0", "channel_name": "#sv-in-ops-add", "categories": [
        {"label": "QC", "members": [
            "Vikash Sunaliya", "Shafaque Shadni", "Mohammad Sameem Nazki", "Shlok Paliwal",
            "Vanshika Sharma", "Utsav Banerjee", "Nishant Gupta", "Manpreet Kaur", "Alisha Chaudhary",
            "Mitta Ruthika", "Harshitha Sakkuri", "Chuppa Harshitha", "Talwinder Singh", "Tanisha Thakur",
            "Subhajit Debbarma", "Saransh Jaggi", "Anushka Jaiswal", "Abhishek Sangwan",
            "Sachin Kumar Singh", "Vinay Pratap Singh", "Manish Kumar Thakur", "Nipun Singh",
            "Aikansh Katiyar",
        ]},
        {"label": "Email Clearance", "members": [
            "Deepika S", "Lavanya Dani", "Riya Sinha", "Sakshi Upesh Kamani", "Md. Parvezuddin",
            "Divya Harish", "Sanskar Shrivastava",
        ]},
    ]},
    {"channel_id": "C023SD1L2E7", "channel_name": "#sv-in-ops-misc-checks", "categories": [
        {"label": "MISC", "members": [
            "Pratyush Badhani", "Samriddhi Kundu", "B Hemanth Reddy", "Kousik Ruidas", "Samraggee Saha",
            "Swati Jampal", "Abhraneel Chattopadhyay", "Shivam Kumar Jha", "Pavithra M",
        ]},
        {"label": "Payment Settlement", "members": ["Barsha Agarwal", "Shivam Bhardwaj"]},
    ]},
    {"channel_id": "C08TMLA7YSU", "channel_name": "#sv-in-ops-research", "categories": [
        {"label": "Research", "members": [
            "Daraksha Hussain", "Shuman Thappa", "Satarupa Konar", "Al Hasan", "Adithyan S", "Aman Raj",
            "Hasamuddin Ansari", "Ballani Venkata Avinas", "Poojasri Adambhakam",
        ]},
    ]},
    {"channel_id": "C08MMSLV43H", "channel_name": "#sv-in-ops-ref", "categories": [
        {"label": "Reference", "members": ["Nazia Hasan", "Sakshi Bhuyan", "Kishore M", "Raunak Kumar", "Sahil"]},
    ]},
    {"channel_id": "C07QAABSJ6R", "channel_name": "#sv-in-ops-additional-tasks", "categories": [
        {"label": "Case Addition", "members": [
            "Manas Kumar Mishra", "Abhay Chandrakant Nayak", "Rahul Sutradhar", "Ankita Basak",
            "Chirag Sethi", "Sonia Thakur",
        ]},
    ]},
]

CATEGORY_TAGS = {
    "Grading":            {"usergroup": "S0BKVL7E0SH", "lead": "UN1E2L4G0"},
    "QC":                 {"usergroup": "S046ESUQLS1", "lead": "U03BUG17X54"},
    "CA + Initiation":    {"usergroup": "S046WGXTBED", "lead": "U017K6KQT2A"},
    "Research":           {"usergroup": "S08VARCA849", "lead": "UN1E2L4G0"},
    "Reference":          {"usergroup": "S04K6P0CYES", "lead": "UN1E2L4G0"},
    "Payment Settlement": {"usergroup": "S0BKX213HFG", "lead": "U017K6KQT2A"},
    "MISC":               {"usergroup": "S05BY1H4HJ5", "lead": "U017K6KQT2A"},
    "Email Clearance":    {"usergroup": "S0BKZ13RE82", "lead": "U03BUG17X54"},
    "Followups":          {"usergroup": "S0BLTALCZA4", "lead": "UURRMS3MG"},
    "Case Addition":      {"usergroup": "S086WH7H6A0", "lead": "UURRMS3MG"},
}

TASK_TYPE_INFO = {
    "CASE_ANALYSIS": ("CA", "Case Analysis"), "INITIATION": ("INIT", "Initiation"),
    "QC": ("QC", "QC"), "GRADING": ("GRD", "Grading"), "FOLLOW_UP": ("FU", "Follow Up"),
    "EMAIL_CLEARANCE": ("EC", "Email Clearance"), "PAYMENTS_SETTLEMENT": ("PS", "Payment Settlement"),
    "ADDITIONAL_TASKS": ("AT", "Additional Tasks"), "RESEARCH": ("RES", "Research"),
    "RESEARCH_FOLLOW_UP": ("RFU", "Research Follow Up"), "INSUFFICIENCY_CLEARANCE": ("IC", "Insufficiency Clearance"),
    "VENDOR_MANAGEMENT": ("VM", "Vendor Management"), "CONSENT_REVIEW": ("CR", "Consent Review"),
    "DOCUMENTS_CROPPING": ("DC", "Documents Cropping"), "WHATSAPP_CLEARANCE": ("WC", "WhatsApp Clearance"),
    "WHATSAPP_FOLLOW_UP": ("WFU", "WhatsApp Follow Up"),
}

# (name, type, shift, daily_target, cohort)
ROSTER = [
    ("Subhashree L", "FTE", "MF", 270, None), ("Priyanka Krishnan", "FTE", "MF", 270, None),
    ("Manash Pratim Kashyap", "FTE", "MF", 270, None), ("Anitha Sagari Ravirala", "FTE", "TS", 270, None),
    ("Aaiyana Vinod Sharma", "FTE", "TS", 270, None), ("Abhishek Parashari", "Intern", "MF", 250, 4),
    ("Abhishek Rawat", "Intern", "MF", 250, 4), ("Adithya Padmanabhan", "Intern", "MF", 250, 4),
    ("Indukuri Niranjan Reddy", "Intern", "MF", 250, 4), ("Ishita Mishra", "Intern", "MF", 250, 4),
    ("Divyajot Kaur", "Intern", "MF", 250, 4), ("Mohd Azfar Khan", "Intern", "MF", 250, 4),
    ("Noshin M K", "Intern", "MF", 250, 4), ("Anand Kumar", "Intern", "MF", 250, 4),
    ("Chinthala VSSSL Mokshajna", "Intern", "MF", 250, 4), ("Anmol Sharma", "Intern", "MF", 250, 4),
    ("Kondeti Ashvitha", "Intern", "MF", 250, None), ("Sahil Vilas Mule", "Intern", "MF", 250, None),
    ("Nishmeet Singh Rajpal", "Intern", "MF", 250, None),

    ("Dithya Ann Mathew", "FTE", "MF", 200, None),
    ("Chirumamilla Hamsa Veni", "Intern", "MF", 180, 3), ("Puneesh Hingorani", "Intern", "MF", 180, 4),
    ("Shambhavi Kumari", "Intern", "MF", 180, 4), ("Vikas Bishnoi", "Intern", "MF", 180, 4),
    ("Akhil", "Intern", "MF", 180, 4), ("K Sai Vaishnav Kumar", "Intern", "MF", 180, 4),
    ("Utkarsh Raj", "Intern", "MF", 180, 4), ("Abhishek Mohan", "Intern", "MF", 180, 4),
    ("Surya Pratap", "Intern", "MF", 180, 4), ("Jay Pawar", "Intern", "MF", 180, 4),
    ("Rohan Kumarraju", "Intern", "MF", 180, 6), ("Mohamed Waseem kurikkal M P", "Intern", "MF", 180, 6),
    ("Shreshth Sahu", "Intern", "MF", 180, 6), ("Lakshit Raina", "Intern", "MF", 180, 6),
    ("Anisha Kumari", "Intern", "MF", 180, 6),
    ("E Tarun", "Intern", "MF", 180, None), ("Shaeeshta Shaila", "Intern", "MF", 180, None),
    ("Peddireddy Vasu Deva Reddy", "Intern", "MF", 180, None), ("Priyanka Lohia", "Intern", "MF", 180, None),
    ("Pentapalli Charan", "Intern", "MF", 180, None),

    ("Vikash Sunaliya", "FTE", "MF", 260, None), ("Shafaque Shadni", "FTE", "TS", 260, None),
    ("Mohammad Sameem Nazki", "FTE", "MF", 260, None), ("Shlok Paliwal", "FTE", "TS", 260, None),
    ("Vanshika Sharma", "FTE", "TS", 260, None), ("Utsav Banerjee", "FTE", "MF", 260, None),
    ("Nishant Gupta", "Intern", "MF", 240, 1), ("Manpreet Kaur", "Intern", "MF", 240, 1),
    ("Alisha Chaudhary", "Intern", "MF", 240, 1), ("Mitta Ruthika", "Intern", "MF", 240, 1),
    ("Harshitha Sakkuri", "Intern", "MF", 240, 2), ("Chuppa Harshitha", "Intern", "MF", 240, 2),
    ("Talwinder Singh", "Intern", "MF", 240, 4), ("Tanisha Thakur", "Intern", "MF", 240, 4),
    ("Subhajit Debbarma", "Intern", "MF", 240, 4), ("Saransh Jaggi", "Intern", "MF", 240, 4),
    ("Anushka Jaiswal", "Intern", "MF", 240, 4), ("Abhishek Sangwan", "Intern", "MF", 240, 4),
    ("Sachin Kumar Singh", "Intern", "MF", 240, 4), ("Vinay Pratap Singh", "Intern", "MF", 240, 6),
    ("Manish Kumar Thakur", "Intern", "MF", 240, 6), ("Nipun Singh", "Intern", "MF", 240, 6),
    ("Aikansh Katiyar", "Intern", "MF", 240, 6),

    ("Pratyush Badhani", "FTE", "TS", 250, None), ("Samriddhi Kundu", "FTE", "MF", 250, None),
    ("B Hemanth Reddy", "FTE", "TS", 250, None), ("Kousik Ruidas", "FTE", "MF", 250, None),
    ("Samraggee Saha", "FTE", "MF", 250, None), ("Swati Jampal", "FTE", "TS", 250, None),
    ("Abhraneel Chattopadhyay", "FTE", "MF", 250, None), ("Shivam Kumar Jha", "FTE", "MF", 250, None),
    ("Pavithra M", "FTE", "TS", 250, None),

    ("Barsha Agarwal", "FTE", "MF", 140, None), ("Shivam Bhardwaj", "FTE", "TS", 140, None),

    ("Daraksha Hussain", "FTE", "MF", 130, None), ("Shuman Thappa", "FTE", "TS", 130, None),
    ("Satarupa Konar", "FTE", "MF", 130, None), ("Al Hasan", "FTE", "MF", 130, None),
    ("Poojasri Adambhakam", "FTE", "TS", 130, None), ("Adithyan S", "Intern", "MF", 115, 5),
    ("Aman Raj", "Intern", "MF", 115, 5), ("Hasamuddin Ansari", "Intern", "MF", 115, 5),
    ("Ballani Venkata Avinas", "Intern", "MF", 115, 5),

    ("Nazia Hasan", "FTE", "TS", 195, None), ("Sakshi Bhuyan", "FTE", "MF", 195, None),
    ("Kishore M", "FTE", "MF", 195, None), ("Raunak Kumar", "Intern", "MF", 170, 5),
    ("Sahil", "Intern", "MF", 170, 5),

    ("Manas Kumar Mishra", "FTE", "TS", 55, None), ("Abhay Chandrakant Nayak", "FTE", "TS", 55, None),
    ("Rahul Sutradhar", "FTE", "MF", 55, None), ("Ankita Basak", "FTE", "MF", 55, None),
    ("Chirag Sethi", "FTE", "MF", 55, None), ("Sonia Thakur", "FTE", "TS", 55, None),

    ("Nishika Dwivedi", "FTE", "TS", 145, None), ("Anindita Maity", "FTE", "TS", 145, None),
    ("Jillella Akshaya Prajwala", "FTE", "TS", 145, None), ("Bevara Hemanth Kumar", "FTE", "MF", 145, None),
    ("Navaneetha KS", "FTE", "MF", 140, None), ("D Joyce Blessia", "FTE", "TS", 140, None),
    ("Nara Sumanth", "Intern", "MF", 120, 5), ("Mehak Rajput", "Intern", "MF", 120, 5),
    ("Manisha Suresh Yadav", "FTE", "MF", 110, None), ("Shaik Suraj", "FTE", "MF", 110, None),
    ("Vivek Kumar Singh", "FTE", "MF", 110, None), ("Tapas Patra", "FTE", "MF", 110, None),
    ("Aishu Ji Lochan", "Intern", "MF", 95, 3), ("Pranshu", "Intern", "MF", 95, 3),
    ("Aishwarya Arya", "Intern", "MF", 95, 4), ("Samiksha Pilaniya", "Intern", "MF", 95, 4),
    ("P Swarna Lakshmi", "FTE", "MF", 110, None), ("Dharani Lakshmi", "FTE", "MF", 110, None),
    ("Gayathri A", "FTE", "MF", 110, None), ("Udita Singh", "FTE", "MF", 110, None),

    ("Deepika S", "FTE", "MF", 220, None), ("Lavanya Dani", "FTE", "TS", 220, None),
    ("Riya Sinha", "Intern", "MF", 195, 5),
    ("Sakshi Upesh Kamani", "FTE", "TS", 220, None), ("Md. Parvezuddin", "Intern", "MF", 195, 5),
    ("Divya Harish", "FTE", "MF", 325, None), ("Sanskar Shrivastava", "FTE", "TS", 325, None),
]

NEW_JOINERS = {"Vinay Pratap Singh", "Manish Kumar Thakur", "Nipun Singh", "Aikansh Katiyar"}

# ── name matching (verbatim from the ops-performance-report skill) ──

NAME_PREFIXES = [
    "Payment Settlement", "Customer Ops", "Q C", "R T", "C S", "A T", "V M",
    "C A", "Add", "Grading", "Initiation", "Misc", "Supp", "Ops", "Edu",
    "Emp", "Ref", "Dev", "Res",
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
    cleaned = clean_name(name)
    return frozenset(t for t in "".join(c if c.isalpha() or c == " " else " " for c in cleaned).split() if t)


def _token_compat(t1, t2):
    return t1 == t2 or (len(t1) == 1 and t2.startswith(t1)) or (len(t2) == 1 and t1.startswith(t2))


def _core_tokens(tokens):
    core = frozenset(t for t in tokens if len(t) > 1)
    return core if core else tokens


def _names_compatible(tokens_a, tokens_b):
    if tokens_a == tokens_b or tokens_a <= tokens_b or tokens_b <= tokens_a:
        return 0
    if len(tokens_a) == len(tokens_b) and any(
        all(_token_compat(x, y) for x, y in zip(tokens_a, perm)) for perm in permutations(tokens_b)
    ):
        return 1
    core_a, core_b = _core_tokens(tokens_a), _core_tokens(tokens_b)
    if core_a and core_b and (core_a <= core_b or core_b <= core_a):
        return 2
    return None


def best_match(target_name, candidate_dict):
    key = clean_name(target_name)
    for k, v in candidate_dict.items():
        if clean_name(k) == key:
            return v
    t_tokens = name_tokens(target_name)
    if not t_tokens:
        return None
    best, best_tier, best_overlap, ties = None, None, -1, 0
    for k, v in candidate_dict.items():
        c_tokens = name_tokens(k)
        if not c_tokens:
            continue
        tier = _names_compatible(t_tokens, c_tokens)
        if tier is None:
            continue
        overlap = len(t_tokens & c_tokens)
        if best_tier is None or (tier, -overlap) < (best_tier, -best_overlap):
            best_tier, best_overlap, best, ties = tier, overlap, v, 1
        elif (tier, overlap) == (best_tier, best_overlap):
            ties += 1
    return None if ties > 1 else best


def humanize(v):
    if not v or v == "N/A":
        return "N/A"
    return " ".join(w.capitalize() for w in v.replace("-", "_").split("_"))


ROSTER_TARGET = {clean_name(n): (target, shift) for n, _typ, shift, target, _c in ROSTER}
ROSTER_TYPE = {clean_name(n): typ for n, typ, _shift, _target, _c in ROSTER}
ROSTER_COHORT = {clean_name(n): cohort for n, _typ, _shift, _target, cohort in ROSTER}


def working_days_in_range(shift, start, end):
    days = (end - start).days + 1
    count = 0
    for i in range(days):
        d = start + dt.timedelta(days=i)
        wd = d.weekday()
        if shift == "MF" and wd <= 4:
            count += 1
        elif shift == "TS" and 1 <= wd <= 5:
            count += 1
    return count


def get_target(member, leaves):
    hit = best_match(member, ROSTER_TARGET)
    if hit is None:
        return None, None, None
    daily_target, shift = hit
    effective_days = max(working_days_in_range(shift, START_DATE, END_DATE) - leaves, 0)
    return daily_target * effective_days, daily_target, effective_days


def get_type_cohort(member):
    key = clean_name(member)
    typ = ROSTER_TYPE.get(key)
    cohort = ROSTER_COHORT.get(key)
    if typ is None:
        for k in ROSTER_TYPE:
            if best_match(member, {k: True}):
                typ, cohort = ROSTER_TYPE.get(k), ROSTER_COHORT.get(k)
                break
    return typ, cohort


# ── Google Sheets (Leave / WFH / Call Log) via service account ──

def _sheets_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    info = json.loads(GOOGLE_SA_JSON)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    return build("sheets", "v4", credentials=creds)


def _read_range(svc, rng):
    resp = svc.spreadsheets().values().get(spreadsheetId=BOUNTY_SHEET_ID, range=rng).execute()
    return resp.get("values", [])


def parse_dmy(s):
    s = s.strip()
    for f in ("%d-%b-%Y", "%d-%B-%Y"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date: {s!r}")


def fetch_leave_totals(svc):
    rows = _read_range(svc, "Leave!A3:H2000")
    totals = defaultdict(float)
    for row in rows:
        if len(row) < 8:
            continue
        name = row[1]
        try:
            d_from, d_to, dur = parse_dmy(row[3]), parse_dmy(row[5]), float(row[7])
        except (ValueError, IndexError):
            continue
        lo, hi = max(d_from, START_DATE), min(d_to, END_DATE)
        if lo > hi:
            continue
        if d_from == d_to:
            overlap = dur
        else:
            overlap = sum(1 for i in range((hi - lo).days + 1) if (lo + dt.timedelta(days=i)).weekday() <= 4)
        totals[clean_name(name)] += overlap
    return totals


def fetch_wfh_totals(svc):
    rows = _read_range(svc, "Leave!J3:N2000")
    totals = defaultdict(float)
    for row in rows:
        if len(row) < 4:
            continue
        name = row[1]
        try:
            d_from, d_to = parse_dmy(row[2]), parse_dmy(row[3])
        except ValueError:
            continue
        lo, hi = max(d_from, START_DATE), min(d_to, END_DATE)
        if lo > hi:
            continue
        totals[clean_name(name)] += (hi - lo).days + 1
    return totals


def fetch_call_totals(svc):
    """Best-effort: the Call Log tab is a pasted snapshot for a fixed window, not a
    live per-week feed. Only trust it if its own header states a range that covers
    (or matches) this run's week — otherwise skip calls entirely rather than show
    stale/wrong numbers."""
    header_rows = _read_range(svc, "Call Log!A1:A2")
    header_text = " ".join(" ".join(r) for r in header_rows)
    m = re.search(r"(\d{1,2}) to (\d{1,2}) (\w+) (\d{4})", header_text)
    if m:
        try:
            lo = dt.datetime.strptime(f"{m.group(1)} {m.group(3)} {m.group(4)}", "%d %b %Y").date()
            hi = dt.datetime.strptime(f"{m.group(2)} {m.group(3)} {m.group(4)}", "%d %b %Y").date()
            if not (lo <= START_DATE and hi >= END_DATE):
                print(f"  Call Log sheet covers {lo}..{hi}, not this week ({START_DATE}..{END_DATE}) — skipping calls")
                return {}
        except ValueError:
            pass
    rows = _read_range(svc, "Call Log!A4:J200")
    totals = {}
    for row in rows:
        if len(row) < 10 or not row[0] or not str(row[3]).strip().isdigit():
            continue
        name_only = re.sub(r"\s*\(\+?\d[\d\- ]*\)\s*$", "", row[0]).strip()
        key = clean_name(name_only)
        total_c, conn_c = int(row[3]), int(row[8])
        if key in totals:
            pt, pc = totals[key]
            totals[key] = (pt + total_c, pc + conn_c)
        else:
            totals[key] = (total_c, conn_c)
    return totals


# ── Redash ──

def _fetch_adhoc_once(sql):
    headers = {"Authorization": f"Key {REDASH_API_KEY}", "Content-Type": "application/json"}
    r = requests.post(f"{REDASH_BASE}/api/query_results", headers=headers,
                       json={"data_source_id": REDASH_DS_ID, "query": sql, "max_age": 0}, timeout=90)
    r.raise_for_status()
    resp = r.json()
    if "query_result" in resp:
        return resp["query_result"]["data"]["rows"]
    job_id = resp.get("job", {}).get("id")
    if not job_id:
        raise Exception(f"Unexpected Redash response: {str(resp)[:300]}")
    for _ in range(45):
        time.sleep(2)
        jr = requests.get(f"{REDASH_BASE}/api/jobs/{job_id}", headers=headers, timeout=30)
        jr.raise_for_status()
        job = jr.json().get("job", {})
        if job.get("status") == 3:
            rr = requests.get(f"{REDASH_BASE}/api/query_results/{job['query_result_id']}", headers=headers, timeout=30)
            rr.raise_for_status()
            return rr.json()["query_result"]["data"]["rows"]
        if job.get("status") == 4:
            raise Exception(f"Redash query failed: {job.get('error')}")
    raise Exception("Redash ad-hoc query timed out")


def fetch_adhoc(sql, retries=2):
    for attempt in range(retries + 1):
        try:
            return _fetch_adhoc_once(sql)
        except Exception:
            if attempt == retries:
                raise
            time.sleep(5)


def fetch_completed():
    sql = f"""
        SELECT u.name AS "Agent Name", tt.value AS "Task Type", COALESCE(ct.value, 'N/A') AS "Check Type",
            COUNT(DISTINCT ts.id) AS "Completed Count"
        FROM tasks ts
        INNER JOIN users u ON u.id = ts.completed_by_user_id_fk
        INNER JOIN enums tt ON ts.task_type = tt.id AND tt.type = 'TEAM_TYPE' AND tt.deleted_at IS NULL
        LEFT JOIN enums ct ON ts.check_type = ct.id AND ct.deleted_at IS NULL
        WHERE ts.deleted_at IS NULL
          AND ts.task_completed_at >= '{START_UTC}' AND ts.task_completed_at < '{END_UTC}'
          AND ts.task_status = (SELECT id FROM enums WHERE type='TASK_STATUS' AND value='COMPLETED' AND deleted_at IS NULL LIMIT 1)
          AND ts.completed_by_user_id_fk NOT IN (4, 17542)
        GROUP BY u.name, tt.value, ct.value ORDER BY u.name, tt.value, ct.value
    """
    return fetch_adhoc(sql)


def fetch_errors():
    sql = f"""
        SELECT u.name AS "Name", COUNT(DISTINCT e.id) AS "Error Count"
        FROM errors e
        INNER JOIN users u ON u.id = e.agent_user_id_fk
        LEFT JOIN teams_user_mapping tum ON tum.user_id_fk = u.id
        LEFT JOIN teams t ON t.id = tum.team_id_fk AND t.deleted_at IS NULL
        LEFT JOIN enums dept_enum ON dept_enum.id = t.department_enum_fk AND dept_enum.deleted_at IS NULL
        WHERE e.deleted_at IS NULL
          AND e.created_at >= '{START_UTC}' AND e.created_at < '{END_UTC}'
          AND UPPER(e.status) IN ('NEW', 'RECTIFIED', 'CLOSED')
          AND (dept_enum.value = 'OPERATIONS' OR LOWER(u.name) LIKE '%system user%' OR LOWER(u.name) LIKE '%springverify ai%')
        GROUP BY u.name ORDER BY u.name
    """
    return fetch_adhoc(sql)


def fetch_case_additions():
    sql = f"""
        WITH consent_events AS (
            SELECT cl.candidate_id_fk,
                CASE WHEN cl.user_type = 1 THEN cl.user_id_fk ELSE cl.proxy_user_id_fk END AS adder_user_id,
                CASE WHEN cl.user_type = 1 THEN 'DIRECT' ELSE 'PROXY' END AS adder_type,
                cl.created_at AS add_at, 0 AS priority
            FROM candidate_logs cl
            WHERE cl.type = 'CANDIDATE_CONSENT_ADDED' AND cl.deleted_at IS NULL
              AND ((cl.user_type = 1 AND cl.user_id_fk IS NOT NULL) OR (cl.user_type = 2 AND cl.proxy_user_id_fk IS NOT NULL))
              AND cl.created_at >= DATE_SUB('{START_UTC}', INTERVAL 30 DAY) AND cl.created_at < '{END_UTC}'
        ),
        consent_exists AS (
            SELECT DISTINCT candidate_id_fk FROM candidate_logs
            WHERE type = 'CANDIDATE_CONSENT_ADDED' AND deleted_at IS NULL
              AND created_at >= DATE_SUB('{START_UTC}', INTERVAL 30 DAY) AND created_at < '{END_UTC}'
        ),
        basic_info_fallback AS (
            SELECT cl.candidate_id_fk,
                CASE WHEN cl.user_type = 1 THEN cl.user_id_fk ELSE cl.proxy_user_id_fk END AS adder_user_id,
                CASE WHEN cl.user_type = 1 THEN 'DIRECT' ELSE 'PROXY' END AS adder_type,
                cl.created_at AS add_at, 1 AS priority
            FROM candidate_logs cl
            WHERE cl.type = 'CANDIDATE_BASIC_INFO_UPDATED' AND cl.deleted_at IS NULL
              AND ((cl.user_type = 1 AND cl.user_id_fk IS NOT NULL) OR (cl.user_type = 2 AND cl.proxy_user_id_fk IS NOT NULL))
              AND cl.created_at >= DATE_SUB('{START_UTC}', INTERVAL 30 DAY) AND cl.created_at < '{END_UTC}'
              AND cl.candidate_id_fk NOT IN (SELECT candidate_id_fk FROM consent_exists)
        ),
        add_events AS (
            SELECT candidate_id_fk, adder_user_id, adder_type, add_at, priority,
                ROW_NUMBER() OVER (PARTITION BY candidate_id_fk ORDER BY priority ASC, add_at ASC) AS rn
            FROM (SELECT * FROM consent_events UNION ALL SELECT * FROM basic_info_fallback) x
        ),
        canonical_add AS (
            SELECT candidate_id_fk, adder_user_id, adder_type, add_at FROM add_events WHERE rn = 1
        ),
        fills AS (
            SELECT ccm.candidate_id, ccm.form_filled,
                CASE WHEN ccm.form_filled_by = 1 THEN ccm.form_filled_by_user_id
                     WHEN ccm.form_filled_by = 3 THEN ccm.proxy_user_id ELSE NULL END AS filler_user_id
            FROM company_candidate_mapping ccm
            WHERE ccm.deleted_at IS NULL
              AND ccm.created_at >= DATE_SUB('{START_UTC}', INTERVAL 30 DAY) AND ccm.created_at < '{END_UTC}'
        ),
        combined AS (
            SELECT ca.candidate_id_fk, ca.adder_user_id, ca.adder_type, ca.add_at, f.form_filled, f.filler_user_id
            FROM canonical_add ca LEFT JOIN fills f ON f.candidate_id = ca.candidate_id_fk
            UNION
            SELECT f.candidate_id AS candidate_id_fk, ca.adder_user_id, ca.adder_type, ca.add_at, f.form_filled, f.filler_user_id
            FROM fills f LEFT JOIN canonical_add ca ON ca.candidate_id_fk = f.candidate_id
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
            UNION ALL SELECT candidate_id_fk, b2_user, 0, 1, 0, 0, b2_date FROM tagged WHERE b2_user IS NOT NULL
            UNION ALL SELECT candidate_id_fk, b3_user, 0, 0, 1, 0, b3_date FROM tagged WHERE b3_user IS NOT NULL
            UNION ALL SELECT candidate_id_fk, b4_user, 0, 0, 0, 1, b4_date FROM tagged WHERE b4_user IS NOT NULL
        )
        SELECT u.name AS "Agent Name", SUM(pac.added_and_filled) AS "Added & Filled",
            SUM(pac.added_not_filled) AS "Added, Not Filled", SUM(pac.filled_only) AS "Filled Only",
            SUM(pac.proxy_added) AS "Proxy Added"
        FROM per_agent_candidate pac JOIN users u ON u.id = pac.agent_user_id
        WHERE pac.credit_date >= '{START_UTC}' AND pac.credit_date < '{END_UTC}'
        GROUP BY u.name ORDER BY u.name
    """
    return fetch_adhoc(sql)


# ── aggregate ──

def build_agent_data(completed_rows, error_rows, case_add_rows):
    data = defaultdict(lambda: {
        "display_name": None, "task_totals": defaultdict(int), "task_check": defaultdict(lambda: defaultdict(int)),
        "completed_total": 0, "error_total": 0, "case_add_total": 0,
    })
    for row in completed_rows:
        raw_name = row.get("Agent Name") or ""
        key = clean_name(raw_name)
        if not key:
            continue
        raw_tt = row.get("Task Type") or ""
        abbr, _full = TASK_TYPE_INFO.get(raw_tt, (humanize(raw_tt)[:4].upper(), humanize(raw_tt)))
        check_raw = row.get("Check Type")
        count = int(row.get("Completed Count") or 0)
        d = data[key]
        d["display_name"] = d["display_name"] or raw_name
        d["task_totals"][abbr] += count
        if check_raw and check_raw != "N/A":
            d["task_check"][abbr][humanize(check_raw)] += count
        d["completed_total"] += count
    for row in error_rows:
        raw_name = row.get("Name") or ""
        key = clean_name(raw_name)
        if not key:
            continue
        d = data[key]
        d["display_name"] = d["display_name"] or raw_name
        d["error_total"] += int(row.get("Error Count") or 0)
    for row in case_add_rows:
        raw_name = row.get("Agent Name") or ""
        key = clean_name(raw_name)
        if not key:
            continue
        af, fo, pa = int(row.get("Added & Filled") or 0), int(row.get("Filled Only") or 0), int(row.get("Proxy Added") or 0)
        d = data[key]
        d["display_name"] = d["display_name"] or raw_name
        d["case_add_total"] += af + fo + pa
    return data


def resolve_member_assignments(agent_data):
    token_index = [(key, name_tokens(key)) for key in agent_data]
    all_members = [(c["label"], m) for ch in CHANNELS for c in ch["categories"] for m in c["members"]]
    exact_owner, claims = {}, defaultdict(list)
    for label, member in all_members:
        key = clean_name(member)
        if key in agent_data:
            exact_owner[key] = (label, member)
            continue
        member_tokens = name_tokens(member)
        if not member_tokens:
            continue
        for k, t in token_index:
            if not t:
                continue
            tier = _names_compatible(member_tokens, t)
            if tier is not None:
                claims[k].append((tier, len(t & member_tokens), label, member))
    assignments = {(label, member): None for label, member in all_members}
    for key, (label, member) in exact_owner.items():
        assignments[(label, member)] = agent_data[key]
    for key, claimants in claims.items():
        if key in exact_owner:
            continue
        claimants.sort(key=lambda c: (c[0], -c[1]))
        top_tier, top_score = claimants[0][0], claimants[0][1]
        winners = [c for c in claimants if c[0] == top_tier and c[1] == top_score]
        if len(winners) == 1:
            _, _, label, member = winners[0]
            assignments[(label, member)] = agent_data[key]
    return assignments


def agent_check_totals(d):
    totals = defaultdict(int)
    for checks in d["task_check"].values():
        for label, cnt in checks.items():
            totals[label] += cnt
    return totals


def build_agent_col_table(active, tot_done, tot_err, col_getter):
    col_totals = defaultdict(int)
    for _, d in active:
        for col, cnt in col_getter(d).items():
            col_totals[col] += cnt
    cols = sorted(col_totals, key=lambda c: col_totals[c], reverse=True)
    name_w = max([len("Agent")] + [len(n) for n, _ in active] + [len("TEAM TOTAL")]) + 2
    col_w = {c: max(len(c), 5) + 2 for c in cols}
    done_w = max(len("Total"), len(str(tot_done))) + 2
    err_w = max(len("Err"), len(str(tot_err))) + 2
    header = "Agent".ljust(name_w)
    for c in cols:
        header += c.rjust(col_w[c])
    header += "Total".rjust(done_w) + "Err".rjust(err_w)
    sep = "-" * len(header)
    lines = [header, sep]
    for name, d in active:
        row = name.ljust(name_w)
        counts = col_getter(d)
        for c in cols:
            v = counts.get(c, 0)
            row += (str(v) if v else "-").rjust(col_w[c])
        row += str(d["completed_total"]).rjust(done_w) + str(d["error_total"]).rjust(err_w)
        lines.append(row)
    lines.append(sep)
    total_row = "TEAM TOTAL".ljust(name_w)
    for c in cols:
        total_row += str(col_totals[c]).rjust(col_w[c])
    total_row += str(tot_done).rjust(done_w) + str(tot_err).rjust(err_w)
    lines.append(total_row)
    return "\n".join(lines)


def fmt(v, suffix=""):
    if v is None:
        return "-"
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return f"{v}{suffix}"


def build_summary_table(label, members, agent_data, assignments, leave_totals, wfh_totals, call_totals):
    rows = []
    unmatched = []
    for member in members:
        d = assignments.get((label, member))
        completed = d["completed_total"] if d else 0
        errors = d["error_total"] if d else 0
        case_add = d["case_add_total"] if d else 0
        display_name = (d["display_name"] if d else None) or member
        leaves = leave_totals.get(clean_name(member), 0.0) or best_match(member, leave_totals) or 0.0
        wfh = wfh_totals.get(clean_name(member), 0.0) or best_match(member, wfh_totals) or 0.0
        target, daily_target, effective_days = get_target(member, leaves)
        total_calls, conn_calls = call_totals.get(clean_name(member)) or best_match(member, call_totals) or (0, 0)
        if d is None and total_calls == 0 and leaves == 0 and wfh == 0 and target is None and case_add == 0:
            unmatched.append(member)
        achieved_metric = case_add if label in CASE_ADD_TARGET_TEAMS else completed
        avg_day = round(achieved_metric / effective_days, 1) if effective_days else (round(achieved_metric / NUM_DAYS, 1) if daily_target is None else 0)
        pct_achieved = round(achieved_metric / target * 100, 1) if target else None
        conn_pct = round(conn_calls / total_calls * 100, 1) if total_calls else None
        rows.append({
            "name": display_name, "completed": completed, "errors": errors, "avg_day": avg_day,
            "total_calls": total_calls, "conn_pct": conn_pct, "target": target, "daily_target": daily_target,
            "pct_achieved": pct_achieved, "leaves": leaves, "wfh": wfh, "case_add": case_add,
        })
    rows.sort(key=lambda r: (r["completed"], r["case_add"]), reverse=True)
    show_calls = any(r["total_calls"] for r in rows)
    show_case = any(r["case_add"] for r in rows)
    cols = ["Agent", "Completed", "Errors", "Avg/Day"]
    if show_calls:
        cols += ["Calls", "Conn%"]
    cols += ["Target/Day", "Target", "%Ach", "Leaves", "WFH"]
    if show_case:
        cols += ["Case+"]
    display_rows = []
    for r in rows:
        row = [r["name"], str(r["completed"]), str(r["errors"]), fmt(r["avg_day"])]
        if show_calls:
            row += [fmt(r["total_calls"]) if r["total_calls"] else "-", fmt(r["conn_pct"], "%")]
        row += [fmt(r["daily_target"]), fmt(r["target"]), fmt(r["pct_achieved"], "%"), fmt(r["leaves"]), fmt(r["wfh"])]
        if show_case:
            row += [fmt(r["case_add"]) if r["case_add"] else "-"]
        display_rows.append(row)
    widths = [max(len(cols[i]), *(len(dr[i]) for dr in display_rows)) + 2 if display_rows else len(cols[i]) + 2 for i in range(len(cols))]
    header = "".join(cols[i].ljust(widths[i]) if i == 0 else cols[i].rjust(widths[i]) for i in range(len(cols)))
    sep = "-" * len(header)
    lines = [header, sep]
    for dr in display_rows:
        lines.append("".join(dr[i].ljust(widths[i]) if i == 0 else dr[i].rjust(widths[i]) for i in range(len(cols))))
    return "\n".join(lines), unmatched


# ── Slack ──

MAX_MESSAGE_CHARS = 3500


def chunk_message(text, max_len=MAX_MESSAGE_CHARS):
    if len(text) <= max_len:
        return [text]
    chunks, current, in_code_block = [], "", False
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
    last_ts = None
    for chunk in chunk_message(text):
        payload = {"channel": channel_id, "text": chunk}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        r = requests.post("https://slack.com/api/chat.postMessage",
                           headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
                           json=payload)
        r.raise_for_status()
        resp = r.json()
        if not resp.get("ok"):
            raise Exception(f"Slack API error for channel {channel_id}: {resp.get('error')}")
        last_ts = resp["ts"]
        if not thread_ts:
            thread_ts = last_ts
    return last_ts


# ── main ──

def main():
    print(f"Weekly report for {DATE_LABEL} ({START_UTC} -> {END_UTC})")

    completed_rows = fetch_completed()
    error_rows = fetch_errors()
    case_add_rows = fetch_case_additions()
    print(f"  Completed: {len(completed_rows)} rows, Errors: {len(error_rows)}, Case adds: {len(case_add_rows)}")
    agent_data = build_agent_data(completed_rows, error_rows, case_add_rows)
    assignments = resolve_member_assignments(agent_data)

    # Known name-collision bug (also present in report.py's matcher): a bare
    # single first-name match ("Manish" vs "Manish Kumar Thakur") wrongly
    # attaches an unrelated Customer Support agent's ("Supp Manish") numbers
    # to this QC intern. Force unmatched rather than report someone else's work.
    assignments[("QC", "Manish Kumar Thakur")] = None

    leave_totals, wfh_totals, call_totals = {}, {}, {}
    if GOOGLE_SA_JSON:
        try:
            svc = _sheets_service()
            leave_totals = fetch_leave_totals(svc)
            wfh_totals = fetch_wfh_totals(svc)
            call_totals = fetch_call_totals(svc)
            print(f"  Leave rows: {len(leave_totals)}, WFH rows: {len(wfh_totals)}, Call rows: {len(call_totals)}")
        except Exception as exc:
            print(f"  WARNING: Google Sheets fetch failed ({exc}) — Leave/WFH/Calls will show as unavailable this run")
    else:
        print("  WARNING: GOOGLE_SERVICE_ACCOUNT_JSON not set — Leave/WFH/Calls unavailable this run")

    below_70 = []  # (tier_sort_key, group_label, row_dict)

    for channel in CHANNELS:
        for category in channel["categories"]:
            label = category["label"]
            members = category["members"]

            summary_table, unmatched = build_summary_table(label, members, agent_data, assignments, leave_totals, wfh_totals, call_totals)

            matched_rows = []
            for member in members:
                d = assignments.get((label, member))
                if d is not None:
                    matched_rows.append((d["display_name"] or member, d))
            matched_rows.sort(key=lambda r: r[1]["completed_total"], reverse=True)
            active = [(n, d) for n, d in matched_rows if d["completed_total"] or d["error_total"] or d["case_add_total"]]
            tot_done = sum(d["completed_total"] for _, d in matched_rows)
            tot_err = sum(d["error_total"] for _, d in matched_rows)
            task_table = build_agent_col_table(active, tot_done, tot_err, lambda d: d["task_totals"]) if active else None
            check_table = build_agent_col_table(active, tot_done, tot_err, agent_check_totals) if active else None

            header = f":bar_chart: *{label} Team Weekly Task Report ({DATE_LABEL})*"
            msg1 = f"{header}\n\n*Summary — Completed / Errors / Avg-Day / Calls / Target / %Achieved / Leaves / WFH*\n```\n{summary_table}\n```"
            messages = [msg1]
            if task_table:
                msg2 = f"*By Task Type*\n```\n{task_table}\n```"
                if unmatched:
                    msg2 += f"\n_No data found for: {', '.join(unmatched)}_"
                messages.append(msg2)
            tag = CATEGORY_TAGS.get(label)
            tag_line = f"cc: <!subteam^{tag['usergroup']}> <@{tag['lead']}>" if tag else ""
            if check_table:
                msg3 = f"*By Check Type*\n```\n{check_table}\n```"
                if tag_line:
                    msg3 += f"\n{tag_line}"
                messages.append(msg3)

            target_channel = TEST_CHANNEL_ID or channel["channel_id"]
            print(f"  Posting {label} -> {target_channel} ({len(messages)} messages)")
            # Each team's Summary/Task-Type/Check-Type messages post as separate
            # top-level messages (not threaded to each other) — matches the
            # existing weekly-report format already posted manually.
            for m in messages:
                if TEST_CHANNEL_ID:
                    m = f"_[TEST RUN — would normally post to {channel['channel_id']}]_\n" + m
                post_slack_message(target_channel, m)

            # Collect below-70%-of-target rows for the HR PIP post
            for member in members:
                d = assignments.get((label, member))
                completed = d["completed_total"] if d else 0
                case_add = d["case_add_total"] if d else 0
                errors = d["error_total"] if d else 0
                display_name = (d["display_name"] if d else None) or member
                leaves = leave_totals.get(clean_name(member), 0.0) or best_match(member, leave_totals) or 0.0
                target, daily_target, effective_days = get_target(member, leaves)
                achieved_metric = case_add if label in CASE_ADD_TARGET_TEAMS else completed
                pct_achieved = round(achieved_metric / target * 100, 1) if target else None
                if target and pct_achieved is not None and pct_achieved < 70:
                    typ, cohort = get_type_cohort(member)
                    below_70.append({
                        "name": display_name, "team": label, "completed": completed, "errors": errors,
                        "target": target, "daily_target": daily_target, "pct_achieved": pct_achieved,
                        "type": typ, "cohort": cohort, "is_new_joiner": member in NEW_JOINERS,
                    })

    # ── HR PIP post: new thread, FTE then Cohort 1-6 ──
    groups = []
    fte_rows = sorted([r for r in below_70 if r["type"] == "FTE"], key=lambda r: r["pct_achieved"])
    if fte_rows:
        groups.append(("FTE", fte_rows))
    intern_rows = [r for r in below_70 if r["type"] == "Intern"]
    for c in range(1, 7):
        c_rows = sorted([r for r in intern_rows if r["cohort"] == c], key=lambda r: r["pct_achieved"])
        if c_rows:
            groups.append((f"Cohort {c}", c_rows))
    unknown_rows = sorted([r for r in below_70 if r["type"] not in ("FTE", "Intern") or (r["type"] == "Intern" and r["cohort"] is None)], key=lambda r: r["pct_achieved"])
    if unknown_rows:
        groups.append(("Unclassified", unknown_rows))

    if groups:
        hr_channel = TEST_CHANNEL_ID or HR_CHANNEL_ID
        intro = f":rotating_light: *PIP Review — Below 70% of Target ({DATE_LABEL})*"
        thread_ts = post_slack_message(hr_channel, intro)
        for group_label, rows in groups:
            # Plain Slack chat.postMessage has no markdown-table rendering — a
            # monospace code block (like every other report in this repo) is the
            # actual "readable table" here, not a GFM pipe table.
            cols = ["Agent", "Team", "Completed", "Target", "%Ach"]
            display_rows = []
            for r in rows:
                marker = " (new joiner)" if r["is_new_joiner"] else ""
                display_rows.append([r["name"] + marker, r["team"], str(r["completed"]), fmt(r["target"]), f"{r['pct_achieved']}%"])
            widths = [max(len(cols[i]), *(len(dr[i]) for dr in display_rows)) + 2 for i in range(len(cols))]
            header_line = "".join(cols[i].ljust(widths[i]) if i == 0 else cols[i].rjust(widths[i]) for i in range(len(cols)))
            sep_line = "-" * len(header_line)
            body_lines = [header_line, sep_line]
            for dr in display_rows:
                body_lines.append("".join(dr[i].ljust(widths[i]) if i == 0 else dr[i].rjust(widths[i]) for i in range(len(cols))))
            body = f"*{group_label}*\n```\n" + "\n".join(body_lines) + "\n```"
            post_slack_message(hr_channel, body, thread_ts)
        post_slack_message(hr_channel, f"{HR_PIP_TAGS} — please review the above and confirm on PIP.", thread_ts)
        print(f"  Posted HR PIP thread with {len(below_70)} below-70% rows across {len(groups)} groups")
    else:
        print("  No below-70%-of-target rows this week — skipping HR PIP post")


if __name__ == "__main__":
    main()

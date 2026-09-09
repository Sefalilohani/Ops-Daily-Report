/**
 * Daily Task Report — ported 1:1 from report.py (Ops-Daily-Report repo).
 * Posts one Slack message-set per team channel with each category's
 * "By Task Type" and "By Check Type" agent tables for the previous day (IST).
 *
 * Secrets: Script Properties "REDASH_API_KEY", "SLACK_BOT_TOKEN".
 * Run manually via runDailyReport(), or install a daily trigger with
 * Triggers.gs's setupTriggers().
 */
var Daily = (function () {
  'use strict';

  var REDASH_BASE = 'https://redash.springworks.in';
  var REDASH_DS_ID = 5;
  var IST_OFFSET_MS = (5 * 60 + 30) * 60 * 1000;

  var TEST_CHANNEL_ALIASES = { 'testing-sefali': 'C0AGRE19V6U' };

  // ── CHANNEL / TEAM CONFIG ──────────────────────────────────────
  // Member lists synced from the "Ops Team Roster" artifact (as of 2026-09-07) —
  // that artifact is the source of truth for who's active on which team; refer to
  // it (not this file's git history) when posting reports or checking membership.
  var CHANNELS = [
    {
      channel_id: 'CS5CX8LPQ', // #sv-in-ops-caseanalysis
      categories: [
        { label: 'CA + Initiation', members: [
          'Subhashree L', 'Priyanka Krishnan', 'Manash Pratim Kashyap', 'Anitha Sagari Ravirala',
          'Aaiyana Vinod Sharma',
          'Abhishek Parashari', 'Abhishek Rawat', 'Adithya Padmanabhan', 'Indukuri Niranjan Reddy', 'Ishita Mishra',
          'Divyajot Kaur', 'Mohd Azfar Khan', 'Noshin M K', 'Anand Kumar',
          'Chinthala VSSSL Mokshajna', 'Anmol Sharma', // Cohort 4
          'Vaishali Bhandari', 'Shouriya Tayal', 'Vipul Patial', 'Prashant Gupta',
          'Pragati Kashyap', 'Anmol Nagpal', 'Kishan Yadav', 'Lovely', 'Siddhartha Kumar' // Cohort 7
        ] }
      ]
    },
    {
      channel_id: 'CS2PEFLMA', // #sv-in-ops-employment
      categories: [
        { label: 'Grading', members: [
          'Dithya Ann Mathew',
          'Chirumamilla Hamsa Veni', // Cohort 3
          'Puneesh Hingorani', 'Shambhavi Kumari', 'Vikas Bishnoi', 'Akhil', 'K Sai Vaishnav Kumar',
          'Utkarsh Raj', 'Abhishek Mohan', 'Surya Pratap', 'Jay Pawar', // Cohort 4
          'Rohan Kumarraju', 'Mohamed Waseem kurikkal M P', 'Shreshth Sahu', 'Lakshit Raina', // Cohort 6
          'Nitin Singh Sikarwar', 'Tappa Shaik Mohammed Vasif', 'Jyoti Raj', 'Akanksha Kumari',
          'Keerthi Rithvik Teja', 'Vaibhav Kumar Singh', 'Tarun Rajput' // Cohort 7
        ] },
        { label: 'Followups', members: [
          // ADD Followups
          'Nishika Dwivedi', 'Anindita Maity', 'Jillella Akshaya Prajwala', 'Bevara Hemanth Kumar',
          // EDU Followups
          'Navaneetha KS', 'D Joyce Blessia', 'Nara Sumanth', 'Mehak Rajput',
          // EMP Followups
          'Manisha Suresh Yadav', 'Shaik Suraj', 'Vivek Kumar Singh', 'Tapas Patra',
          'Pranshu', 'Aishwarya Arya', 'Samiksha Pilaniya',
          'P Swarna Lakshmi', 'Dharani Lakshmi', 'Gayathri A', 'Udita Singh'
        ] }
      ]
    },
    {
      channel_id: 'CQRU28ES0', // #sv-in-ops-add (Address Verification)
      categories: [
        { label: 'QC', members: [
          'Vikash Sunaliya', 'Shafaque Shadni', 'Shlok Paliwal', 'Vanshika Sharma', 'Utsav Banerjee',
          'Nishant Gupta', 'Manpreet Kaur', // Cohort 1
          'Talwinder Singh', 'Tanisha Thakur', 'Subhajit Debbarma', 'Saransh Jaggi', 'Anushka Jaiswal', 'Abhishek Sangwan', // Cohort 4
          'Vinay Pratap Singh', 'Manish Kumar Thakur', 'Nipun Singh', 'Aikansh Katiyar' // Cohort 6
        ] },
        { label: 'Email Clearance', members: [
          'Deepika S', 'Lavanya Dani', 'Riya Sinha',
          'Md. Parvezuddin',
          'Divya Harish', 'Sanskar Shrivastava'
        ] }
      ]
    },
    {
      channel_id: 'C023SD1L2E7', // #sv-in-ops-misc-checks
      categories: [
        { label: 'MISC', members: [
          'Pratyush Badhani', 'Samriddhi Kundu', 'B Hemanth Reddy', 'Kousik Ruidas', 'Samraggee Saha',
          'Swati Jampal', 'Abhraneel Chattopadhyay', 'Shivam Kumar Jha'
        ] },
        { label: 'Payment Settlement', members: ['Barsha Agarwal', 'Shivam Bhardwaj'] }
      ]
    },
    {
      channel_id: 'C07QAABSJ6R', // #sv-in-ops-additional-tasks
      categories: [
        { label: 'Case Addition', members: [
          'Manas Kumar Mishra', 'Rahul Sutradhar', 'Ankita Basak', 'Chirag Sethi', 'Sonia Thakur'
        ] }
      ]
    },
    {
      channel_id: 'C08TMLA7YSU', // #sv-in-ops-research
      categories: [
        { label: 'Research', members: [
          'Shuman Thappa', 'Satarupa Konar', 'Al Hasan', 'Poojasri Adambhakam',
          'Adithyan S', 'Aman Raj', 'Hasamuddin Ansari', 'Ballani Venkata Avinas', // Cohort 5
          'Khushi', 'Yusra Waseem' // Cohort 6
        ] }
      ]
    },
    {
      channel_id: 'C08MMSLV43H', // #sv-in-ops-ref
      categories: [
        { label: 'Reference', members: ['Nazia Hasan', 'Sakshi Bhuyan', 'Kishore M', 'Raunak Kumar', 'Sahil'] }
      ]
    }
  ];

  var CATEGORY_TAGS = {
    'Grading':            { usergroup: 'S0BKVL7E0SH', lead: 'UN1E2L4G0' },
    'QC':                 { usergroup: 'S046ESUQLS1', lead: 'U03BUG17X54' },
    'CA + Initiation':    { usergroup: 'S046WGXTBED', lead: 'U017K6KQT2A' },
    'Research':           { usergroup: 'S08VARCA849', lead: 'UN1E2L4G0' },
    'Reference':          { usergroup: 'S04K6P0CYES', lead: 'UN1E2L4G0' },
    'Email Clearance':    { usergroup: 'S0BKZ13RE82', lead: 'U03BUG17X54' },
    'Followups':          { usergroup: 'S0BLTALCZA4', lead: 'UURRMS3MG' },
    'Case Addition':      { usergroup: 'S086WH7H6A0', lead: 'UURRMS3MG' },
    'Payment Settlement': { usergroup: 'S0BKX213HFG', lead: 'U017K6KQT2A' },
    'MISC':               { usergroup: 'S05BY1H4HJ5', lead: 'U017K6KQT2A' }
  };

  var TASK_TYPE_INFO = {
    CASE_ANALYSIS: ['CA', 'Case Analysis'],
    INITIATION: ['INIT', 'Initiation'],
    QC: ['QC', 'QC'],
    GRADING: ['GRD', 'Grading'],
    FOLLOW_UP: ['FU', 'Follow Up'],
    EMAIL_CLEARANCE: ['EC', 'Email Clearance'],
    PAYMENTS_SETTLEMENT: ['PS', 'Payment Settlement'],
    ADDITIONAL_TASKS: ['AT', 'Additional Tasks'],
    RESEARCH: ['RES', 'Research'],
    RESEARCH_FOLLOW_UP: ['RFU', 'Research Follow Up'],
    INSUFFICIENCY_CLEARANCE: ['IC', 'Insufficiency Clearance'],
    VENDOR_MANAGEMENT: ['VM', 'Vendor Management'],
    CONSENT_REVIEW: ['CR', 'Consent Review'],
    DOCUMENTS_CROPPING: ['DC', 'Documents Cropping'],
    WHATSAPP_CLEARANCE: ['WC', 'WhatsApp Clearance'],
    WHATSAPP_FOLLOW_UP: ['WFU', 'WhatsApp Follow Up']
  };

  var NAME_PREFIXES = [
    'Payment Settlement', 'Customer Ops', 'Q C', 'R T', 'C S', 'A T', 'V M',
    'C A', 'Add', 'Grading', 'Initiation', 'Misc', 'Supp', 'Ops', 'Edu',
    'Emp', 'Ref', 'Dev'
  ];

  var MAX_MESSAGE_CHARS = 3500;

  // ── SMALL HELPERS ────────────────────────────────────────────

  function scriptProp(name) {
    return PropertiesService.getScriptProperties().getProperty(name);
  }

  function humanize(enumValue) {
    if (!enumValue || enumValue === 'N/A') return 'N/A';
    return enumValue.replace(/-/g, '_').split('_').map(function (w) {
      return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
    }).join(' ');
  }

  function taskTypeInfo(rawTaskType) {
    if (TASK_TYPE_INFO[rawTaskType]) return TASK_TYPE_INFO[rawTaskType];
    var label = humanize(rawTaskType);
    return [label.slice(0, 4).toUpperCase(), label];
  }

  function cleanName(name) {
    var n = (name || '').split(/\s+/).filter(Boolean).join(' ');
    var upper = n.toUpperCase();
    var prefixes = NAME_PREFIXES.slice().sort(function (a, b) { return b.length - a.length; });
    for (var i = 0; i < prefixes.length; i++) {
      var p = prefixes[i];
      if (upper.indexOf(p.toUpperCase() + ' ') === 0) {
        n = n.slice(p.length).trim();
        break;
      }
    }
    return n.toLowerCase();
  }

  function nameTokens(name) {
    var cleaned = cleanName(name);
    var spaced = cleaned.split('').map(function (c) {
      return /[a-z]/.test(c) || c === ' ' ? c : ' ';
    }).join('');
    var toks = spaced.split(/\s+/).filter(Boolean);
    return new Set(toks);
  }

  function ordinal(n) {
    if (n >= 11 && n <= 13) return n + 'th';
    var suf = ['th', 'st', 'nd', 'rd', 'th'][Math.min(n % 10, 4)];
    return n + suf;
  }

  var MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];

  function fmtDate(y, m, d) {
    return ordinal(d) + ' ' + MONTH_NAMES[m - 1] + ' ' + y;
  }

  // ── SET HELPERS (frozenset equivalents) ─────────────────────

  function setEquals(a, b) {
    if (a.size !== b.size) return false;
    for (var x of a) if (!b.has(x)) return false;
    return true;
  }
  function isSubset(a, b) { // a <= b
    for (var x of a) if (!b.has(x)) return false;
    return true;
  }
  function setIntersectSize(a, b) {
    var c = 0;
    for (var x of a) if (b.has(x)) c++;
    return c;
  }
  function coreTokens(tokens) {
    var core = new Set();
    tokens.forEach(function (t) { if (t.length > 1) core.add(t); });
    return core.size ? core : tokens;
  }
  function tokenCompat(t1, t2) {
    return t1 === t2 || (t1.length === 1 && t2.indexOf(t1) === 0) || (t2.length === 1 && t1.indexOf(t2) === 0);
  }
  function permutations(arr) {
    if (arr.length <= 1) return [arr];
    var result = [];
    for (var i = 0; i < arr.length; i++) {
      var rest = arr.slice(0, i).concat(arr.slice(i + 1));
      permutations(rest).forEach(function (p) { result.push([arr[i]].concat(p)); });
    }
    return result;
  }

  /** Returns a match tier (lower = stronger), or null if incompatible. */
  function namesCompatible(tokensA, tokensB) {
    if (setEquals(tokensA, tokensB) || isSubset(tokensA, tokensB) || isSubset(tokensB, tokensA)) return 0;
    if (tokensA.size === tokensB.size) {
      var arrA = Array.from(tokensA);
      var perms = permutations(Array.from(tokensB));
      for (var p = 0; p < perms.length; p++) {
        var perm = perms[p];
        var ok = true;
        for (var i = 0; i < arrA.length; i++) {
          if (!tokenCompat(arrA[i], perm[i])) { ok = false; break; }
        }
        if (ok) return 1;
      }
    }
    var coreA = coreTokens(tokensA), coreB = coreTokens(tokensB);
    if (coreA.size && coreB.size && (isSubset(coreA, coreB) || isSubset(coreB, coreA))) return 2;
    return null;
  }

  // ── HTTP / REDASH ────────────────────────────────────────────

  function httpJson(method, url, headers, payload) {
    var options = { method: method, headers: headers, muteHttpExceptions: true };
    if (payload !== undefined) {
      options.contentType = 'application/json';
      options.payload = JSON.stringify(payload);
    }
    var resp = UrlFetchApp.fetch(url, options);
    var code = resp.getResponseCode();
    if (code < 200 || code >= 300) {
      throw new Error('HTTP ' + code + ' for ' + url + ': ' + resp.getContentText().slice(0, 300));
    }
    return JSON.parse(resp.getContentText());
  }

  function fetchAdhocOnce(sql) {
    var headers = { Authorization: 'Key ' + scriptProp('REDASH_API_KEY') };
    var resp = httpJson('post', REDASH_BASE + '/api/query_results', headers,
      { data_source_id: REDASH_DS_ID, query: sql, max_age: 0 });
    if (resp.query_result) return resp.query_result.data.rows;
    var jobId = resp.job && resp.job.id;
    if (!jobId) throw new Error('Unexpected Redash response: ' + JSON.stringify(resp).slice(0, 300));
    for (var i = 0; i < 30; i++) {
      Utilities.sleep(2000);
      var jr = httpJson('get', REDASH_BASE + '/api/jobs/' + jobId, headers);
      var job = jr.job || {};
      if (job.status === 3) {
        var rr = httpJson('get', REDASH_BASE + '/api/query_results/' + job.query_result_id, headers);
        return rr.query_result.data.rows;
      }
      if (job.status === 4) throw new Error('Redash query failed: ' + job.error);
    }
    throw new Error('Redash ad-hoc query timed out after 60s');
  }

  function fetchAdhoc(sql) {
    var retries = 2;
    for (var attempt = 0; attempt <= retries; attempt++) {
      try {
        return fetchAdhocOnce(sql);
      } catch (e) {
        if (attempt === retries) throw e;
        Logger.log('  fetchAdhoc attempt ' + (attempt + 1) + ' failed (' + e + '), retrying...');
        Utilities.sleep(5000);
      }
    }
  }

  function istDayUtcBounds(y, m, d) {
    var start = new Date(Date.UTC(y, m - 1, d, 0, 0, 0));
    var end = new Date(start.getTime() + 24 * 3600 * 1000);
    return [formatSql(start), formatSql(end)];
  }

  function formatSql(date) {
    return Utilities.formatDate(date, 'Etc/UTC', 'yyyy-MM-dd HH:mm:ss');
  }

  function fetchCompleted(startUtc, endUtc) {
    var sql = "" +
      "        SELECT\n" +
      "            u.name AS \"Agent Name\",\n" +
      "            tt.value AS \"Task Type\",\n" +
      "            COALESCE(ct.value, 'N/A') AS \"Check Type\",\n" +
      "            COUNT(DISTINCT ts.id) AS \"Completed Count\"\n" +
      "        FROM tasks ts\n" +
      "        INNER JOIN users u ON u.id = ts.completed_by_user_id_fk\n" +
      "        INNER JOIN enums tt ON ts.task_type = tt.id AND tt.type = 'TEAM_TYPE' AND tt.deleted_at IS NULL\n" +
      "        LEFT JOIN enums ct ON ts.check_type = ct.id AND ct.deleted_at IS NULL\n" +
      "        WHERE\n" +
      "            ts.deleted_at IS NULL\n" +
      "            AND ts.task_completed_at >= '" + startUtc + "'\n" +
      "            AND ts.task_completed_at < '" + endUtc + "'\n" +
      "            AND ts.task_status = (SELECT id FROM enums WHERE type='TASK_STATUS' AND value='COMPLETED' AND deleted_at IS NULL LIMIT 1)\n" +
      "            AND ts.completed_by_user_id_fk NOT IN (4, 17542)\n" +
      "        GROUP BY u.name, tt.value, ct.value\n" +
      "        ORDER BY u.name, tt.value, ct.value\n";
    var rows = fetchAdhoc(sql);
    Logger.log('  Completed: ' + rows.length + ' rows');
    return rows;
  }

  function fetchErrors(startUtc, endUtc) {
    var sql = "" +
      "        SELECT u.name AS \"Name\", COUNT(DISTINCT e.id) AS \"Error Count\"\n" +
      "        FROM errors e\n" +
      "        INNER JOIN users u ON u.id = e.agent_user_id_fk\n" +
      "        LEFT JOIN teams_user_mapping tum ON tum.user_id_fk = u.id\n" +
      "        LEFT JOIN teams t ON t.id = tum.team_id_fk AND t.deleted_at IS NULL\n" +
      "        LEFT JOIN enums dept_enum ON dept_enum.id = t.department_enum_fk AND dept_enum.deleted_at IS NULL\n" +
      "        WHERE e.deleted_at IS NULL\n" +
      "          AND e.created_at >= '" + startUtc + "' AND e.created_at < '" + endUtc + "'\n" +
      "          AND (dept_enum.value = 'OPERATIONS' OR LOWER(u.name) LIKE '%system user%' OR LOWER(u.name) LIKE '%springverify ai%')\n" +
      "        GROUP BY u.name\n" +
      "        ORDER BY u.name\n";
    var rows = fetchAdhoc(sql);
    Logger.log('  Errors: ' + rows.length + ' rows');
    return rows;
  }

  function fetchCaseAdditions(startUtc, endUtc) {
    var sql = "" +
      "        WITH consent_events AS (\n" +
      "            SELECT\n" +
      "                cl.candidate_id_fk,\n" +
      "                CASE WHEN cl.user_type = 1 THEN cl.user_id_fk ELSE cl.proxy_user_id_fk END AS adder_user_id,\n" +
      "                CASE WHEN cl.user_type = 1 THEN 'DIRECT' ELSE 'PROXY' END AS adder_type,\n" +
      "                cl.created_at AS add_at, 0 AS priority\n" +
      "            FROM candidate_logs cl\n" +
      "            WHERE cl.type = 'CANDIDATE_CONSENT_ADDED' AND cl.deleted_at IS NULL\n" +
      "              AND ((cl.user_type = 1 AND cl.user_id_fk IS NOT NULL)\n" +
      "                OR (cl.user_type = 2 AND cl.proxy_user_id_fk IS NOT NULL))\n" +
      "              AND cl.created_at >= DATE_SUB('" + startUtc + "', INTERVAL 30 DAY)\n" +
      "              AND cl.created_at < '" + endUtc + "'\n" +
      "        ),\n" +
      "        consent_exists AS (\n" +
      "            SELECT DISTINCT candidate_id_fk FROM candidate_logs\n" +
      "            WHERE type = 'CANDIDATE_CONSENT_ADDED' AND deleted_at IS NULL\n" +
      "              AND created_at >= DATE_SUB('" + startUtc + "', INTERVAL 30 DAY)\n" +
      "              AND created_at < '" + endUtc + "'\n" +
      "        ),\n" +
      "        basic_info_fallback AS (\n" +
      "            SELECT\n" +
      "                cl.candidate_id_fk,\n" +
      "                CASE WHEN cl.user_type = 1 THEN cl.user_id_fk ELSE cl.proxy_user_id_fk END AS adder_user_id,\n" +
      "                CASE WHEN cl.user_type = 1 THEN 'DIRECT' ELSE 'PROXY' END AS adder_type,\n" +
      "                cl.created_at AS add_at, 1 AS priority\n" +
      "            FROM candidate_logs cl\n" +
      "            WHERE cl.type = 'CANDIDATE_BASIC_INFO_UPDATED' AND cl.deleted_at IS NULL\n" +
      "              AND ((cl.user_type = 1 AND cl.user_id_fk IS NOT NULL)\n" +
      "                OR (cl.user_type = 2 AND cl.proxy_user_id_fk IS NOT NULL))\n" +
      "              AND cl.created_at >= DATE_SUB('" + startUtc + "', INTERVAL 30 DAY)\n" +
      "              AND cl.created_at < '" + endUtc + "'\n" +
      "              AND cl.candidate_id_fk NOT IN (SELECT candidate_id_fk FROM consent_exists)\n" +
      "        ),\n" +
      "        add_events AS (\n" +
      "            SELECT candidate_id_fk, adder_user_id, adder_type, add_at, priority,\n" +
      "                ROW_NUMBER() OVER (PARTITION BY candidate_id_fk ORDER BY priority ASC, add_at ASC) AS rn\n" +
      "            FROM (SELECT * FROM consent_events UNION ALL SELECT * FROM basic_info_fallback) x\n" +
      "        ),\n" +
      "        canonical_add AS (\n" +
      "            SELECT candidate_id_fk, adder_user_id, adder_type, add_at FROM add_events WHERE rn = 1\n" +
      "        ),\n" +
      "        fills AS (\n" +
      "            SELECT\n" +
      "                ccm.candidate_id, ccm.form_filled,\n" +
      "                CASE WHEN ccm.form_filled_by = 1 THEN ccm.form_filled_by_user_id\n" +
      "                     WHEN ccm.form_filled_by = 3 THEN ccm.proxy_user_id\n" +
      "                     ELSE NULL END AS filler_user_id\n" +
      "            FROM company_candidate_mapping ccm\n" +
      "            WHERE ccm.deleted_at IS NULL\n" +
      "              AND ccm.created_at >= DATE_SUB('" + startUtc + "', INTERVAL 30 DAY)\n" +
      "              AND ccm.created_at < '" + endUtc + "'\n" +
      "        ),\n" +
      "        combined AS (\n" +
      "            SELECT ca.candidate_id_fk, ca.adder_user_id, ca.adder_type, ca.add_at, f.form_filled, f.filler_user_id\n" +
      "            FROM canonical_add ca\n" +
      "            LEFT JOIN fills f ON f.candidate_id = ca.candidate_id_fk\n" +
      "            UNION\n" +
      "            SELECT f.candidate_id AS candidate_id_fk, ca.adder_user_id, ca.adder_type, ca.add_at, f.form_filled, f.filler_user_id\n" +
      "            FROM fills f\n" +
      "            LEFT JOIN canonical_add ca ON ca.candidate_id_fk = f.candidate_id\n" +
      "            WHERE ca.candidate_id_fk IS NULL AND f.filler_user_id IS NOT NULL\n" +
      "        ),\n" +
      "        tagged AS (\n" +
      "            SELECT candidate_id_fk,\n" +
      "                CASE WHEN adder_type = 'PROXY' THEN adder_user_id END AS b4_user, add_at AS b4_date,\n" +
      "                CASE WHEN adder_type = 'DIRECT' AND filler_user_id IS NOT NULL AND filler_user_id = adder_user_id THEN adder_user_id END AS b1_user, add_at AS b1_date,\n" +
      "                CASE WHEN adder_type = 'DIRECT' AND form_filled IS NULL THEN adder_user_id END AS b2_user, add_at AS b2_date,\n" +
      "                CASE WHEN filler_user_id IS NOT NULL AND filler_user_id <> COALESCE(adder_user_id, -1) THEN filler_user_id END AS b3_user, form_filled AS b3_date\n" +
      "            FROM combined\n" +
      "        ),\n" +
      "        per_agent_candidate AS (\n" +
      "            SELECT candidate_id_fk, b1_user AS agent_user_id, 1 AS added_and_filled, 0 AS added_not_filled, 0 AS filled_only, 0 AS proxy_added, b1_date AS credit_date FROM tagged WHERE b1_user IS NOT NULL\n" +
      "            UNION ALL\n" +
      "            SELECT candidate_id_fk, b2_user, 0, 1, 0, 0, b2_date FROM tagged WHERE b2_user IS NOT NULL\n" +
      "            UNION ALL\n" +
      "            SELECT candidate_id_fk, b3_user, 0, 0, 1, 0, b3_date FROM tagged WHERE b3_user IS NOT NULL\n" +
      "            UNION ALL\n" +
      "            SELECT candidate_id_fk, b4_user, 0, 0, 0, 1, b4_date FROM tagged WHERE b4_user IS NOT NULL\n" +
      "        )\n" +
      "        SELECT\n" +
      "            u.name AS \"Agent Name\",\n" +
      "            SUM(pac.added_and_filled) AS \"Added & Filled\",\n" +
      "            SUM(pac.added_not_filled) AS \"Added, Not Filled\",\n" +
      "            SUM(pac.filled_only) AS \"Filled Only\",\n" +
      "            SUM(pac.proxy_added) AS \"Proxy Added\"\n" +
      "        FROM per_agent_candidate pac\n" +
      "        JOIN users u ON u.id = pac.agent_user_id\n" +
      "        WHERE pac.credit_date >= '" + startUtc + "' AND pac.credit_date < '" + endUtc + "'\n" +
      "        GROUP BY u.name\n" +
      "        ORDER BY u.name\n";
    var rows = fetchAdhoc(sql);
    Logger.log('  Case additions: ' + rows.length + ' rows');
    return rows;
  }

  // ── AGGREGATE ───────────────────────────────────────────────

  function newAgent() {
    return {
      display_name: null,
      task_totals: {},
      task_labels: {},
      task_check: {},
      completed_total: 0, error_total: 0, case_add_total: 0,
      case_add_added_filled: 0, case_add_added_not_filled: 0,
      case_add_filled_only: 0, case_add_proxy_added: 0
    };
  }

  function getAgent(data, key) {
    if (!data[key]) data[key] = newAgent();
    return data[key];
  }

  function buildAgentData(completedRows, errorRows, caseAddRows) {
    var data = {};

    completedRows.forEach(function (row) {
      var rawName = row['Agent Name'] || '';
      var key = cleanName(rawName);
      if (!key) return;
      var info = taskTypeInfo(row['Task Type'] || '');
      var abbr = info[0], fullLabel = info[1];
      var checkRaw = row['Check Type'];
      var count = parseInt(row['Completed Count'] || 0, 10);
      var d = getAgent(data, key);
      d.display_name = d.display_name || rawName;
      d.task_totals[abbr] = (d.task_totals[abbr] || 0) + count;
      d.task_labels[abbr] = fullLabel;
      if (checkRaw && checkRaw !== 'N/A') {
        var h = humanize(checkRaw);
        d.task_check[abbr] = d.task_check[abbr] || {};
        d.task_check[abbr][h] = (d.task_check[abbr][h] || 0) + count;
      }
      d.completed_total += count;
    });

    errorRows.forEach(function (row) {
      var rawName = row['Name'] || '';
      var key = cleanName(rawName);
      if (!key) return;
      var count = parseInt(row['Error Count'] || 0, 10);
      var d = getAgent(data, key);
      d.display_name = d.display_name || rawName;
      d.error_total += count;
    });

    caseAddRows.forEach(function (row) {
      var rawName = row['Agent Name'] || '';
      var key = cleanName(rawName);
      if (!key) return;
      var af = parseInt(row['Added & Filled'] || 0, 10);
      var anf = parseInt(row['Added, Not Filled'] || 0, 10);
      var fo = parseInt(row['Filled Only'] || 0, 10);
      var pa = parseInt(row['Proxy Added'] || 0, 10);
      var d = getAgent(data, key);
      d.display_name = d.display_name || rawName;
      d.case_add_added_filled += af;
      d.case_add_added_not_filled += anf;
      d.case_add_filled_only += fo;
      d.case_add_proxy_added += pa;
      // Case+ = sum of all 4 buckets — matches report.py's 20 Aug decision.
      d.case_add_total += af + anf + fo + pa;
    });

    return data;
  }

  // ── MATCHING ─────────────────────────────────────────────────

  function buildTokenIndex(agentData) {
    return Object.keys(agentData).map(function (key) { return [key, nameTokens(key)]; });
  }

  function resolveMemberAssignments(agentData) {
    var tokenIndex = buildTokenIndex(agentData);

    var allMembers = [];
    CHANNELS.forEach(function (channel) {
      channel.categories.forEach(function (category) {
        category.members.forEach(function (member) {
          allMembers.push([category.label, member]);
        });
      });
    });

    var exactOwner = {}; // candidateKey -> [label, member]
    var claims = {};     // candidateKey -> [[tier, overlap, label, member], ...]

    allMembers.forEach(function (pair) {
      var label = pair[0], member = pair[1];
      var key = cleanName(member);
      if (agentData[key]) {
        exactOwner[key] = [label, member];
        return;
      }
      var memberTokens = nameTokens(member);
      if (!memberTokens.size) return;
      tokenIndex.forEach(function (entry) {
        var k = entry[0], t = entry[1];
        if (!t.size) return;
        var tier = namesCompatible(memberTokens, t);
        if (tier !== null) {
          claims[k] = claims[k] || [];
          claims[k].push([tier, setIntersectSize(t, memberTokens), label, member]);
        }
      });
    });

    var assignments = {};
    var assignKey = function (label, member) { return label + ' ' + member; };
    allMembers.forEach(function (pair) { assignments[assignKey(pair[0], pair[1])] = null; });

    Object.keys(exactOwner).forEach(function (key) {
      var pair = exactOwner[key];
      assignments[assignKey(pair[0], pair[1])] = agentData[key];
    });

    Object.keys(claims).forEach(function (key) {
      if (exactOwner[key]) return;
      var claimants = claims[key].slice().sort(function (a, b) {
        if (a[0] !== b[0]) return a[0] - b[0];
        return b[1] - a[1];
      });
      var topTier = claimants[0][0], topScore = claimants[0][1];
      var winners = claimants.filter(function (c) { return c[0] === topTier && c[1] === topScore; });
      if (winners.length === 1) {
        var label = winners[0][2], member = winners[0][3];
        assignments[assignKey(label, member)] = agentData[key];
      }
    });

    return { get: function (label, member) { return assignments[assignKey(label, member)]; } };
  }

  // ── FORMAT SLACK MESSAGE ─────────────────────────────────────

  function agentCheckTotals(d) {
    var totals = {};
    Object.keys(d.task_check).forEach(function (abbr) {
      var checks = d.task_check[abbr];
      Object.keys(checks).forEach(function (label) {
        totals[label] = (totals[label] || 0) + checks[label];
      });
    });
    return totals;
  }

  var CASE_ADD_SUBCOLS = [
    ['Add&Fill', 'case_add_added_filled'],
    ['AddOnly', 'case_add_added_not_filled'],
    ['FillOnly', 'case_add_filled_only'],
    ['Proxy', 'case_add_proxy_added']
  ];

  function buildAgentColTable(active, totDone, totErr, totCase, showCaseAddition, colGetter) {
    var colTotals = {};
    active.forEach(function (pair) {
      var counts = colGetter(pair[1]);
      Object.keys(counts).forEach(function (c) { colTotals[c] = (colTotals[c] || 0) + counts[c]; });
    });
    var cols = Object.keys(colTotals).sort(function (a, b) { return colTotals[b] - colTotals[a]; });

    var caseTotals = {};
    if (showCaseAddition) {
      CASE_ADD_SUBCOLS.forEach(function (pair) {
        var key = pair[1];
        caseTotals[key] = active.reduce(function (s, p) { return s + p[1][key]; }, 0);
      });
    }

    var nameW = Math.max.apply(null, ['Agent'.length, 'TEAM TOTAL'.length].concat(active.map(function (p) { return p[0].length; }))) + 2;
    var colW = {};
    cols.forEach(function (c) { colW[c] = Math.max(c.length, 5) + 2; });
    var doneW = Math.max('Total'.length, String(totDone).length) + 2;
    var errW = Math.max('Err'.length, String(totErr).length) + 2;
    var caseTotalW = showCaseAddition ? Math.max('Case+'.length, String(totCase).length) + 2 : 0;
    var caseW = {};
    if (showCaseAddition) {
      CASE_ADD_SUBCOLS.forEach(function (pair) {
        var label = pair[0], key = pair[1];
        caseW[label] = Math.max(label.length, String(caseTotals[key]).length) + 2;
      });
    }

    var header = 'Agent'.padEnd(nameW);
    cols.forEach(function (c) { header += c.padStart(colW[c]); });
    header += 'Total'.padStart(doneW) + 'Err'.padStart(errW);
    if (showCaseAddition) {
      header += 'Case+'.padStart(caseTotalW);
      CASE_ADD_SUBCOLS.forEach(function (pair) { header += pair[0].padStart(caseW[pair[0]]); });
    }
    var sep = '-'.repeat(header.length);

    var lines = [header, sep];
    active.forEach(function (pair) {
      var name = pair[0], d = pair[1];
      var row = name.padEnd(nameW);
      var counts = colGetter(d);
      cols.forEach(function (c) {
        var v = counts[c] || 0;
        row += (v ? String(v) : '-').padStart(colW[c]);
      });
      row += String(d.completed_total).padStart(doneW) + String(d.error_total).padStart(errW);
      if (showCaseAddition) {
        row += String(d.case_add_total).padStart(caseTotalW);
        CASE_ADD_SUBCOLS.forEach(function (pair) {
          var label = pair[0], key = pair[1];
          var v = d[key];
          row += (v ? String(v) : '-').padStart(caseW[label]);
        });
      }
      lines.push(row);
    });
    lines.push(sep);

    var totalRow = 'TEAM TOTAL'.padEnd(nameW);
    cols.forEach(function (c) { totalRow += String(colTotals[c]).padStart(colW[c]); });
    totalRow += String(totDone).padStart(doneW) + String(totErr).padStart(errW);
    if (showCaseAddition) {
      totalRow += String(totCase).padStart(caseTotalW);
      CASE_ADD_SUBCOLS.forEach(function (pair) {
        var label = pair[0], key = pair[1];
        totalRow += String(caseTotals[key]).padStart(caseW[label]);
      });
    }
    lines.push(totalRow);

    return lines.join('\n');
  }

  function formatCategorySection(label, members, agentData, assignments) {
    var tag = CATEGORY_TAGS[label];
    var tagLine = tag ? ('cc: <!subteam^' + tag.usergroup + '> <@' + tag.lead + '>') : '';

    if (!members.length) {
      var text = '*' + label + '*\n_No members configured yet._';
      return { bodies: [text + (tagLine ? '\n' + tagLine : '')], totDone: 0, totErr: 0, totCase: 0 };
    }

    var idleNames = [];
    var unmatched = [];
    var matchedRows = [];

    members.forEach(function (member) {
      var d = assignments.get(label, member);
      if (d === null || d === undefined) { unmatched.push(member); return; }
      matchedRows.push([d.display_name || member, d]);
    });

    matchedRows.sort(function (a, b) { return b[1].completed_total - a[1].completed_total; });

    var showCaseAddition = matchedRows.some(function (p) { return p[1].case_add_total > 0; });

    var active = [];
    var totDone = 0, totErr = 0, totCase = 0;
    matchedRows.forEach(function (pair) {
      var name = pair[0], d = pair[1];
      totDone += d.completed_total;
      totErr += d.error_total;
      totCase += d.case_add_total;
      if (d.completed_total === 0 && d.error_total === 0 && d.case_add_total === 0) {
        idleNames.push(name);
        return;
      }
      active.push([name, d]);
    });

    if (!active.length) {
      var body = '_No activity today._';
      if (idleNames.length) body += '\n_No activity: ' + idleNames.join(', ') + '_';
      if (unmatched.length) body += '\n_No data found for: ' + unmatched.join(', ') + '_';
      if (tagLine) body += '\n' + tagLine;
      return { bodies: [body], totDone: totDone, totErr: totErr, totCase: totCase };
    }

    var taskTable = buildAgentColTable(active, totDone, totErr, totCase, showCaseAddition, function (d) { return d.task_totals; });
    var msg1 = '*By Task Type*\n```\n' + taskTable + '\n```';
    if (idleNames.length) msg1 += '\n_No activity: ' + idleNames.join(', ') + '_';
    if (unmatched.length) msg1 += '\n_No data found for: ' + unmatched.join(', ') + '_';

    var checkTable = buildAgentColTable(active, totDone, totErr, totCase, showCaseAddition, agentCheckTotals);
    var msg2 = '*By Check Type*\n```\n' + checkTable + '\n```';
    if (tagLine) msg2 += '\n' + tagLine;

    return { bodies: [msg1, msg2], totDone: totDone, totErr: totErr, totCase: totCase };
  }

  function formatChannelMessages(channelCfg, dateLabel, agentData, assignments) {
    var messages = [];
    channelCfg.categories.forEach(function (c) {
      var result = formatCategorySection(c.label, c.members, agentData, assignments);
      var header = '📊 *' + c.label + ' Team Daily Task Report — ' + dateLabel + '*';
      messages.push(header + '\n\n' + result.bodies[0]);
      for (var i = 1; i < result.bodies.length; i++) messages.push(result.bodies[i]);
    });
    return messages;
  }

  // ── SLACK ────────────────────────────────────────────────────

  function resolveSlackToken() {
    var token = scriptProp('SLACK_BOT_TOKEN');
    var resp = httpJson('post', 'https://slack.com/api/auth.test', { Authorization: 'Bearer ' + token });
    if (!resp.ok) {
      throw new Error('SLACK_BOT_TOKEN failed auth.test: ' + resp.error + '. Re-check the Script Property.');
    }
    Logger.log('Slack auth OK — bot: ' + resp.user + ', team: ' + resp.team);
    return token;
  }

  function chunkMessage(text) {
    var maxLen = MAX_MESSAGE_CHARS;
    if (text.length <= maxLen) return [text];
    var chunks = [], current = '', inCodeBlock = false;
    var lines = text.split('\n');
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var candidate = current ? (current + '\n' + line) : line;
      if (candidate.length > maxLen && current) {
        if (inCodeBlock) {
          chunks.push(current + '\n```');
          current = '```\n' + line;
        } else {
          chunks.push(current);
          current = line;
        }
      } else {
        current = candidate;
      }
      if (line.trim() === '```') inCodeBlock = !inCodeBlock;
    }
    if (current) chunks.push(current);
    return chunks;
  }

  function postSlackMessage(slackToken, channelId, text, threadTs) {
    var tsList = [];
    chunkMessage(text).forEach(function (chunk) {
      var payload = { channel: channelId, text: chunk };
      if (threadTs) payload.thread_ts = threadTs;
      var resp = httpJson('post', 'https://slack.com/api/chat.postMessage',
        { Authorization: 'Bearer ' + slackToken, 'Content-Type': 'application/json' }, payload);
      if (!resp.ok) throw new Error('Slack API error for channel ' + channelId + ': ' + resp.error);
      tsList.push(resp.ts);
    });
    return tsList;
  }

  // ── MAIN ─────────────────────────────────────────────────────

  /**
   * @param {string} [overrideDate] YYYY-MM-DD — else "yesterday" in IST.
   * @param {string} [testChannelAlias] key into TEST_CHANNEL_ALIASES — redirects all posts there.
   */
  function run(overrideDate, testChannelAlias) {
    var slackToken = resolveSlackToken();
    var testChannelId = testChannelAlias ? TEST_CHANNEL_ALIASES[testChannelAlias] : '';

    var y, m, d;
    if (overrideDate) {
      var parts = overrideDate.split('-').map(Number);
      y = parts[0]; m = parts[1]; d = parts[2];
    } else {
      var nowIst = new Date(new Date().getTime() + IST_OFFSET_MS);
      var yest = new Date(Date.UTC(nowIst.getUTCFullYear(), nowIst.getUTCMonth(), nowIst.getUTCDate() - 1));
      y = yest.getUTCFullYear(); m = yest.getUTCMonth() + 1; d = yest.getUTCDate();
    }

    var dateLabel = fmtDate(y, m, d);
    var bounds = istDayUtcBounds(y, m, d);
    var startUtc = bounds[0], endUtc = bounds[1];
    Logger.log('Reporting on: ' + dateLabel + ' (raw UTC calendar-day window ' + startUtc + ' -> ' + endUtc + ', matches Redash Q3045)');

    Logger.log('Fetching Redash data...');
    var completedRows = fetchCompleted(startUtc, endUtc);
    var errorRows = fetchErrors(startUtc, endUtc);
    var caseAddRows = fetchCaseAdditions(startUtc, endUtc);

    var agentData = buildAgentData(completedRows, errorRows, caseAddRows);
    var assignments = resolveMemberAssignments(agentData);

    var failures = [];

    CHANNELS.forEach(function (channelCfg) {
      var hasMembers = channelCfg.categories.some(function (c) { return c.members.length; });
      if (!hasMembers) {
        Logger.log('Skipping channel ' + channelCfg.channel_id + ' — no members configured yet');
        return;
      }

      // Each channel is independent — one bad/inaccessible channel (e.g. the bot
      // hasn't been invited to it) must not abort every other team's report.
      try {
        var messages = formatChannelMessages(channelCfg, dateLabel, agentData, assignments);
        var targetChannel = testChannelId || channelCfg.channel_id;

        messages.forEach(function (message) {
          if (testChannelId) {
            message = '_[TEST RUN — would normally post to ' + channelCfg.channel_id + ']_\n' + message;
          }
          postSlackMessage(slackToken, targetChannel, message).forEach(function (ts) {
            Logger.log('Posted to ' + targetChannel + ' (ts=' + ts + ')');
          });
        });
      } catch (e) {
        Logger.log('ERROR posting to channel ' + channelCfg.channel_id + ': ' + e + ' — continuing with remaining channels.');
        failures.push(channelCfg.channel_id + ': ' + e);
      }
    });

    if (failures.length) {
      throw new Error('Daily report finished with ' + failures.length + ' channel failure(s): ' + failures.join(' | '));
    }
  }

  return { run: run };
})();

/** Manual entry point — run from the Apps Script editor, or via a trigger. */
function runDailyReport() {
  Daily.run();
}

/** Test run — redirects every channel post to #testing-sefali. */
function runDailyReportTest() {
  Daily.run(null, 'testing-sefali');
}

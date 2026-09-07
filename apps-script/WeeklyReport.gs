/**
 * Weekly Ops Performance Report — ported 1:1 from weekly_report.py (Ops-Daily-Report repo).
 * Every Monday, reports on the PRECEDING Monday-Sunday week for all Ops sub-teams:
 * Summary (Completed/Errors/Avg-Day/Calls/Target/%Achieved/Leaves/WFH), By Task Type,
 * By Check Type — posted to each team's Slack channel. Also posts a "Below 70% of
 * Target" breakdown (FTE, then Interns by cohort) as a thread in the HR ops channel.
 *
 * Secrets: Script Properties "REDASH_API_KEY", "SLACK_BOT_TOKEN".
 * Leave/WFH/Call Log now come straight from the Bounty Google Sheet via SpreadsheetApp
 * (the running user's own Google identity) — no service-account JSON needed any more;
 * just make sure this script's owner has at least Viewer access to the sheet.
 */
var Weekly = (function () {
  'use strict';

  var REDASH_BASE = 'https://redash.springworks.in';
  var REDASH_DS_ID = 5;
  var IST_OFFSET_MS = (5 * 60 + 30) * 60 * 1000;

  var BOUNTY_SHEET_ID = '1dUzxzF_6lY3lPdiHpmBg0mbas4q-Pp3ALE1Zx0WXHow';

  var TEST_CHANNEL_ALIASES = { 'testing-sefali': 'C0AGRE19V6U' };
  var HR_CHANNEL_ID = 'C029UP81727'; // #hr-sv-ops
  var HR_PIP_TAGS = 'cc: <@UN1E2L4G0> <@U03BUG17X54> <@U017K6KQT2A> <@UURRMS3MG>'; // Selva, Ramya, Thanveer, Shalini

  var CASE_ADD_TARGET_TEAMS = { 'Case Addition': true };

  // ── CHANNEL / TEAM CONFIG (all sub-teams) ──
  var CHANNELS = [
    { channel_id: 'CS5CX8LPQ', channel_name: '#sv-in-ops-caseanalysis', categories: [
      { label: 'CA + Initiation', members: [
        'Subhashree L', 'Priyanka Krishnan', 'Manash Pratim Kashyap', 'Anitha Sagari Ravirala',
        'Aaiyana Vinod Sharma', 'Kondeti Ashvitha', 'Sahil Vilas Mule', 'Nishmeet Singh Rajpal',
        'Abhishek Parashari', 'Abhishek Rawat', 'Adithya Padmanabhan', 'Indukuri Niranjan Reddy',
        'Ishita Mishra', 'Divyajot Kaur', 'Mohd Azfar Khan', 'Noshin M K', 'Anand Kumar',
        'Chinthala VSSSL Mokshajna', 'Anmol Sharma'
      ] }
    ] },
    { channel_id: 'CS2PEFLMA', channel_name: '#sv-in-ops-employment', categories: [
      { label: 'Grading', members: [
        'Dithya Ann Mathew', 'E Tarun', 'Shaeeshta Shaila', 'Chirumamilla Hamsa Veni',
        'Peddireddy Vasu Deva Reddy', 'Priyanka Lohia', 'Shreshth Sahu', 'Puneesh Hingorani',
        'Shambhavi Kumari', 'Vikas Bishnoi', 'Akhil', 'Pentapalli Charan', 'K Sai Vaishnav Kumar',
        'Lakshit Raina', 'Utkarsh Raj', 'Abhishek Mohan', 'Mohamed Waseem kurikkal M P',
        'Surya Pratap', 'Jay Pawar', 'Anisha Kumari', 'Rohan Kumarraju'
      ] },
      { label: 'Followups', members: [
        'Chandrima Banik', 'Nishika Dwivedi', 'Anindita Maity', 'Jillella Akshaya Prajwala',
        'Bevara Hemanth Kumar', 'Debjani Dutta Gupta', 'Kartik Kaushal', 'Navaneetha KS',
        'D Joyce Blessia', 'Janani S P', 'Nara Sumanth', 'Mehak Rajput', 'Manisha Suresh Yadav',
        'Aishu Ji Lochan', 'Pratham Rathor', 'Adyasha Pattanaik', 'Pranshu', 'Gayathri A',
        'Dharani Lakshmi', 'P Swarna Lakshmi', 'Udita Singh', 'Aishwarya Arya', 'Samiksha Pilaniya',
        'Vivek Kumar Singh', 'Tapas Patra', 'Shaik Suraj'
      ] }
    ] },
    { channel_id: 'CQRU28ES0', channel_name: '#sv-in-ops-add', categories: [
      { label: 'QC', members: [
        'Vikash Sunaliya', 'Shafaque Shadni', 'Mohammad Sameem Nazki', 'Shlok Paliwal',
        'Vanshika Sharma', 'Utsav Banerjee', 'Nishant Gupta', 'Manpreet Kaur', 'Alisha Chaudhary',
        'Mitta Ruthika', 'Harshitha Sakkuri', 'Chuppa Harshitha', 'Talwinder Singh', 'Tanisha Thakur',
        'Subhajit Debbarma', 'Saransh Jaggi', 'Anushka Jaiswal', 'Abhishek Sangwan',
        'Sachin Kumar Singh', 'Vinay Pratap Singh', 'Manish Kumar Thakur', 'Nipun Singh',
        'Aikansh Katiyar'
      ] },
      { label: 'Email Clearance', members: [
        'Deepika S', 'Lavanya Dani', 'Riya Sinha', 'Sakshi Upesh Kamani', 'Md. Parvezuddin',
        'Divya Harish', 'Sanskar Shrivastava'
      ] }
    ] },
    { channel_id: 'C023SD1L2E7', channel_name: '#sv-in-ops-misc-checks', categories: [
      { label: 'MISC', members: [
        'Pratyush Badhani', 'Samriddhi Kundu', 'B Hemanth Reddy', 'Kousik Ruidas', 'Samraggee Saha',
        'Swati Jampal', 'Abhraneel Chattopadhyay', 'Shivam Kumar Jha', 'Pavithra M'
      ] },
      { label: 'Payment Settlement', members: ['Barsha Agarwal', 'Shivam Bhardwaj'] }
    ] },
    { channel_id: 'C08TMLA7YSU', channel_name: '#sv-in-ops-research', categories: [
      { label: 'Research', members: [
        'Daraksha Hussain', 'Shuman Thappa', 'Satarupa Konar', 'Al Hasan', 'Adithyan S', 'Aman Raj',
        'Hasamuddin Ansari', 'Ballani Venkata Avinas', 'Poojasri Adambhakam'
      ] }
    ] },
    { channel_id: 'C08MMSLV43H', channel_name: '#sv-in-ops-ref', categories: [
      { label: 'Reference', members: ['Nazia Hasan', 'Sakshi Bhuyan', 'Kishore M', 'Raunak Kumar', 'Sahil'] }
    ] },
    { channel_id: 'C07QAABSJ6R', channel_name: '#sv-in-ops-additional-tasks', categories: [
      { label: 'Case Addition', members: [
        'Manas Kumar Mishra', 'Abhay Chandrakant Nayak', 'Rahul Sutradhar', 'Ankita Basak',
        'Chirag Sethi', 'Sonia Thakur'
      ] }
    ] }
  ];

  var CATEGORY_TAGS = {
    'Grading':            { usergroup: 'S0BKVL7E0SH', lead: 'UN1E2L4G0' },
    'QC':                 { usergroup: 'S046ESUQLS1', lead: 'U03BUG17X54' },
    'CA + Initiation':    { usergroup: 'S046WGXTBED', lead: 'U017K6KQT2A' },
    'Research':           { usergroup: 'S08VARCA849', lead: 'UN1E2L4G0' },
    'Reference':          { usergroup: 'S04K6P0CYES', lead: 'UN1E2L4G0' },
    'Payment Settlement': { usergroup: 'S0BKX213HFG', lead: 'U017K6KQT2A' },
    'MISC':               { usergroup: 'S05BY1H4HJ5', lead: 'U017K6KQT2A' },
    'Email Clearance':    { usergroup: 'S0BKZ13RE82', lead: 'U03BUG17X54' },
    'Followups':          { usergroup: 'S0BLTALCZA4', lead: 'UURRMS3MG' },
    'Case Addition':      { usergroup: 'S086WH7H6A0', lead: 'UURRMS3MG' }
  };

  var TASK_TYPE_INFO = {
    CASE_ANALYSIS: ['CA', 'Case Analysis'], INITIATION: ['INIT', 'Initiation'],
    QC: ['QC', 'QC'], GRADING: ['GRD', 'Grading'], FOLLOW_UP: ['FU', 'Follow Up'],
    EMAIL_CLEARANCE: ['EC', 'Email Clearance'], PAYMENTS_SETTLEMENT: ['PS', 'Payment Settlement'],
    ADDITIONAL_TASKS: ['AT', 'Additional Tasks'], RESEARCH: ['RES', 'Research'],
    RESEARCH_FOLLOW_UP: ['RFU', 'Research Follow Up'], INSUFFICIENCY_CLEARANCE: ['IC', 'Insufficiency Clearance'],
    VENDOR_MANAGEMENT: ['VM', 'Vendor Management'], CONSENT_REVIEW: ['CR', 'Consent Review'],
    DOCUMENTS_CROPPING: ['DC', 'Documents Cropping'], WHATSAPP_CLEARANCE: ['WC', 'WhatsApp Clearance'],
    WHATSAPP_FOLLOW_UP: ['WFU', 'WhatsApp Follow Up']
  };

  // (name, type, shift, daily_target, cohort)
  var ROSTER = [
    ['Subhashree L', 'FTE', 'MF', 270, null], ['Priyanka Krishnan', 'FTE', 'MF', 270, null],
    ['Manash Pratim Kashyap', 'FTE', 'MF', 270, null], ['Anitha Sagari Ravirala', 'FTE', 'TS', 270, null],
    ['Aaiyana Vinod Sharma', 'FTE', 'TS', 270, null], ['Abhishek Parashari', 'Intern', 'MF', 250, 4],
    ['Abhishek Rawat', 'Intern', 'MF', 250, 4], ['Adithya Padmanabhan', 'Intern', 'MF', 250, 4],
    ['Indukuri Niranjan Reddy', 'Intern', 'MF', 250, 4], ['Ishita Mishra', 'Intern', 'MF', 250, 4],
    ['Divyajot Kaur', 'Intern', 'MF', 250, 4], ['Mohd Azfar Khan', 'Intern', 'MF', 250, 4],
    ['Noshin M K', 'Intern', 'MF', 250, 4], ['Anand Kumar', 'Intern', 'MF', 250, 4],
    ['Chinthala VSSSL Mokshajna', 'Intern', 'MF', 250, 4], ['Anmol Sharma', 'Intern', 'MF', 250, 4],
    ['Kondeti Ashvitha', 'Intern', 'MF', 250, null], ['Sahil Vilas Mule', 'Intern', 'MF', 250, null],
    ['Nishmeet Singh Rajpal', 'Intern', 'MF', 250, null],

    ['Dithya Ann Mathew', 'FTE', 'MF', 200, null],
    ['Chirumamilla Hamsa Veni', 'Intern', 'MF', 180, 3], ['Puneesh Hingorani', 'Intern', 'MF', 180, 4],
    ['Shambhavi Kumari', 'Intern', 'MF', 180, 4], ['Vikas Bishnoi', 'Intern', 'MF', 180, 4],
    ['Akhil', 'Intern', 'MF', 180, 4], ['K Sai Vaishnav Kumar', 'Intern', 'MF', 180, 4],
    ['Utkarsh Raj', 'Intern', 'MF', 180, 4], ['Abhishek Mohan', 'Intern', 'MF', 180, 4],
    ['Surya Pratap', 'Intern', 'MF', 180, 4], ['Jay Pawar', 'Intern', 'MF', 180, 4],
    ['Rohan Kumarraju', 'Intern', 'MF', 180, 6], ['Mohamed Waseem kurikkal M P', 'Intern', 'MF', 180, 6],
    ['Shreshth Sahu', 'Intern', 'MF', 180, 6], ['Lakshit Raina', 'Intern', 'MF', 180, 6],
    ['Anisha Kumari', 'Intern', 'MF', 180, 6],
    ['E Tarun', 'Intern', 'MF', 180, null], ['Shaeeshta Shaila', 'Intern', 'MF', 180, null],
    ['Peddireddy Vasu Deva Reddy', 'Intern', 'MF', 180, null], ['Priyanka Lohia', 'Intern', 'MF', 180, null],
    ['Pentapalli Charan', 'Intern', 'MF', 180, null],

    ['Vikash Sunaliya', 'FTE', 'MF', 260, null], ['Shafaque Shadni', 'FTE', 'TS', 260, null],
    ['Mohammad Sameem Nazki', 'FTE', 'MF', 260, null], ['Shlok Paliwal', 'FTE', 'TS', 260, null],
    ['Vanshika Sharma', 'FTE', 'TS', 260, null], ['Utsav Banerjee', 'FTE', 'MF', 260, null],
    ['Nishant Gupta', 'Intern', 'MF', 240, 1], ['Manpreet Kaur', 'Intern', 'MF', 240, 1],
    ['Alisha Chaudhary', 'Intern', 'MF', 240, 1], ['Mitta Ruthika', 'Intern', 'MF', 240, 1],
    ['Harshitha Sakkuri', 'Intern', 'MF', 240, 2], ['Chuppa Harshitha', 'Intern', 'MF', 240, 2],
    ['Talwinder Singh', 'Intern', 'MF', 240, 4], ['Tanisha Thakur', 'Intern', 'MF', 240, 4],
    ['Subhajit Debbarma', 'Intern', 'MF', 240, 4], ['Saransh Jaggi', 'Intern', 'MF', 240, 4],
    ['Anushka Jaiswal', 'Intern', 'MF', 240, 4], ['Abhishek Sangwan', 'Intern', 'MF', 240, 4],
    ['Sachin Kumar Singh', 'Intern', 'MF', 240, 4], ['Vinay Pratap Singh', 'Intern', 'MF', 240, 6],
    ['Manish Kumar Thakur', 'Intern', 'MF', 240, 6], ['Nipun Singh', 'Intern', 'MF', 240, 6],
    ['Aikansh Katiyar', 'Intern', 'MF', 240, 6],

    ['Pratyush Badhani', 'FTE', 'TS', 250, null], ['Samriddhi Kundu', 'FTE', 'MF', 250, null],
    ['B Hemanth Reddy', 'FTE', 'TS', 250, null], ['Kousik Ruidas', 'FTE', 'MF', 250, null],
    ['Samraggee Saha', 'FTE', 'MF', 250, null], ['Swati Jampal', 'FTE', 'TS', 250, null],
    ['Abhraneel Chattopadhyay', 'FTE', 'MF', 250, null], ['Shivam Kumar Jha', 'FTE', 'MF', 250, null],
    ['Pavithra M', 'FTE', 'TS', 250, null],

    ['Barsha Agarwal', 'FTE', 'MF', 140, null], ['Shivam Bhardwaj', 'FTE', 'TS', 140, null],

    ['Daraksha Hussain', 'FTE', 'MF', 130, null], ['Shuman Thappa', 'FTE', 'TS', 130, null],
    ['Satarupa Konar', 'FTE', 'MF', 130, null], ['Al Hasan', 'FTE', 'MF', 130, null],
    ['Poojasri Adambhakam', 'FTE', 'TS', 130, null], ['Adithyan S', 'Intern', 'MF', 115, 5],
    ['Aman Raj', 'Intern', 'MF', 115, 5], ['Hasamuddin Ansari', 'Intern', 'MF', 115, 5],
    ['Ballani Venkata Avinas', 'Intern', 'MF', 115, 5],

    ['Nazia Hasan', 'FTE', 'TS', 195, null], ['Sakshi Bhuyan', 'FTE', 'MF', 195, null],
    ['Kishore M', 'FTE', 'MF', 195, null], ['Raunak Kumar', 'Intern', 'MF', 170, 5],
    ['Sahil', 'Intern', 'MF', 170, 5],

    ['Manas Kumar Mishra', 'FTE', 'TS', 55, null], ['Abhay Chandrakant Nayak', 'FTE', 'TS', 55, null],
    ['Rahul Sutradhar', 'FTE', 'MF', 55, null], ['Ankita Basak', 'FTE', 'MF', 55, null],
    ['Chirag Sethi', 'FTE', 'MF', 55, null], ['Sonia Thakur', 'FTE', 'TS', 55, null],

    ['Nishika Dwivedi', 'FTE', 'TS', 145, null], ['Anindita Maity', 'FTE', 'TS', 145, null],
    ['Jillella Akshaya Prajwala', 'FTE', 'TS', 145, null], ['Bevara Hemanth Kumar', 'FTE', 'MF', 145, null],
    ['Navaneetha KS', 'FTE', 'MF', 140, null], ['D Joyce Blessia', 'FTE', 'TS', 140, null],
    ['Nara Sumanth', 'Intern', 'MF', 120, 5], ['Mehak Rajput', 'Intern', 'MF', 120, 5],
    ['Manisha Suresh Yadav', 'FTE', 'MF', 110, null], ['Shaik Suraj', 'FTE', 'MF', 110, null],
    ['Vivek Kumar Singh', 'FTE', 'MF', 110, null], ['Tapas Patra', 'FTE', 'MF', 110, null],
    ['Aishu Ji Lochan', 'Intern', 'MF', 95, 3], ['Pranshu', 'Intern', 'MF', 95, 3],
    ['Aishwarya Arya', 'Intern', 'MF', 95, 4], ['Samiksha Pilaniya', 'Intern', 'MF', 95, 4],
    ['P Swarna Lakshmi', 'FTE', 'MF', 110, null], ['Dharani Lakshmi', 'FTE', 'MF', 110, null],
    ['Gayathri A', 'FTE', 'MF', 110, null], ['Udita Singh', 'FTE', 'MF', 110, null],

    ['Deepika S', 'FTE', 'MF', 220, null], ['Lavanya Dani', 'FTE', 'TS', 220, null],
    ['Riya Sinha', 'Intern', 'MF', 195, 5],
    ['Sakshi Upesh Kamani', 'FTE', 'TS', 220, null], ['Md. Parvezuddin', 'Intern', 'MF', 195, 5],
    ['Divya Harish', 'FTE', 'MF', 325, null], ['Sanskar Shrivastava', 'FTE', 'TS', 325, null]
  ];

  var NEW_JOINERS = { 'Vinay Pratap Singh': true, 'Manish Kumar Thakur': true, 'Nipun Singh': true, 'Aikansh Katiyar': true };

  var NAME_PREFIXES = [
    'Payment Settlement', 'Customer Ops', 'Q C', 'R T', 'C S', 'A T', 'V M',
    'C A', 'Add', 'Grading', 'Initiation', 'Misc', 'Supp', 'Ops', 'Edu',
    'Emp', 'Ref', 'Dev', 'Res'
  ];

  var MAX_MESSAGE_CHARS = 3500;

  // ── SMALL HELPERS ────────────────────────────────────────────

  function scriptProp(name) {
    return PropertiesService.getScriptProperties().getProperty(name);
  }

  function humanize(v) {
    if (!v || v === 'N/A') return 'N/A';
    return v.replace(/-/g, '_').split('_').map(function (w) {
      return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
    }).join(' ');
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
    return new Set(spaced.split(/\s+/).filter(Boolean));
  }

  function setEquals(a, b) {
    if (a.size !== b.size) return false;
    for (var x of a) if (!b.has(x)) return false;
    return true;
  }
  function isSubset(a, b) {
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

  /** candidateDict: plain object key -> value. Mirrors Python's best_match(). */
  function bestMatch(targetName, candidateDict) {
    var key = cleanName(targetName);
    var keys = Object.keys(candidateDict);
    for (var i = 0; i < keys.length; i++) {
      if (cleanName(keys[i]) === key) return candidateDict[keys[i]];
    }
    var tTokens = nameTokens(targetName);
    if (!tTokens.size) return null;
    var best = null, bestTier = null, bestOverlap = -1, ties = 0;
    for (var j = 0; j < keys.length; j++) {
      var k = keys[j];
      var cTokens = nameTokens(k);
      if (!cTokens.size) continue;
      var tier = namesCompatible(tTokens, cTokens);
      if (tier === null) continue;
      var overlap = setIntersectSize(tTokens, cTokens);
      if (bestTier === null || tier < bestTier || (tier === bestTier && overlap > bestOverlap)) {
        bestTier = tier; bestOverlap = overlap; best = candidateDict[k]; ties = 1;
      } else if (tier === bestTier && overlap === bestOverlap) {
        ties += 1;
      }
    }
    return ties > 1 ? null : best;
  }

  function ordinal(n) {
    if (n >= 11 && n <= 13) return n + 'th';
    return n + ['th', 'st', 'nd', 'rd', 'th'][Math.min(n % 10, 4)];
  }
  var MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];
  function fmtDateYMD(y, m, d) {
    return ordinal(d) + ' ' + MONTH_NAMES[m - 1] + ' ' + y;
  }

  function fmt(v, suffix) {
    suffix = suffix || '';
    if (v === null || v === undefined) return '-';
    if (typeof v === 'number' && Number.isInteger(v) === false && v === Math.trunc(v)) v = Math.trunc(v);
    return String(v) + suffix;
  }

  // ── DATE RANGE: previous Monday-Sunday, unless overridden ──

  function pyWeekday(y, m, d) {
    // Python date.weekday(): Monday=0 ... Sunday=6.
    var jsDay = new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // Sunday=0..Saturday=6
    return (jsDay + 6) % 7;
  }

  function addDaysYMD(y, m, d, delta) {
    var dt = new Date(Date.UTC(y, m - 1, d + delta));
    return { y: dt.getUTCFullYear(), m: dt.getUTCMonth() + 1, d: dt.getUTCDate() };
  }

  function ymdToUtcMidnight(y, m, d) {
    return Utilities.formatDate(new Date(Date.UTC(y, m - 1, d, 0, 0, 0)), 'Etc/UTC', 'yyyy-MM-dd HH:mm:ss');
  }

  function ymdKey(ymd) { return ymd.y * 10000 + ymd.m * 100 + ymd.d; }
  function ymdCompare(a, b) { return ymdKey(a) - ymdKey(b); }
  function ymdMax(a, b) { return ymdCompare(a, b) >= 0 ? a : b; }
  function ymdMin(a, b) { return ymdCompare(a, b) <= 0 ? a : b; }
  function ymdDiffDays(a, b) { // a - b, in days
    return Math.round((Date.UTC(a.y, a.m - 1, a.d) - Date.UTC(b.y, b.m - 1, b.d)) / 86400000);
  }

  function computeDateRange(overrideStart, overrideEnd) {
    var startY, startM, startD, endY, endM, endD;
    if (overrideStart && overrideEnd) {
      var sp = overrideStart.split('-').map(Number);
      var ep = overrideEnd.split('-').map(Number);
      startY = sp[0]; startM = sp[1]; startD = sp[2];
      endY = ep[0]; endM = ep[1]; endD = ep[2];
    } else {
      var nowIst = new Date(new Date().getTime() + IST_OFFSET_MS);
      var todayY = nowIst.getUTCFullYear(), todayM = nowIst.getUTCMonth() + 1, todayD = nowIst.getUTCDate();
      var wd = pyWeekday(todayY, todayM, todayD);
      var thisMonday = addDaysYMD(todayY, todayM, todayD, -wd);
      var start = addDaysYMD(thisMonday.y, thisMonday.m, thisMonday.d, -7);
      var end = addDaysYMD(thisMonday.y, thisMonday.m, thisMonday.d, -1);
      startY = start.y; startM = start.m; startD = start.d;
      endY = end.y; endM = end.m; endD = end.d;
    }
    var START = { y: startY, m: startM, d: startD };
    var END = { y: endY, m: endM, d: endD };
    var numDays = ymdDiffDays(END, START) + 1;
    var startUtc = ymdToUtcMidnight(START.y, START.m, START.d);
    var endPlus1 = addDaysYMD(END.y, END.m, END.d, 1);
    var endUtc = ymdToUtcMidnight(endPlus1.y, endPlus1.m, endPlus1.d);
    var dateLabel = fmtDateYMD(START.y, START.m, START.d) + ' - ' + fmtDateYMD(END.y, END.m, END.d);
    return { START: START, END: END, numDays: numDays, startUtc: startUtc, endUtc: endUtc, dateLabel: dateLabel };
  }

  function workingDaysInRange(shift, start, end) {
    var days = ymdDiffDays(end, start) + 1;
    var count = 0;
    for (var i = 0; i < days; i++) {
      var d = addDaysYMD(start.y, start.m, start.d, i);
      var wd = pyWeekday(d.y, d.m, d.d);
      if (shift === 'MF' && wd <= 4) count++;
      else if (shift === 'TS' && wd >= 1 && wd <= 5) count++;
    }
    return count;
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
    for (var i = 0; i < 45; i++) {
      Utilities.sleep(2000);
      var jr = httpJson('get', REDASH_BASE + '/api/jobs/' + jobId, headers);
      var job = jr.job || {};
      if (job.status === 3) {
        var rr = httpJson('get', REDASH_BASE + '/api/query_results/' + job.query_result_id, headers);
        return rr.query_result.data.rows;
      }
      if (job.status === 4) throw new Error('Redash query failed: ' + job.error);
    }
    throw new Error('Redash ad-hoc query timed out');
  }

  function fetchAdhoc(sql) {
    var retries = 2;
    for (var attempt = 0; attempt <= retries; attempt++) {
      try {
        return fetchAdhocOnce(sql);
      } catch (e) {
        if (attempt === retries) throw e;
        Utilities.sleep(5000);
      }
    }
  }

  function fetchCompleted(startUtc, endUtc) {
    var sql = "" +
      "        SELECT u.name AS \"Agent Name\", tt.value AS \"Task Type\", COALESCE(ct.value, 'N/A') AS \"Check Type\",\n" +
      "            COUNT(DISTINCT ts.id) AS \"Completed Count\"\n" +
      "        FROM tasks ts\n" +
      "        INNER JOIN users u ON u.id = ts.completed_by_user_id_fk\n" +
      "        INNER JOIN enums tt ON ts.task_type = tt.id AND tt.type = 'TEAM_TYPE' AND tt.deleted_at IS NULL\n" +
      "        LEFT JOIN enums ct ON ts.check_type = ct.id AND ct.deleted_at IS NULL\n" +
      "        WHERE ts.deleted_at IS NULL\n" +
      "          AND ts.task_completed_at >= '" + startUtc + "' AND ts.task_completed_at < '" + endUtc + "'\n" +
      "          AND ts.task_status = (SELECT id FROM enums WHERE type='TASK_STATUS' AND value='COMPLETED' AND deleted_at IS NULL LIMIT 1)\n" +
      "          AND ts.completed_by_user_id_fk NOT IN (4, 17542)\n" +
      "        GROUP BY u.name, tt.value, ct.value ORDER BY u.name, tt.value, ct.value\n";
    return fetchAdhoc(sql);
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
      "          AND UPPER(e.status) IN ('NEW', 'RECTIFIED', 'CLOSED')\n" +
      "          AND (dept_enum.value = 'OPERATIONS' OR LOWER(u.name) LIKE '%system user%' OR LOWER(u.name) LIKE '%springverify ai%')\n" +
      "        GROUP BY u.name ORDER BY u.name\n";
    return fetchAdhoc(sql);
  }

  function fetchCaseAdditions(startUtc, endUtc) {
    var sql = "" +
      "        WITH consent_events AS (\n" +
      "            SELECT cl.candidate_id_fk,\n" +
      "                CASE WHEN cl.user_type = 1 THEN cl.user_id_fk ELSE cl.proxy_user_id_fk END AS adder_user_id,\n" +
      "                CASE WHEN cl.user_type = 1 THEN 'DIRECT' ELSE 'PROXY' END AS adder_type,\n" +
      "                cl.created_at AS add_at, 0 AS priority\n" +
      "            FROM candidate_logs cl\n" +
      "            WHERE cl.type = 'CANDIDATE_CONSENT_ADDED' AND cl.deleted_at IS NULL\n" +
      "              AND ((cl.user_type = 1 AND cl.user_id_fk IS NOT NULL) OR (cl.user_type = 2 AND cl.proxy_user_id_fk IS NOT NULL))\n" +
      "              AND cl.created_at >= DATE_SUB('" + startUtc + "', INTERVAL 30 DAY) AND cl.created_at < '" + endUtc + "'\n" +
      "        ),\n" +
      "        consent_exists AS (\n" +
      "            SELECT DISTINCT candidate_id_fk FROM candidate_logs\n" +
      "            WHERE type = 'CANDIDATE_CONSENT_ADDED' AND deleted_at IS NULL\n" +
      "              AND created_at >= DATE_SUB('" + startUtc + "', INTERVAL 30 DAY) AND created_at < '" + endUtc + "'\n" +
      "        ),\n" +
      "        basic_info_fallback AS (\n" +
      "            SELECT cl.candidate_id_fk,\n" +
      "                CASE WHEN cl.user_type = 1 THEN cl.user_id_fk ELSE cl.proxy_user_id_fk END AS adder_user_id,\n" +
      "                CASE WHEN cl.user_type = 1 THEN 'DIRECT' ELSE 'PROXY' END AS adder_type,\n" +
      "                cl.created_at AS add_at, 1 AS priority\n" +
      "            FROM candidate_logs cl\n" +
      "            WHERE cl.type = 'CANDIDATE_BASIC_INFO_UPDATED' AND cl.deleted_at IS NULL\n" +
      "              AND ((cl.user_type = 1 AND cl.user_id_fk IS NOT NULL) OR (cl.user_type = 2 AND cl.proxy_user_id_fk IS NOT NULL))\n" +
      "              AND cl.created_at >= DATE_SUB('" + startUtc + "', INTERVAL 30 DAY) AND cl.created_at < '" + endUtc + "'\n" +
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
      "            SELECT ccm.candidate_id, ccm.form_filled,\n" +
      "                CASE WHEN ccm.form_filled_by = 1 THEN ccm.form_filled_by_user_id\n" +
      "                     WHEN ccm.form_filled_by = 3 THEN ccm.proxy_user_id ELSE NULL END AS filler_user_id\n" +
      "            FROM company_candidate_mapping ccm\n" +
      "            WHERE ccm.deleted_at IS NULL\n" +
      "              AND ccm.created_at >= DATE_SUB('" + startUtc + "', INTERVAL 30 DAY) AND ccm.created_at < '" + endUtc + "'\n" +
      "        ),\n" +
      "        combined AS (\n" +
      "            SELECT ca.candidate_id_fk, ca.adder_user_id, ca.adder_type, ca.add_at, f.form_filled, f.filler_user_id\n" +
      "            FROM canonical_add ca LEFT JOIN fills f ON f.candidate_id = ca.candidate_id_fk\n" +
      "            UNION\n" +
      "            SELECT f.candidate_id AS candidate_id_fk, ca.adder_user_id, ca.adder_type, ca.add_at, f.form_filled, f.filler_user_id\n" +
      "            FROM fills f LEFT JOIN canonical_add ca ON ca.candidate_id_fk = f.candidate_id\n" +
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
      "            UNION ALL SELECT candidate_id_fk, b2_user, 0, 1, 0, 0, b2_date FROM tagged WHERE b2_user IS NOT NULL\n" +
      "            UNION ALL SELECT candidate_id_fk, b3_user, 0, 0, 1, 0, b3_date FROM tagged WHERE b3_user IS NOT NULL\n" +
      "            UNION ALL SELECT candidate_id_fk, b4_user, 0, 0, 0, 1, b4_date FROM tagged WHERE b4_user IS NOT NULL\n" +
      "        )\n" +
      "        SELECT u.name AS \"Agent Name\", SUM(pac.added_and_filled) AS \"Added & Filled\",\n" +
      "            SUM(pac.added_not_filled) AS \"Added, Not Filled\", SUM(pac.filled_only) AS \"Filled Only\",\n" +
      "            SUM(pac.proxy_added) AS \"Proxy Added\"\n" +
      "        FROM per_agent_candidate pac JOIN users u ON u.id = pac.agent_user_id\n" +
      "        WHERE pac.credit_date >= '" + startUtc + "' AND pac.credit_date < '" + endUtc + "'\n" +
      "        GROUP BY u.name ORDER BY u.name\n";
    return fetchAdhoc(sql);
  }

  // ── AGGREGATE ───────────────────────────────────────────────

  function newAgent() {
    return { display_name: null, task_totals: {}, task_check: {}, completed_total: 0, error_total: 0, case_add_total: 0 };
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
      var rawTt = row['Task Type'] || '';
      var info = TASK_TYPE_INFO[rawTt] || [humanize(rawTt).slice(0, 4).toUpperCase(), humanize(rawTt)];
      var abbr = info[0];
      var checkRaw = row['Check Type'];
      var count = parseInt(row['Completed Count'] || 0, 10);
      var d = getAgent(data, key);
      d.display_name = d.display_name || rawName;
      d.task_totals[abbr] = (d.task_totals[abbr] || 0) + count;
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
      var d = getAgent(data, key);
      d.display_name = d.display_name || rawName;
      d.error_total += parseInt(row['Error Count'] || 0, 10);
    });
    caseAddRows.forEach(function (row) {
      var rawName = row['Agent Name'] || '';
      var key = cleanName(rawName);
      if (!key) return;
      var af = parseInt(row['Added & Filled'] || 0, 10);
      var fo = parseInt(row['Filled Only'] || 0, 10);
      var pa = parseInt(row['Proxy Added'] || 0, 10);
      var d = getAgent(data, key);
      d.display_name = d.display_name || rawName;
      d.case_add_total += af + fo + pa;
    });
    return data;
  }

  function resolveMemberAssignments(agentData) {
    var tokenIndex = Object.keys(agentData).map(function (key) { return [key, nameTokens(key)]; });
    var allMembers = [];
    CHANNELS.forEach(function (ch) {
      ch.categories.forEach(function (c) {
        c.members.forEach(function (m) { allMembers.push([c.label, m]); });
      });
    });
    var exactOwner = {}, claims = {};
    allMembers.forEach(function (pair) {
      var label = pair[0], member = pair[1];
      var key = cleanName(member);
      if (agentData[key]) { exactOwner[key] = [label, member]; return; }
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
    var assignKey = function (label, member) { return label + '  ' + member; };
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
    return {
      get: function (label, member) { return assignments[assignKey(label, member)]; },
      set: function (label, member, val) { assignments[assignKey(label, member)] = val; }
    };
  }

  function agentCheckTotals(d) {
    var totals = {};
    Object.keys(d.task_check).forEach(function (abbr) {
      var checks = d.task_check[abbr];
      Object.keys(checks).forEach(function (label) { totals[label] = (totals[label] || 0) + checks[label]; });
    });
    return totals;
  }

  function buildAgentColTable(active, totDone, totErr, colGetter) {
    var colTotals = {};
    active.forEach(function (p) {
      var counts = colGetter(p[1]);
      Object.keys(counts).forEach(function (c) { colTotals[c] = (colTotals[c] || 0) + counts[c]; });
    });
    var cols = Object.keys(colTotals).sort(function (a, b) { return colTotals[b] - colTotals[a]; });
    var nameW = Math.max.apply(null, ['Agent'.length, 'TEAM TOTAL'.length].concat(active.map(function (p) { return p[0].length; }))) + 2;
    var colW = {};
    cols.forEach(function (c) { colW[c] = Math.max(c.length, 5) + 2; });
    var doneW = Math.max('Total'.length, String(totDone).length) + 2;
    var errW = Math.max('Err'.length, String(totErr).length) + 2;
    var header = 'Agent'.padEnd(nameW);
    cols.forEach(function (c) { header += c.padStart(colW[c]); });
    header += 'Total'.padStart(doneW) + 'Err'.padStart(errW);
    var sep = '-'.repeat(header.length);
    var lines = [header, sep];
    active.forEach(function (p) {
      var name = p[0], d = p[1];
      var row = name.padEnd(nameW);
      var counts = colGetter(d);
      cols.forEach(function (c) {
        var v = counts[c] || 0;
        row += (v ? String(v) : '-').padStart(colW[c]);
      });
      row += String(d.completed_total).padStart(doneW) + String(d.error_total).padStart(errW);
      lines.push(row);
    });
    lines.push(sep);
    var totalRow = 'TEAM TOTAL'.padEnd(nameW);
    cols.forEach(function (c) { totalRow += String(colTotals[c]).padStart(colW[c]); });
    totalRow += String(totDone).padStart(doneW) + String(totErr).padStart(errW);
    lines.push(totalRow);
    return lines.join('\n');
  }

  // ── ROSTER lookups ──

  var ROSTER_TARGET = {}, ROSTER_TYPE = {}, ROSTER_COHORT = {};
  ROSTER.forEach(function (r) {
    var key = cleanName(r[0]);
    ROSTER_TARGET[key] = [r[3], r[2]]; // [daily_target, shift]
    ROSTER_TYPE[key] = r[1];
    ROSTER_COHORT[key] = r[4];
  });

  function getTarget(member, leaves, START, END) {
    var hit = bestMatch(member, ROSTER_TARGET);
    if (hit === null || hit === undefined) return { target: null, dailyTarget: null, effectiveDays: null };
    var dailyTarget = hit[0], shift = hit[1];
    var effectiveDays = Math.max(workingDaysInRange(shift, START, END) - leaves, 0);
    return { target: dailyTarget * effectiveDays, dailyTarget: dailyTarget, effectiveDays: effectiveDays };
  }

  function getTypeCohort(member) {
    var key = cleanName(member);
    var typ = ROSTER_TYPE[key];
    var cohort = ROSTER_COHORT[key];
    if (typ === undefined) {
      var keys = Object.keys(ROSTER_TYPE);
      for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var probe = {}; probe[k] = true;
        if (bestMatch(member, probe)) { typ = ROSTER_TYPE[k]; cohort = ROSTER_COHORT[k]; break; }
      }
    }
    return { typ: typ, cohort: cohort };
  }

  // ── Google Sheets (Leave / WFH / Call Log) via SpreadsheetApp ──

  function parseDmy(s) {
    s = (s || '').trim();
    var m = /^(\d{1,2})-([A-Za-z]+)-(\d{4})$/.exec(s);
    if (!m) throw new Error('Unrecognized date: ' + JSON.stringify(s));
    var day = parseInt(m[1], 10);
    var monName = m[2].toLowerCase();
    var year = parseInt(m[3], 10);
    var monthIdx = MONTH_NAMES.findIndex(function (mn) {
      return mn.toLowerCase() === monName || mn.toLowerCase().indexOf(monName) === 0;
    });
    if (monthIdx < 0) throw new Error('Unrecognized date: ' + JSON.stringify(s));
    return { y: year, m: monthIdx + 1, d: day };
  }

  function getRangeValues(ss, sheetName, a1Range) {
    var sheet = ss.getSheetByName(sheetName);
    if (!sheet) return [];
    return sheet.getRange(a1Range).getValues();
  }

  function fetchLeaveTotals(ss, START, END) {
    var rows = getRangeValues(ss, 'Leave', 'A3:H2000');
    var totals = {};
    rows.forEach(function (row) {
      if (row.length < 8 || !row[1]) return;
      var name = String(row[1]);
      var dFrom, dTo, dur;
      try {
        dFrom = parseDmy(String(row[3]));
        dTo = parseDmy(String(row[5]));
        dur = parseFloat(row[7]);
        if (isNaN(dur)) return;
      } catch (e) { return; }
      var lo = ymdMax(dFrom, START), hi = ymdMin(dTo, END);
      if (ymdCompare(lo, hi) > 0) return;
      var overlap;
      if (ymdKey(dFrom) === ymdKey(dTo)) {
        overlap = dur;
      } else {
        overlap = 0;
        var span = ymdDiffDays(hi, lo) + 1;
        for (var i = 0; i < span; i++) {
          var day = addDaysYMD(lo.y, lo.m, lo.d, i);
          if (pyWeekday(day.y, day.m, day.d) <= 4) overlap++;
        }
      }
      var key = cleanName(name);
      totals[key] = (totals[key] || 0) + overlap;
    });
    return totals;
  }

  function fetchWfhTotals(ss, START, END) {
    var rows = getRangeValues(ss, 'Leave', 'J3:N2000');
    var totals = {};
    rows.forEach(function (row) {
      if (row.length < 4 || !row[1]) return;
      var name = String(row[1]);
      var dFrom, dTo;
      try {
        dFrom = parseDmy(String(row[2]));
        dTo = parseDmy(String(row[3]));
      } catch (e) { return; }
      var lo = ymdMax(dFrom, START), hi = ymdMin(dTo, END);
      if (ymdCompare(lo, hi) > 0) return;
      var key = cleanName(name);
      totals[key] = (totals[key] || 0) + (ymdDiffDays(hi, lo) + 1);
    });
    return totals;
  }

  function fetchCallTotals(ss, START, END) {
    var headerRows = getRangeValues(ss, 'Call Log', 'A1:A2');
    var headerText = headerRows.map(function (r) { return r.join(' '); }).join(' ');
    var m = /(\d{1,2}) to (\d{1,2}) (\w+) (\d{4})/.exec(headerText);
    if (m) {
      try {
        var lo = parseDmy(m[1] + '-' + m[3] + '-' + m[4]);
        var hi = parseDmy(m[2] + '-' + m[3] + '-' + m[4]);
        if (!(ymdCompare(lo, START) <= 0 && ymdCompare(hi, END) >= 0)) {
          Logger.log('  Call Log sheet covers ' + JSON.stringify(lo) + '..' + JSON.stringify(hi) + ', not this week — skipping calls');
          return {};
        }
      } catch (e) { /* fall through, matches Python's bare except ValueError: pass */ }
    }
    var rows = getRangeValues(ss, 'Call Log', 'A4:J200');
    var totals = {};
    rows.forEach(function (row) {
      if (row.length < 10 || !row[0] || !/^\d+$/.test(String(row[3]).trim())) return;
      var nameOnly = String(row[0]).replace(/\s*\(\+?\d[\d\- ]*\)\s*$/, '').trim();
      var key = cleanName(nameOnly);
      var totalC = parseInt(row[3], 10), connC = parseInt(row[8], 10) || 0;
      if (totals[key]) {
        totals[key] = [totals[key][0] + totalC, totals[key][1] + connC];
      } else {
        totals[key] = [totalC, connC];
      }
    });
    return totals;
  }

  // ── SLACK ────────────────────────────────────────────────────

  function chunkMessage(text) {
    var maxLen = MAX_MESSAGE_CHARS;
    if (text.length <= maxLen) return [text];
    var chunks = [], current = '', inCodeBlock = false;
    text.split('\n').forEach(function (line) {
      var candidate = current ? (current + '\n' + line) : line;
      if (candidate.length > maxLen && current) {
        if (inCodeBlock) { chunks.push(current + '\n```'); current = '```\n' + line; }
        else { chunks.push(current); current = line; }
      } else {
        current = candidate;
      }
      if (line.trim() === '```') inCodeBlock = !inCodeBlock;
    });
    if (current) chunks.push(current);
    return chunks;
  }

  function postSlackMessage(slackToken, channelId, text, threadTs) {
    var lastTs = null;
    chunkMessage(text).forEach(function (chunk) {
      var payload = { channel: channelId, text: chunk };
      if (threadTs) payload.thread_ts = threadTs;
      var resp = httpJson('post', 'https://slack.com/api/chat.postMessage',
        { Authorization: 'Bearer ' + slackToken, 'Content-Type': 'application/json' }, payload);
      if (!resp.ok) throw new Error('Slack API error for channel ' + channelId + ': ' + resp.error);
      lastTs = resp.ts;
      if (!threadTs) threadTs = lastTs;
    });
    return lastTs;
  }

  // ── main ──

  /**
   * @param {string} [overrideStart] YYYY-MM-DD
   * @param {string} [overrideEnd] YYYY-MM-DD
   * @param {string} [testChannelAlias] key into TEST_CHANNEL_ALIASES
   */
  function run(overrideStart, overrideEnd, testChannelAlias) {
    var slackToken = scriptProp('SLACK_BOT_TOKEN');
    var testChannelId = testChannelAlias ? TEST_CHANNEL_ALIASES[testChannelAlias] : '';

    var range = computeDateRange(overrideStart, overrideEnd);
    var START = range.START, END = range.END, DATE_LABEL = range.dateLabel;
    Logger.log('Weekly report for ' + DATE_LABEL + ' (' + range.startUtc + ' -> ' + range.endUtc + ')');

    var completedRows = fetchCompleted(range.startUtc, range.endUtc);
    var errorRows = fetchErrors(range.startUtc, range.endUtc);
    var caseAddRows = fetchCaseAdditions(range.startUtc, range.endUtc);
    Logger.log('  Completed: ' + completedRows.length + ' rows, Errors: ' + errorRows.length + ', Case adds: ' + caseAddRows.length);

    var agentData = buildAgentData(completedRows, errorRows, caseAddRows);
    var assignments = resolveMemberAssignments(agentData);

    // Known name-collision bug (also present in the Python source): a bare
    // single first-name match ("Manish" vs "Manish Kumar Thakur") wrongly
    // attaches an unrelated Customer Support agent's numbers to this QC intern.
    assignments.set('QC', 'Manish Kumar Thakur', null);

    var leaveTotals = {}, wfhTotals = {}, callTotals = {};
    try {
      var ss = SpreadsheetApp.openById(BOUNTY_SHEET_ID);
      leaveTotals = fetchLeaveTotals(ss, START, END);
      wfhTotals = fetchWfhTotals(ss, START, END);
      callTotals = fetchCallTotals(ss, START, END);
      Logger.log('  Leave rows: ' + Object.keys(leaveTotals).length + ', WFH rows: ' + Object.keys(wfhTotals).length + ', Call rows: ' + Object.keys(callTotals).length);
    } catch (exc) {
      Logger.log('  WARNING: Google Sheets fetch failed (' + exc + ') — Leave/WFH/Calls will show as unavailable this run. Make sure this script has at least Viewer access to the Bounty sheet.');
    }

    var below70 = [];

    CHANNELS.forEach(function (channel) {
      channel.categories.forEach(function (category) {
        var label = category.label;
        var members = category.members;

        var rows = [];
        var unmatched = [];
        members.forEach(function (member) {
          var d = assignments.get(label, member);
          var completed = d ? d.completed_total : 0;
          var errors = d ? d.error_total : 0;
          var caseAdd = d ? d.case_add_total : 0;
          var displayName = (d ? d.display_name : null) || member;
          var leaves = leaveTotals[cleanName(member)] || bestMatch(member, leaveTotals) || 0;
          var wfh = wfhTotals[cleanName(member)] || bestMatch(member, wfhTotals) || 0;
          var tgt = getTarget(member, leaves, START, END);
          var callHit = callTotals[cleanName(member)] || bestMatch(member, callTotals) || [0, 0];
          var totalCalls = callHit[0], connCalls = callHit[1];
          if (!d && totalCalls === 0 && leaves === 0 && wfh === 0 && tgt.target === null && caseAdd === 0) {
            unmatched.push(member);
          }
          var achievedMetric = CASE_ADD_TARGET_TEAMS[label] ? caseAdd : completed;
          var avgDay = tgt.effectiveDays ? Math.round((achievedMetric / tgt.effectiveDays) * 10) / 10
            : (tgt.dailyTarget === null ? Math.round((achievedMetric / range.numDays) * 10) / 10 : 0);
          var pctAchieved = tgt.target ? Math.round((achievedMetric / tgt.target) * 1000) / 10 : null;
          var connPct = totalCalls ? Math.round((connCalls / totalCalls) * 1000) / 10 : null;
          rows.push({
            name: displayName, completed: completed, errors: errors, avg_day: avgDay,
            total_calls: totalCalls, conn_pct: connPct, target: tgt.target, daily_target: tgt.dailyTarget,
            pct_achieved: pctAchieved, leaves: leaves, wfh: wfh, case_add: caseAdd
          });
        });
        rows.sort(function (a, b) { return (b.completed - a.completed) || (b.case_add - a.case_add); });

        var showCalls = rows.some(function (r) { return r.total_calls; });
        var showCase = rows.some(function (r) { return r.case_add; });
        var cols = ['Agent', 'Completed', 'Errors', 'Avg/Day'];
        if (showCalls) cols = cols.concat(['Calls', 'Conn%']);
        cols = cols.concat(['Target/Day', 'Target', '%Ach', 'Leaves', 'WFH']);
        if (showCase) cols.push('Case+');

        var displayRows = rows.map(function (r) {
          var row = [r.name, String(r.completed), String(r.errors), fmt(r.avg_day)];
          if (showCalls) row = row.concat([r.total_calls ? fmt(r.total_calls) : '-', fmt(r.conn_pct, '%')]);
          row = row.concat([fmt(r.daily_target), fmt(r.target), fmt(r.pct_achieved, '%'), fmt(r.leaves), fmt(r.wfh)]);
          if (showCase) row.push(r.case_add ? fmt(r.case_add) : '-');
          return row;
        });
        var widths = cols.map(function (c, i) {
          var maxLen = displayRows.length ? Math.max.apply(null, displayRows.map(function (dr) { return dr[i].length; })) : 0;
          return Math.max(c.length, maxLen) + 2;
        });
        var summaryHeader = cols.map(function (c, i) { return i === 0 ? c.padEnd(widths[i]) : c.padStart(widths[i]); }).join('');
        var summarySep = '-'.repeat(summaryHeader.length);
        var summaryLines = [summaryHeader, summarySep].concat(displayRows.map(function (dr) {
          return dr.map(function (v, i) { return i === 0 ? v.padEnd(widths[i]) : v.padStart(widths[i]); }).join('');
        }));
        var summaryTable = summaryLines.join('\n');

        var matchedRows = [];
        members.forEach(function (member) {
          var d = assignments.get(label, member);
          if (d) matchedRows.push([d.display_name || member, d]);
        });
        matchedRows.sort(function (a, b) { return b[1].completed_total - a[1].completed_total; });
        var active = matchedRows.filter(function (p) { return p[1].completed_total || p[1].error_total || p[1].case_add_total; });
        var totDone = matchedRows.reduce(function (s, p) { return s + p[1].completed_total; }, 0);
        var totErr = matchedRows.reduce(function (s, p) { return s + p[1].error_total; }, 0);
        var taskTable = active.length ? buildAgentColTable(active, totDone, totErr, function (d) { return d.task_totals; }) : null;
        var checkTable = active.length ? buildAgentColTable(active, totDone, totErr, agentCheckTotals) : null;

        var header = '📊 *' + label + ' Team Weekly Task Report (' + DATE_LABEL + ')*';
        var msg1 = header + '\n\n*Summary — Completed / Errors / Avg-Day / Calls / Target / %Achieved / Leaves / WFH*\n```\n' + summaryTable + '\n```';
        var messages = [msg1];
        if (taskTable) {
          var msg2 = '*By Task Type*\n```\n' + taskTable + '\n```';
          if (unmatched.length) msg2 += '\n_No data found for: ' + unmatched.join(', ') + '_';
          messages.push(msg2);
        }
        var tag = CATEGORY_TAGS[label];
        var tagLine = tag ? ('cc: <!subteam^' + tag.usergroup + '> <@' + tag.lead + '>') : '';
        if (checkTable) {
          var msg3 = '*By Check Type*\n```\n' + checkTable + '\n```';
          if (tagLine) msg3 += '\n' + tagLine;
          messages.push(msg3);
        }

        var targetChannel = testChannelId || channel.channel_id;
        Logger.log('  Posting ' + label + ' -> ' + targetChannel + ' (' + messages.length + ' messages)');
        messages.forEach(function (m) {
          if (testChannelId) m = '_[TEST RUN — would normally post to ' + channel.channel_id + ']_\n' + m;
          postSlackMessage(slackToken, targetChannel, m);
        });

        // Collect below-70%-of-target rows for the HR PIP post.
        members.forEach(function (member) {
          var d = assignments.get(label, member);
          var completed = d ? d.completed_total : 0;
          var caseAdd = d ? d.case_add_total : 0;
          var errors = d ? d.error_total : 0;
          var displayName = (d ? d.display_name : null) || member;
          var leaves = leaveTotals[cleanName(member)] || bestMatch(member, leaveTotals) || 0;
          var wfh = wfhTotals[cleanName(member)] || bestMatch(member, wfhTotals) || 0;
          var tgt = getTarget(member, leaves, START, END);
          var achievedMetric = CASE_ADD_TARGET_TEAMS[label] ? caseAdd : completed;
          var pctAchieved = tgt.target ? Math.round((achievedMetric / tgt.target) * 1000) / 10 : null;
          var avgDay = tgt.effectiveDays ? Math.round((achievedMetric / tgt.effectiveDays) * 10) / 10 : 0;
          if (tgt.target && pctAchieved !== null && pctAchieved < 70) {
            var tc = getTypeCohort(member);
            below70.push({
              name: displayName, team: label, completed: completed, errors: errors,
              avg_day: avgDay, leaves: leaves, wfh: wfh,
              target: tgt.target, daily_target: tgt.dailyTarget, pct_achieved: pctAchieved,
              type: tc.typ, cohort: tc.cohort, is_new_joiner: !!NEW_JOINERS[member]
            });
          }
        });
      });
    });

    // ── HR PIP post: new thread, FTE then Cohort 1-6 ──
    var groups = [];
    var fteRows = below70.filter(function (r) { return r.type === 'FTE'; }).sort(function (a, b) { return a.pct_achieved - b.pct_achieved; });
    if (fteRows.length) groups.push(['FTE', fteRows]);
    var internRows = below70.filter(function (r) { return r.type === 'Intern'; });
    for (var c = 1; c <= 6; c++) {
      var cRows = internRows.filter(function (r) { return r.cohort === c; }).sort(function (a, b) { return a.pct_achieved - b.pct_achieved; });
      if (cRows.length) groups.push(['Cohort ' + c, cRows]);
    }
    var unknownRows = below70.filter(function (r) { return (r.type !== 'FTE' && r.type !== 'Intern') || (r.type === 'Intern' && (r.cohort === null || r.cohort === undefined)); })
      .sort(function (a, b) { return a.pct_achieved - b.pct_achieved; });
    if (unknownRows.length) groups.push(['Unclassified', unknownRows]);

    if (groups.length) {
      var hrChannel = testChannelId || HR_CHANNEL_ID;
      var intro = '🚨 *PIP Review — Below 70% of Target (' + DATE_LABEL + ')*';
      var threadTs = postSlackMessage(slackToken, hrChannel, intro);
      groups.forEach(function (pair) {
        var groupLabel = pair[0], grows = pair[1];
        var cols = ['Agent', 'Team', 'Completed', 'Errors', 'Avg/Day', 'Target', '%Ach', 'Leaves', 'WFH'];
        var displayRows = grows.map(function (r) {
          var marker = r.is_new_joiner ? ' (new joiner)' : '';
          return [r.name + marker, r.team, String(r.completed), String(r.errors), fmt(r.avg_day),
            fmt(r.target), r.pct_achieved + '%', fmt(r.leaves), fmt(r.wfh)];
        });
        var widths = cols.map(function (c, i) {
          return Math.max(c.length, Math.max.apply(null, displayRows.map(function (dr) { return dr[i].length; }))) + 2;
        });
        var headerLine = cols.map(function (c, i) { return i === 0 ? c.padEnd(widths[i]) : c.padStart(widths[i]); }).join('');
        var sepLine = '-'.repeat(headerLine.length);
        var bodyLines = [headerLine, sepLine].concat(displayRows.map(function (dr) {
          return dr.map(function (v, i) { return i === 0 ? v.padEnd(widths[i]) : v.padStart(widths[i]); }).join('');
        }));
        var body = '*' + groupLabel + '*\n```\n' + bodyLines.join('\n') + '\n```';
        postSlackMessage(slackToken, hrChannel, body, threadTs);
      });
      postSlackMessage(slackToken, hrChannel, HR_PIP_TAGS + ' — please review the above and confirm on PIP.', threadTs);
      Logger.log('  Posted HR PIP thread with ' + below70.length + ' below-70% rows across ' + groups.length + ' groups');
    } else {
      Logger.log('  No below-70%-of-target rows this week — skipping HR PIP post');
    }
  }

  return { run: run };
})();

/** Manual entry point — run from the Apps Script editor, or via a trigger. */
function runWeeklyReport() {
  Weekly.run();
}

/** Test run — redirects every channel post (including the HR PIP thread) to #testing-sefali. */
function runWeeklyReportTest() {
  Weekly.run(null, null, 'testing-sefali');
}

/**
 * One-time setup: run setupTriggers() once from the Apps Script editor to install
 * the daily (6:30 AM IST) and weekly (Monday 9:00 AM IST) time-driven triggers —
 * matching the cron schedules the GitHub Actions workflows used to run.
 */
function setupTriggers() {
  removeTriggers();

  ScriptApp.newTrigger('runDailyReport')
    .timeBased()
    .atHour(6)
    .nearMinute(30)
    .everyDays(1)
    .inTimezone('Asia/Kolkata')
    .create();

  ScriptApp.newTrigger('runWeeklyReport')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(9)
    .nearMinute(0)
    .inTimezone('Asia/Kolkata')
    .create();

  Logger.log('Triggers installed: runDailyReport (daily ~6:30 AM IST), runWeeklyReport (Monday ~9:00 AM IST).');
}

function removeTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var fn = t.getHandlerFunction();
    if (fn === 'runDailyReport' || fn === 'runWeeklyReport') {
      ScriptApp.deleteTrigger(t);
    }
  });
}

/** Lists currently installed triggers in the Apps Script log — handy sanity check. */
function listTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    Logger.log(t.getHandlerFunction() + ' — ' + t.getEventType() + ' — id ' + t.getUniqueId());
  });
}

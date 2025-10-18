import logging
import time
from datetime import datetime, timedelta
from utils import create_requests_session, process_date, record_failed_date

logger = logging.getLogger("daily_downloader")

def seconds_until_next_time(hhmm: str) -> int:
    now = datetime.now()
    target = datetime.strptime(hhmm, "%H:%M").time()
    today_target = datetime.combine(now.date(), target)
    if today_target > now:
        delta = today_target - now
    else:
        tomorrow = now.date() + timedelta(days=1)
        delta = datetime.combine(tomorrow, target) - now
    return int(delta.total_seconds())

def run_daily(exec_time: str, force: bool = False):
    try:
        datetime.strptime(exec_time, "%H:%M")
    except ValueError:
        logger.error(f"Invalid time format: {exec_time}. Use HH:MM.")
        raise SystemExit(1)

    logger.info(f"[DAILY MODE] Scheduler starting. Will run daily at {exec_time}. (Ctrl+C to stop)")
    session = create_requests_session()

    try:
        while True:
            secs = seconds_until_next_time(exec_time)
            hrs = secs // 3600
            mins = (secs % 3600) // 60
            logger.info(f"[DAILY MODE] Sleeping for {hrs}h {mins}m until next run at {exec_time}")
            time.sleep(secs)

            today = datetime.now().strftime("%Y%m%d")
            logger.info(f"[DAILY MODE] Triggering job for {today}")
            ok = process_date(session, today, force=force)
            if not ok:
                record_failed_date(today)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.exception(f"Scheduler encountered an unexpected error: {e}")
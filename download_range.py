import logging
import sys
from utils import to_yyyymmdd, daterange_inclusive, process_date, record_failed_date, create_requests_session

logger = logging.getLogger("range_downloader")

def run_range(start: str, end: str, force: bool = False):
    try:
        start_y = to_yyyymmdd(start)
        end_y = to_yyyymmdd(end)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    if start_y > end_y:
        logger.error("Start date cannot be after end date.")
        sys.exit(1)

    session = create_requests_session()
    logger.info(f"Starting range run: {start_y} -> {end_y}")

    any_failures = False
    for d in daterange_inclusive(start_y, end_y):
        ok = process_date(session, d, force=force)
        if not ok:
            any_failures = True
            record_failed_date(d)

    logger.info("Range run complete.")
    if any_failures:
        logger.warning(f"Some dates failed. See logs/failed_dates.txt and logs/app.log for details.")
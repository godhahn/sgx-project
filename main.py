import argparse
import logging
import sys

from utils import setup_logging, DEFAULT_DAILY_TIME
from download_range import run_range
from download_daily import run_daily

def build_parser():
    p = argparse.ArgumentParser(description="SGX derivatives downloader")
    p.add_argument("--mode", choices=["daily", "range"], required=True, help="Mode: daily or range")
    p.add_argument("--time", default=None, help="(daily) Execution time HH:MM (default 21:00)")
    p.add_argument("--start", help="(range) Start date YYYY-MM-DD or YYYYMMDD")
    p.add_argument("--end", help="(range) End date YYYY-MM-DD or YYYYMMDD")
    p.add_argument("--force", action="store_true", help="Overwrite existing files (force redownload)")
    return p

def main():
    setup_logging()
    logger = logging.getLogger("main")

    args = build_parser().parse_args()

    if args.mode == "range":
        if not args.start or not args.end:
            logger.error("Range mode requires --start and --end")
            sys.exit(1)
        run_range(args.start, args.end, force=args.force)

    elif args.mode == "daily":
        exec_time = args.time if args.time else DEFAULT_DAILY_TIME
        run_daily(exec_time, force=args.force)

if __name__ == "__main__":
    main()
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Iterator, List, Optional, Tuple
import requests
import re
import numpy as np

BASE_URL_TEMPLATE = "https://links.sgx.com/1.0.0/derivatives-historical/{id}/{filename}"
DOWNLOAD_ROOT = "./data"
LOG_DIR = "logs"
APP_LOG = os.path.join(LOG_DIR, "app.log")
FAILED_DATES_FILE = os.path.join(LOG_DIR, "failed_dates.txt")

REQUEST_TIMEOUT = 30
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 5

DEFAULT_DAILY_TIME = "21:00"

REFERENCE_DATE_STR = "20210104"
REFERENCE_ID = 4804

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        logger.handlers.clear()

    # Console: INFO and above
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))

    # File: DEBUG and above
    fh = logging.FileHandler(APP_LOG, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))

    logger.addHandler(ch)
    logger.addHandler(fh)


def get_files_for_date(yyyymmdd: str) -> List[Tuple[str, str]]:
    return [
        ("WEBPXTICK_DT.zip", f"WEBPXTICK_DT-{yyyymmdd}.zip"),
        ("TickData_structure.dat", "TickData_structure.dat"),
        ("TC.txt", f"TC_{yyyymmdd}.txt"),
        ("TC_structure.dat", "TC_structure.dat"),
    ]


def to_yyyymmdd(s: str) -> str:
    if not s:
        raise ValueError("Empty date string")
    s = s.strip()
    if len(s) == 8 and s.isdigit():
        datetime.strptime(s, "%Y%m%d")
        return s
    dt = datetime.strptime(s, "%Y-%m-%d")
    return dt.strftime("%Y%m%d")


def daterange_inclusive(start_y: str, end_y: str) -> Iterator[str]:
    start = datetime.strptime(start_y, "%Y%m%d").date()
    end = datetime.strptime(end_y, "%Y%m%d").date()
    cur = start
    while cur <= end:
        yield cur.strftime("%Y%m%d")
        cur += timedelta(days=1)


def make_date_dir(yyyymmdd: str) -> str:
    path = os.path.join(DOWNLOAD_ROOT, yyyymmdd)
    os.makedirs(path, exist_ok=True)
    return path


def get_business_days_diff(date_str1: str, date_str2: str) -> int:
    start_date = np.datetime64(datetime.strptime(date_str1, "%Y%m%d"), "[D]")
    end_date = np.datetime64(datetime.strptime(date_str2, "%Y%m%d"), "[D]")
    return np.busday_count(start_date, end_date)


def get_date_by_id(session: requests.Session, sgx_id: int) -> Optional[str]:
    logger = logging.getLogger("core")
    url = BASE_URL_TEMPLATE.format(id=sgx_id, filename="TC.txt")
    try:
        with session.head(url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status_code != 200:
                logger.debug(f"ID {sgx_id} is invalid (HTTP {resp.status_code})")
                return None
            
            content_disposition = resp.headers.get('Content-Disposition')
            if not content_disposition:
                logger.debug(f"ID {sgx_id} has no Content-Disposition header.")
                return None
            
            date_match = re.search(r"(\d{8})", content_disposition)
            if date_match:
                actual_date = date_match.group(1)
                logger.debug(f"ID {sgx_id} corresponds to date {actual_date}")
                return actual_date
            return None
    except requests.RequestException as e:
        logger.error(f"Network error while verifying ID {sgx_id}: {e}")
        return None

def find_sgx_id_for_date(session: requests.Session, target_date: str) -> Optional[int]:
    logger = logging.getLogger("core")
    
    bus_days_diff = get_business_days_diff(REFERENCE_DATE_STR, target_date)
    estimated_id = REFERENCE_ID + bus_days_diff
    
    current_id = estimated_id
    max_attempts = 10
    for i in range(max_attempts):
        actual_date = get_date_by_id(session, current_id)
        
        if actual_date is None:
            logger.warning(f"[{target_date}] Estimated ID {current_id} is likely a holiday. Adjusting.")
            current_id -= 1
            continue

        if actual_date == target_date:
            logger.info(f"[{target_date}] Successfully confirmed ID: {current_id}")
            return current_id
        
        correction_diff = get_business_days_diff(actual_date, target_date)
        if correction_diff == 0:
            logger.warning(f"[{target_date}] Business day difference is zero but dates don't match. Assuming ID {current_id} is correct due to holiday mismatch.")
            return current_id

        logger.info(f"[{target_date}] ID {current_id} is for {actual_date}. Adjusting by {correction_diff} business days.")
        current_id += correction_diff
        
    logger.error(f"[{target_date}] Failed to find correct ID after {max_attempts} attempts.")
    return None


def download_url_for(sgx_id: int, url_filename: str) -> str:
    return BASE_URL_TEMPLATE.format(id=sgx_id, filename=url_filename)


def download_single_file(session: requests.Session, date: str, sgx_id: int, url_filename: str, save_filename: str, force: bool = False) -> bool:
    logger = logging.getLogger("core")
    date_dir = make_date_dir(date)
    local_path = os.path.join(date_dir, save_filename)

    if os.path.exists(local_path) and not force:
        logger.info(f"[{date}] Exists - skipping: {save_filename}")
        return True

    url = download_url_for(sgx_id, url_filename)
    logger.info(f"[{date}] Downloading {url_filename} to save as {save_filename}")

    attempt = 0
    while attempt < RETRY_ATTEMPTS:
        attempt += 1
        try:
            with session.get(url, stream=True, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status_code != 200:
                    logger.warning(f"[{date}] HTTP {resp.status_code} for {url_filename} (attempt {attempt})")
                    if attempt >= RETRY_ATTEMPTS: raise requests.HTTPError(f"HTTP {resp.status_code}")
                    time.sleep(RETRY_BASE_DELAY_SECONDS * attempt)
                    continue

                with open(local_path, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=8192):
                        fh.write(chunk)

                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    logger.info(f"[{date}] Downloaded: {save_filename}")
                    return True
                else:
                    logger.warning(f"[{date}] Empty file received for {url_filename}. Retrying...")
                    if os.path.exists(local_path): os.remove(local_path)
                    time.sleep(RETRY_BASE_DELAY_SECONDS * attempt)
                    
        except requests.RequestException as e:
            logger.error(f"[{date}] Error downloading {url_filename} (attempt {attempt}): {e}")
            if attempt < RETRY_ATTEMPTS:
                delay = RETRY_BASE_DELAY_SECONDS * attempt
                logger.info(f"[{date}] Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"[{date}] Final failure for {url_filename} after {RETRY_ATTEMPTS} attempts")
                if os.path.exists(local_path):
                    try: os.remove(local_path)
                    except Exception: pass
                return False
                
    logger.error(f"[{date}] Final failure for {url_filename}, received empty file after {RETRY_ATTEMPTS} attempts.")
    return False


def process_date(session: requests.Session, yyyymmdd: str, force: bool = False) -> bool:
    logger = logging.getLogger("core")

    try:
        target_dt = datetime.strptime(yyyymmdd, "%Y%m%d")
        if target_dt.year < 2021:
            logger.error(f"[{yyyymmdd}] Date is before 2021. This script only supports dates from 2021 onwards due to SGX data inconsistencies. Skipping.")
            return False
    except ValueError:
        logger.error(f"[{yyyymmdd}] Invalid date format provided.")
        return False
    
    logger.info(f"[{yyyymmdd}] Processing date...")

    sgx_id = find_sgx_id_for_date(session, yyyymmdd)
    if sgx_id is None:
        logger.error(f"[{yyyymmdd}] CRITICAL: Could not determine SGX ID. This could be a non-business day or a data gap. Skipping.")
        return False
    
    all_ok = True
    for url_filename, save_filename in get_files_for_date(yyyymmdd):
        ok = download_single_file(session, yyyymmdd, sgx_id, url_filename, save_filename, force=force)
        if not ok:
            all_ok = False

    if all_ok:
        logger.info(f"[{yyyymmdd}] All files successfully processed/verified.")
    else:
        logger.error(f"[{yyyymmdd}] One or more files failed to download for this date.")
    return all_ok


def record_failed_date(yyyymmdd: str):
    logger = logging.getLogger("core")
    os.makedirs(LOG_DIR, exist_ok=True)
    path = FAILED_DATES_FILE

    try:
        date_obj = datetime.strptime(yyyymmdd, '%Y%m%d')
        date_to_record = date_obj.strftime('%Y-%m-%d')
    except ValueError:
        logger.error(f"Could not format date for failure log: {yyyymmdd}. Recording as is.")
        date_to_record = yyyymmdd

    existing = set()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = {line.strip() for line in f if line.strip()}
        except Exception:
            logger.debug("Could not read failed_dates file; will recreate.")
            
    if date_to_record not in existing:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{date_to_record}\n")
        logger.info(f"[{yyyymmdd}] Recorded in failed_dates.txt (as {date_to_record})")


def create_requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session
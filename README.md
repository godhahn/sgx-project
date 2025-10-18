# SGX Derivatives Data Downloader
Simple Python CLI tool to download SGX derivatives tick and trade cancellation data.

- `WEBPXTICK_DT-YYYYMMDD.zip`
- `TickData_structure.dat`
- `TC_YYYYMMDD.txt`
- `TC_structure.dat`

## Command-Line Interface
### Download Range
```bash
python main.py --mode range --start 2024-01-01 --end 2024-01-31
```
### Download Daily (default 21:00 UTC)
```bash
python main.py --mode daily --time 21:00
```
### Force Re-download
```bash
python main.py --mode range --start 2024-01-01 --end 2024-01-31 --force
```

## Important
- This tool is designed to work for dates from January 1, 2021, onwards only.
- This tool uses UTC timing for standardization.
   - For **download range**, it will download the data inclusive of the provided start and end dates.
   - For **download daily**, the default schedule of `2100 UTC` downloads the current day's data. This corresponds to `0500 SGT` the following morning, ensuring data for the previous trading day is always available.

## Logging & Recovery
- `INFO`, `WARNING`, `ERROR` written to console.
- `DEBUG` and above written to `logs/app.log`.
- Automatic retry: each file retried up to 3 times with increasing delays (5s × attempt).
- Manual retry: dates with any final failures appended to `logs/failed_dates.txt`.

## Folder Structure
```bash
project/
├─ README.md
├─ main.py
├─ utils.py
├─ download_range.py  # Logic for the 'range' mode
├─ download_daily.py  # Logic for the 'daily' mode
├─ data/YYYYMMDD/     # Storage
├─ logs/
│  ├─ app.log
│  └─ failed_dates.txt
└─ assets/
   ├─ 01_endpoint_source.png
   └─ 02_endpoint_source.png
```

## Deployment & Optimization
- Run on a cloud server for persistent daily downloads.
- Store downloaded files in a cloud database or object storage.
- Use Airflow for orchestration and scheduling if needed.

## Test Scenarios
| Scenario                                 | Command                                                                                | Expected Outcome                                                                             |
| ---------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Range Mode — Valid Range                 | `python main.py --mode range --start 2024-01-02 --end 2024-01-05`                          | Creates folders `data/20240102` … `data/20240105` with 4 files each. Log records successful downloads.                |
| Range Mode — Pre-2021 Date               | `python main.py --mode range --start 2020-12-30 --end 2020-12-31`                      | Logs error: *“Date is before 2021... Skipping.”* for each date. No data folders are created.                     |
| Range Mode — Weekend                     | `python main.py --mode range --start 2025-10-12 --end 2025-10-13`                      | (Sat/Sun) Logs error: *“Could not determine SGX ID... Skipping.”* for each date. Records dates in `failed_dates.txt`. |
| Range Mode — Invalid Range (Start > End) | `python main.py --mode range --start 2024-01-31 --end 2024-01-01`                          | Prints error: *“Start date cannot be after end date.”* No files downloaded.                                           |
| Range Mode — Existing Files (Skip Logic) | `python main.py --mode range --start 2024-01-02 --end 2024-01-03`                          | Logs: *“Skipping existing file...”* No duplicate downloads unless `--force` is added.                                 |
| Daily Mode — Manual Trigger (Scheduler)  | `python main.py --mode daily --time 13:07`                                             | Logs scheduler start, sleeps until time, runs once, downloads today’s folder.                                          |
| Daily Mode — Invalid Time Format         | `python main.py --mode daily --time 25:99`                                             | Prints error: *“Invalid time format. Use HH:MM.”* Exits.                                                         |
| Forced Re-download                       | `python main.py --mode range --start 2024-01-02 --end 2024-01-02 --force`                  | All existing files re-downloaded regardless of presence.                                                             |
| Network Failure / Retry Logic            | Disable internet **or** temporarily edit URL to invalid                                | Logs multiple retry attempts, marks date in `failed_dates.txt`.                                                   |
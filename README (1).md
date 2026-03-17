# Small Business Automation Kit
### Python scripts that handle the repetitive stuff so you don't have to

Built by [Mikael Pelz, PhD](https://www.linkedin.com/in/mikaelpelz) — these scripts came out of years of watching small teams spend hours on tasks that a well-written 50 lines of Python could handle in seconds.

Every script in this kit is:
- **Configurable at the top** — change behavior without touching the code
- **Logged** — every action is recorded so you always know what happened
- **Safe** — nothing is deleted without warning, dry-run modes where it matters
- **Resilient** — clear error messages when something unexpected happens

---

## What's in the kit

| # | Script | What it does |
|---|--------|-------------|
| 01 | `01_folder_auto_sorter.py` | Watches a folder and sorts files into subfolders by type — **FREE** |
| 02 | `02_bulk_file_renamer.py` | Renames files in bulk with a dry-run preview before touching anything |
| 03 | `03_deadline_reminder_emailer.py` | Reads a CSV of deadlines and emails reminders at the right time |
| 04 | `04_invoice_generator.py` | Fills a Word invoice template from a spreadsheet row |
| 05 | `05_inbox_action_item_extractor.py` | Scans Gmail and pulls out tasks and follow-ups using AI |
| 06 | `06_webpage_change_monitor.py` | Alerts you when a webpage's content changes |
| 07 | `07_weekly_digest_builder.py` | Compiles your weekly log into a formatted summary email |

> **Note:** Script 01 is free and fully functional. Scripts 02–07 are included in the [paid kit on Gumroad](#).

---

## Setup

### Requirements
- Python 3.8 or higher — download from [python.org](https://python.org)
- The packages listed in `requirements.txt`

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run a script
```bash
python scripts/01_folder_auto_sorter.py
```

Each script has a **CONFIGURATION** section at the top. Edit that section only — no need to touch the code below it.

---

## Running on a schedule

### Mac / Linux (cron)
Open Terminal and run `crontab -e`, then add a line like:
```
# Run folder sorter every day at 8am
0 8 * * * /usr/bin/python3 /path/to/scripts/01_folder_auto_sorter.py
```

### Windows (Task Scheduler)
1. Open Task Scheduler → Create Basic Task
2. Set your trigger (daily, on login, etc.)
3. Action: Start a program → `python.exe`
4. Add arguments: `C:\path\to\scripts\01_folder_auto_sorter.py`

---

## Sample data
The `sample-data/` folder contains example input files you can use to test each script before pointing it at your real data. Always recommended for a first run.

---

## Logs
Every script writes to the `logs/` folder. If something doesn't work as expected, the log file is the first place to look — it records every action with a timestamp.

---

## Questions or issues?
Open an issue on this repo or reach out directly. If a script breaks on your specific file format, I want to know — that's exactly the kind of edge case these scripts are built to handle.

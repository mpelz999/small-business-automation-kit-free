"""
=============================================================
  FOLDER AUTO-SORTER
  Small Business Automation Kit — Script 01 (FREE TEASER)
  by Mikael Pelz, PhD
=============================================================

WHAT IT DOES:
  Sorts files in a folder into subfolders automatically.
  Supports four sorting strategies you can mix and match:
    - By file type/extension  (e.g. .pdf -> invoices/)
    - By keyword in filename  (e.g. "invoice" -> invoices/)
    - By date                 (e.g. -> 2024/October/)
    - Watch mode              (runs continuously, sorts as files arrive)

  Every move is logged. Undo restores everything from the log.
  Nothing is ever deleted.

WHY I BUILT IT THIS WAY:
  Most sorting scripts just move files and move on. If something
  lands in the wrong place there's no way to trace it, and no
  way back. This script logs every single action so you can
  undo an entire run with one command. It also never deletes
  files — ever — and never silently overwrites them.

  The keyword rules came from watching people whose files don't
  sort cleanly by extension alone. A PDF could be an invoice,
  a contract, or a resume. Keywords let you sort by what the
  file actually is, not just what type it is.

SETUP:
  1. Install Python 3.8+ from python.org
  2. Install dependencies:  pip install watchdog
  3. Edit the CONFIGURATION section below
  4. Run one of these commands:

     Sort once:       python 01_folder_auto_sorter.py
     Dry run:         python 01_folder_auto_sorter.py --dry-run
     Watch mode:      python 01_folder_auto_sorter.py --watch
     Undo last run:   python 01_folder_auto_sorter.py --undo

  To run on a schedule automatically:
  - Mac/Linux: add to crontab  (see README)
  - Windows:   use Task Scheduler  (see README)

=============================================================
"""

import os
import sys
import json
import time
import shutil
import logging
import argparse
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


# =============================================================
#  CONFIGURATION — edit everything in this section
# =============================================================

# The folder you want to auto-sort
# Examples:
#   Windows:  r"C:\Users\YourName\Downloads"
#   Mac:      "/Users/yourname/Downloads"
#   Relative: "./sample-data/incoming"
WATCH_FOLDER = "./sample-data/incoming"

# Where to save the log file and undo history
LOG_FILE  = "./logs/folder_sorter_log.txt"
UNDO_FILE = "./logs/folder_sorter_undo.json"

# ------------------------------------------------------------------
# SORTING MODE
# Choose how files get sorted. Options:
#   "extension"          — sort by file type (.pdf, .jpg, etc.)
#   "keyword"            — sort by words in the filename
#   "date"               — sort into year/month subfolders by file date
#   "extension+keyword"  — keyword rules take priority, extension
#                          rules catch everything else (recommended)
# ------------------------------------------------------------------
SORT_MODE = "extension+keyword"

# ------------------------------------------------------------------
# EXTENSION RULES
# Map file extensions to subfolder names.
# Used when SORT_MODE includes "extension".
# ------------------------------------------------------------------
EXTENSION_RULES = {
    "invoices":      [".pdf"],
    "images":        [".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tiff"],
    "spreadsheets":  [".xlsx", ".xls", ".csv", ".numbers"],
    "documents":     [".docx", ".doc", ".txt", ".rtf", ".pages", ".md"],
    "presentations": [".pptx", ".ppt", ".key"],
    "archives":      [".zip", ".tar", ".gz", ".rar", ".7z"],
    "videos":        [".mp4", ".mov", ".avi", ".mkv", ".wmv"],
    "audio":         [".mp3", ".wav", ".m4a", ".aac", ".flac"],
}

# ------------------------------------------------------------------
# KEYWORD RULES
# Map keywords (found anywhere in the filename) to subfolder names.
# Keywords are case-insensitive. First match wins.
# Used when SORT_MODE includes "keyword".
#
# Example: "invoice_acme_sept.pdf" matches "invoice" and goes to
# invoices/ — even if .pdf is mapped to a different folder above.
# ------------------------------------------------------------------
KEYWORD_RULES = {
    "invoices":  ["invoice", "receipt", "billing", "payment"],
    "contracts": ["contract", "agreement", "nda", "proposal"],
    "reports":   ["report", "summary", "analysis", "review", "audit"],
    "resumes":   ["resume", "cv", "curriculum"],
    "photos":    ["photo", "headshot", "portrait", "screenshot"],
}

# ------------------------------------------------------------------
# DATE SORTING
# When SORT_MODE is "date", files are sorted into:
#   <WATCH_FOLDER>/<year>/<month>/filename
# Example: ./incoming/2024/October/invoice.pdf
#
# DATE_SOURCE options:
#   "modified" — use the file's last-modified date (most reliable)
#   "created"  — use the file's creation date
# ------------------------------------------------------------------
DATE_SOURCE = "modified"

# ------------------------------------------------------------------
# UNMATCHED FILES
# What to do with files that don't match any rule.
# Options:
#   "unsorted" — move to an 'unsorted' subfolder
#   "skip"     — leave them where they are
# ------------------------------------------------------------------
UNMATCHED_FILES = "unsorted"

# Files to always ignore (never move these)
IGNORE_FILES = [
    ".DS_Store",
    "desktop.ini",
    "Thumbs.db",
    ".gitkeep",
]

# In watch mode: seconds to wait after a file appears before moving it.
# Gives large files time to finish copying before the script touches them.
WATCH_SETTLE_SECONDS = 2

# =============================================================
#  END OF CONFIGURATION — no need to edit below this line
# =============================================================


# ── Logging setup ──────────────────────────────────────────────

def setup_logging(log_file: str) -> logging.Logger:
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("folder_sorter")
    if logger.handlers:
        return logger  # already configured (watch mode reuses this)

    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ── Undo history ───────────────────────────────────────────────

def load_undo_history(undo_file: str) -> list:
    path = Path(undo_file)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_undo_history(undo_file: str, history: list) -> None:
    Path(undo_file).parent.mkdir(parents=True, exist_ok=True)
    with open(undo_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def undo_last_run(undo_file: str, logger: logging.Logger) -> None:
    """Restore all files moved in the most recent sort run."""
    history = load_undo_history(undo_file)

    if not history:
        logger.info("")
        logger.info("  No undo history found. Nothing to restore.")
        logger.info(f"  (Expected file: {Path(undo_file).resolve()})")
        logger.info("")
        return

    last_run = history[-1]
    moves    = last_run.get("moves", [])
    run_time = last_run.get("started", "unknown time")

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  UNDO — restoring run from {run_time}")
    logger.info(f"  {len(moves)} file(s) to restore")
    logger.info("=" * 60)
    logger.info("")

    restored = 0
    errors   = 0

    for move in reversed(moves):
        src      = Path(move["to"])
        original = Path(move["from"])

        if not src.exists():
            logger.warning(f"  MISSING   {src.name}  — not found at destination, skipping")
            errors += 1
            continue

        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            safe_dest = get_safe_destination(original)
            shutil.move(str(src), str(safe_dest))
            logger.info(f"  RESTORED  {src.name}  ->  {safe_dest.parent.name}/")
            restored += 1
        except Exception as e:
            logger.warning(f"  ERROR     {src.name}  — {e}")
            errors += 1

    # Remove the undone run so it can't be undone twice
    history.pop()
    save_undo_history(undo_file, history)

    logger.info("")
    logger.info("-" * 60)
    logger.info(f"  Restored: {restored} file(s)")
    if errors:
        logger.warning(f"  Errors:   {errors} file(s) — check log for details")
    logger.info("-" * 60)
    logger.info("")


# ── Sorting helpers ────────────────────────────────────────────

def build_extension_map(rules: dict) -> dict:
    """Invert extension rules for fast lookup: {'.pdf': 'invoices', ...}"""
    ext_map = {}
    for category, extensions in rules.items():
        for ext in extensions:
            ext_lower = ext.lower()
            if ext_lower in ext_map:
                raise ValueError(
                    f"Extension '{ext_lower}' appears in both "
                    f"'{ext_map[ext_lower]}' and '{category}'. "
                    "Each extension can only belong to one category."
                )
            ext_map[ext_lower] = category
    return ext_map


def match_keyword(filename: str, keyword_rules: dict) -> str | None:
    """Return the first matching category for a filename, or None."""
    name_lower = filename.lower()
    for category, keywords in keyword_rules.items():
        for kw in keywords:
            if kw.lower() in name_lower:
                return category
    return None


def get_date_subfolder(file_path: Path, source: str) -> str:
    """Return a 'YYYY/MonthName' path string based on the file's date."""
    try:
        ts = file_path.stat().st_ctime if source == "created" else file_path.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y/%B")  # e.g. "2024/October"
    except Exception:
        return "undated"


def get_safe_destination(destination: Path) -> Path:
    """
    If a file already exists at the destination, append a counter.
    invoice.pdf -> invoice_2.pdf -> invoice_3.pdf
    Never silently overwrites.
    """
    if not destination.exists():
        return destination
    stem, suffix, parent = destination.stem, destination.suffix, destination.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def resolve_category(
    file_path: Path,
    sort_mode: str,
    ext_map: dict,
    keyword_rules: dict,
    date_source: str,
    unmatched: str,
) -> str | None:
    """
    Return the destination subfolder name for a file.
    Returns None only when the file should be skipped entirely.
    """
    filename  = file_path.name
    extension = file_path.suffix.lower()

    if sort_mode == "date":
        return get_date_subfolder(file_path, date_source)

    if sort_mode == "keyword":
        category = match_keyword(filename, keyword_rules)
        return category if category else (None if unmatched == "skip" else "unsorted")

    if sort_mode == "extension":
        category = ext_map.get(extension)
        return category if category else (None if unmatched == "skip" else "unsorted")

    if sort_mode == "extension+keyword":
        # Keywords take priority — they encode what the file IS
        # Extensions catch everything keywords miss
        category = match_keyword(filename, keyword_rules) or ext_map.get(extension)
        return category if category else (None if unmatched == "skip" else "unsorted")

    raise ValueError(
        f"Unknown SORT_MODE: '{sort_mode}'. "
        "Choose: extension | keyword | date | extension+keyword"
    )


# ── Core sort run ──────────────────────────────────────────────

def sort_folder(
    watch_folder: str,
    sort_mode: str,
    extension_rules: dict,
    keyword_rules: dict,
    date_source: str,
    unmatched: str,
    ignore_files: list,
    dry_run: bool,
    undo_file: str,
    logger: logging.Logger,
    single_file: Path = None,
) -> dict:
    """
    Sort files in watch_folder.
    When single_file is provided only that file is processed
    (used internally by watch mode).
    """
    watch_path = Path(watch_folder)

    if not watch_path.exists():
        logger.error(f"Watch folder not found: {watch_path.resolve()}")
        logger.error("Please check the WATCH_FOLDER setting in the configuration.")
        return {"error": True}

    ext_map   = build_extension_map(extension_rules)
    summary   = {"moved": 0, "skipped": 0, "renamed": 0, "errors": 0}
    run_moves = []
    mode_label = "[DRY RUN] " if dry_run else ""

    files = [single_file] if single_file else sorted(
        f for f in watch_path.iterdir() if f.is_file()
    )

    if not single_file:
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"  {mode_label}FOLDER AUTO-SORTER  [{sort_mode} mode]")
        logger.info(f"  Started:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"  Watching: {watch_path.resolve()}")
        logger.info("=" * 60)

        if dry_run:
            logger.info("")
            logger.info("  DRY RUN — no files will be moved.")
            logger.info("  Set DRY_RUN = False to run for real.")

        if not files:
            logger.info("  No files found. Nothing to sort.")
            logger.info("")
            return summary

        logger.info(f"  Found {len(files)} file(s) to process.")
        logger.info("")

    for file_path in files:
        filename = file_path.name

        # Skip system files and hidden files
        if filename in ignore_files or filename.startswith("."):
            logger.debug(f"IGNORED | {filename}")
            summary["skipped"] += 1
            continue

        category = resolve_category(
            file_path, sort_mode, ext_map,
            keyword_rules, date_source, unmatched
        )

        if category is None:
            logger.info(f"  SKIPPED   {filename}  (no matching rule)")
            summary["skipped"] += 1
            continue

        dest_folder = watch_path / category
        dest_path   = get_safe_destination(dest_folder / filename)
        renamed     = dest_path.name != filename

        try:
            if not dry_run:
                dest_folder.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(dest_path))
                run_moves.append({"from": str(file_path), "to": str(dest_path)})

            label = f"  MOVED     {filename}  ->  {category}/"
            if renamed:
                label += f"  (saved as {dest_path.name} to avoid overwrite)"
                summary["renamed"] += 1
            logger.info(label)
            summary["moved"] += 1

        except PermissionError:
            logger.warning(
                f"  ERROR     {filename}  — permission denied. "
                "Is the file open in another program?"
            )
            summary["errors"] += 1
        except Exception as e:
            logger.warning(f"  ERROR     {filename}  — {e}")
            summary["errors"] += 1

    # Save undo history after a real (non-dry-run, non-watch-single-file) run
    if not dry_run and run_moves and not single_file:
        history = load_undo_history(undo_file)
        history.append({
            "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode":    sort_mode,
            "moves":   run_moves,
        })
        save_undo_history(undo_file, history)

    if not single_file:
        logger.info("")
        logger.info("-" * 60)
        logger.info(f"  {mode_label}DONE")
        logger.info(f"  Moved:   {summary['moved']} file(s)")
        if summary["renamed"]:
            logger.info(f"  Renamed: {summary['renamed']} file(s) to avoid overwriting")
        if summary["skipped"]:
            logger.info(f"  Skipped: {summary['skipped']} file(s)")
        if summary["errors"]:
            logger.warning(f"  Errors:  {summary['errors']} — check log for details")
        if not dry_run:
            logger.info("  Undo:    python 01_folder_auto_sorter.py --undo")
        logger.info(f"  Log:     {Path(LOG_FILE).resolve()}")
        logger.info("-" * 60)
        logger.info("")

    return summary


# ── Watch mode ─────────────────────────────────────────────────

class SortHandler(FileSystemEventHandler):
    """Processes new files arriving in the watched folder."""

    def __init__(self, config: dict, logger: logging.Logger):
        self.config  = config
        self.logger  = logger
        self.pending = {}  # path_str -> timestamp first seen

    def on_created(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        # Only react to files directly in the watch folder, not subfolders
        if file_path.parent.resolve() == Path(self.config["watch_folder"]).resolve():
            self.pending[str(file_path)] = time.time()

    def process_pending(self):
        """Move files that have been stable for WATCH_SETTLE_SECONDS."""
        now     = time.time()
        to_move = [
            p for p, t in list(self.pending.items())
            if now - t >= self.config["settle_seconds"]
        ]
        for path_str in to_move:
            del self.pending[path_str]
            file_path = Path(path_str)
            if file_path.exists():
                self.logger.info(f"  NEW FILE  {file_path.name}")
                sort_folder(
                    single_file=file_path,
                    logger=self.logger,
                    **{k: v for k, v in self.config.items() if k != "settle_seconds"},
                )


def run_watch_mode(config: dict, logger: logging.Logger) -> None:
    if not WATCHDOG_AVAILABLE:
        logger.error("")
        logger.error("  Watch mode requires the 'watchdog' package.")
        logger.error("  Install it with:  pip install watchdog")
        logger.error("")
        raise SystemExit(1)

    watch_path = Path(config["watch_folder"])
    if not watch_path.exists():
        logger.error(f"  Watch folder not found: {watch_path.resolve()}")
        raise SystemExit(1)

    handler  = SortHandler(config, logger)
    observer = Observer()
    observer.schedule(handler, str(watch_path), recursive=False)
    observer.start()

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  WATCH MODE  [{config['sort_mode']} mode]")
    logger.info(f"  Watching:   {watch_path.resolve()}")
    logger.info(f"  Press Ctrl+C to stop.")
    logger.info("=" * 60)
    logger.info("")

    try:
        while True:
            time.sleep(0.5)
            handler.process_pending()
    except KeyboardInterrupt:
        observer.stop()
        logger.info("")
        logger.info("  Watch mode stopped.")
        logger.info("")
    observer.join()


# ── CLI ────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Folder Auto-Sorter — Small Business Automation Kit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python 01_folder_auto_sorter.py               sort once
  python 01_folder_auto_sorter.py --dry-run     preview without moving anything
  python 01_folder_auto_sorter.py --watch       watch folder continuously
  python 01_folder_auto_sorter.py --undo        restore files from last run
        """
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would happen without moving files")
    parser.add_argument("--watch",   action="store_true",
                        help="Watch folder continuously and sort as files arrive")
    parser.add_argument("--undo",    action="store_true",
                        help="Restore all files moved in the most recent run")
    return parser.parse_args()


def main():
    args   = parse_args()
    logger = setup_logging(LOG_FILE)

    if args.undo:
        undo_last_run(UNDO_FILE, logger)
        return

    config = dict(
        watch_folder    = WATCH_FOLDER,
        sort_mode       = SORT_MODE,
        extension_rules = EXTENSION_RULES,
        keyword_rules   = KEYWORD_RULES,
        date_source     = DATE_SOURCE,
        unmatched       = UNMATCHED_FILES,
        ignore_files    = IGNORE_FILES,
        dry_run         = args.dry_run,
        undo_file       = UNDO_FILE,
        settle_seconds  = WATCH_SETTLE_SECONDS,
    )

    if args.watch:
        run_watch_mode(config, logger)
    else:
        sort_config = {k: v for k, v in config.items() if k != "settle_seconds"}
        result = sort_folder(logger=logger, single_file=None, **sort_config)
        if result.get("error"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()

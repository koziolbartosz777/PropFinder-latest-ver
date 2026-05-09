"""
run_scraper.py — PropAgent nightly scraper runner
==================================================
Runs each configured spider for each city, then marks gone listings.
Log is appended to scraper_log.txt in the project directory.

Usage:
    python run_scraper.py
"""

import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG — edit these to change what gets scraped
# ──────────────────────────────────────────────────────────────────────────────
CITIES    = ["krakow"]
MAX_PAGES = 10
SPIDERS   = ["otodom", "gratka", "nro"]
# ──────────────────────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).resolve().parent
LOG_FILE    = PROJECT_DIR / "scraper_log.txt"


def log(msg: str, file=None):
    """Print to stdout and optionally append to log file handle."""
    print(msg)
    if file:
        file.write(msg + "\n")


def run_spider(spider: str, city: str, log_file) -> bool:
    """
    Run a single scrapy spider for one city.
    Returns True on success, False on failure.
    """
    cmd = [
        sys.executable, "-m", "scrapy", "crawl",
        spider,
        "-a", f"miasto={city}",
        "-a", f"max_stron={MAX_PAGES}",
    ]
    label = f"[{spider}@{city}]"
    log(f"{label} Starting: {' '.join(cmd)}", log_file)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_DIR),
            capture_output=False,   # let scrapy output flow to console
            timeout=3600,           # 1 h hard cap per spider
        )
        if result.returncode == 0:
            log(f"{label} Finished OK (exit 0)", log_file)
            return True
        else:
            log(f"{label} FAILED with exit code {result.returncode}", log_file)
            return False
    except subprocess.TimeoutExpired:
        log(f"{label} TIMED OUT after 3600 s", log_file)
        return False
    except Exception as exc:
        log(f"{label} ERROR: {exc}", log_file)
        return False


def main():
    started_at = datetime.now()
    banner = f"\n{'='*60}\nPropAgent scraper run started at {started_at:%Y-%m-%d %H:%M:%S}\n{'='*60}"

    with open(LOG_FILE, "a", encoding="utf-8") as lf:
        log(banner, lf)

        total   = 0
        failed  = []

        for city in CITIES:
            for spider in SPIDERS:
                total += 1
                ok = run_spider(spider, city, lf)
                if not ok:
                    failed.append(f"{spider}@{city}")

        # ── Mark gone listings ────────────────────────────────────────────────
        log("\n[mark_sold] Updating gone listings…", lf)
        try:
            # Import from the project package (cwd already correct for imports)
            sys.path.insert(0, str(PROJECT_DIR))
            from ScraperMieszkan.mark_sold import update_sold_auctions
            update_sold_auctions()
            log("[mark_sold] Done.", lf)
        except Exception as exc:
            log(f"[mark_sold] ERROR: {exc}", lf)

        # ── Summary ───────────────────────────────────────────────────────────
        finished_at = datetime.now()
        duration    = finished_at - started_at
        summary_lines = [
            "",
            f"{'─'*60}",
            f"Run finished at {finished_at:%Y-%m-%d %H:%M:%S}  (took {duration})",
            f"Spiders run   : {total}",
            f"Successful    : {total - len(failed)}",
            f"Failed        : {len(failed)}",
        ]
        if failed:
            summary_lines.append(f"Failed spiders: {', '.join(failed)}")
        summary_lines.append(f"{'─'*60}\n")

        for line in summary_lines:
            log(line, lf)

    # Also print summary to console (already printed via log() above)
    if failed:
        print(f"\n[WARNING] {len(failed)} spider(s) failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"\n[OK] All {total} spider(s) completed successfully.")


if __name__ == "__main__":
    main()

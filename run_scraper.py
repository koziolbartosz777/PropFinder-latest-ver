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
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG — edit these to change what gets scraped
# ──────────────────────────────────────────────────────────────────────────────
CITIES    = ["krakow"]
MAX_PAGES = 999   # scrapuj wszystkie strony (spider sam zatrzyma się gdy nie ma więcej)
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

        # ── Przywróć oferty Otodom, które były gone przez blokadę (jednorazowo) ─
        log("\n[restore_otodom] Przywracanie ofert otodom oznaczonych gone przez blokadę…", lf)
        try:
            from ScraperMieszkan.utils import get_db_connection
            conn_r = get_db_connection()
            cur_r  = conn_r.cursor()
            # Jeśli otodom działał podczas tego uruchomienia (last_seen zaktualizowane),
            # lub przywracamy oferty widziane w ciągu ostatnich 7 dni przed oznaczeniem gone.
            # Bezpieczne: następny run mark_sold i tak sprawdzi last_seen.
            cur_r.execute("""
                UPDATE auctions
                SET status = 'active'
                WHERE portal = 'otodom'
                  AND status = 'gone'
                  AND last_seen >= NOW() - INTERVAL '14 days'
            """)
            restored = cur_r.rowcount
            conn_r.commit()
            cur_r.close()
            conn_r.close()
            if restored > 0:
                log(f"[restore_otodom] Przywrócono {restored} ofert otodom do active.", lf)
            else:
                log("[restore_otodom] Brak ofert do przywrócenia.", lf)
        except Exception as exc:
            log(f"[restore_otodom] ERROR: {exc}", lf)

        # ── Backfill missing cena_za_m2 in price_history ─────────────────────
        log("\n[migrate] Backfilling NULL cena_za_m2 records…", lf)
        try:
            sys.path.insert(0, str(PROJECT_DIR))
            from ScraperMieszkan.utils import get_db_connection
            conn_m = get_db_connection()
            cur_m  = conn_m.cursor()
            cur_m.execute("""
                UPDATE price_history ph
                SET    cena_za_m2 = ROUND(ph.cena_pln::numeric / a.metraz)
                FROM   auctions a
                WHERE  ph.auction_id   = a.auction_id
                  AND  ph.cena_za_m2   IS NULL
                  AND  ph.cena_pln     IS NOT NULL
                  AND  a.metraz        IS NOT NULL
                  AND  a.metraz        > 0
            """)
            updated = cur_m.rowcount
            conn_m.commit()
            cur_m.close()
            conn_m.close()
            log(f"[migrate] Updated {updated} rows.", lf)
        except Exception as exc:
            log(f"[migrate] ERROR: {exc}", lf)

        # ── Backfill dzielnica dla NRO z adres_pelny ─────────────────────────
        log("\n[migrate] Backfilling dzielnica for NRO from adres_pelny…", lf)
        try:
            from ScraperMieszkan.utils import get_db_connection
            conn_d = get_db_connection()
            cur_d  = conn_d.cursor()
            # NRO zapisuje location jako "Kraków, Grzegórzki" lub "Małopolskie, Kraków, Grzegórzki".
            # Ostatni człon po przecinku to dzielnica — pod warunkiem że to nie jest nazwa miasta.
            MIASTA_SQL = ("'Kraków','Warszawa','Wrocław','Gdańsk','Poznań',"
                          "'Łódź','Katowice','Szczecin','Bydgoszcz','Lublin',"
                          "'Białystok','Rzeszów','Toruń','Kraków','Kielce'")
            cur_d.execute(f"""
                UPDATE auctions
                SET dzielnica = extracted
                FROM (
                    SELECT auction_id,
                           TRIM(REGEXP_REPLACE(adres_pelny, '^.*,\\s*', '')) AS extracted
                    FROM   auctions
                    WHERE  portal      = 'nro'
                      AND  (dzielnica IS NULL OR dzielnica = '')
                      AND  adres_pelny IS NOT NULL
                      AND  adres_pelny LIKE '%,%'
                ) sub
                WHERE  auctions.auction_id = sub.auction_id
                  AND  sub.extracted NOT IN ({MIASTA_SQL})
                  AND  sub.extracted != ''
            """)
            nro_updated = cur_d.rowcount
            # ── Wyczyść błędne dzielnice Gratki (np. "Kraków" zamiast prawdziwej dzielnicy)
            cur_d.execute(f"""
                UPDATE auctions
                SET dzielnica = NULL
                WHERE portal = 'gratka'
                  AND dzielnica IN ({MIASTA_SQL})
            """)
            gratka_cleared = cur_d.rowcount
            conn_d.commit()
            cur_d.close()
            conn_d.close()
            log(f"[migrate] NRO dzielnica backfilled: {nro_updated} rows. "
                f"Gratka city-as-dzielnica cleared: {gratka_cleared} rows.", lf)
        except Exception as exc:
            log(f"[migrate] dzielnica ERROR: {exc}", lf)

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

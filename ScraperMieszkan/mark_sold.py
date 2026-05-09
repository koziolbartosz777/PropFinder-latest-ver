from dotenv import load_dotenv
from ScraperMieszkan.utils import get_db_connection
import logging

logger = logging.getLogger(__name__)


def update_sold_auctions():
    load_dotenv()

    conn = get_db_connection()
    cursor = conn.cursor()

    # ── Ustal które portale faktycznie były scrapowane w ciągu ostatnich 26h ──
    # Jeśli portal nie zwrócił żadnych ofert (last_seen >= NOW()-26h jest puste),
    # to prawdopodobnie był zablokowany — nie oznaczamy jego ogłoszeń jako gone.
    cursor.execute("""
        SELECT DISTINCT portal
        FROM auctions
        WHERE last_seen >= NOW() - INTERVAL '26 hours'
    """)
    scraped_portals = [row[0] for row in cursor.fetchall()]

    if not scraped_portals:
        logger.warning(
            "[mark_sold] Żaden portal nie był scrapowany w ostatnich 26h — "
            "pomijam oznaczanie gone (spider mógł być zablokowany)."
        )
        cursor.close()
        conn.close()
        return

    # ── Oznacz gone tylko dla portali, które BYŁY scrapowane ─────────────────
    # Listing uznajemy za gone jeśli od 48h nie był widziany
    # ORAZ jego portal faktycznie działał podczas ostatniego scraping run.
    placeholders = ",".join(["%s"] * len(scraped_portals))
    cursor.execute(
        f"""
        UPDATE auctions
        SET status = 'gone'
        WHERE status = 'active'
          AND portal IN ({placeholders})
          AND last_seen < NOW() - INTERVAL '48 hours'
        """,
        scraped_portals,
    )
    updated = cursor.rowcount
    conn.commit()

    # ── Log portale które były pominięte (prawdopodobnie zablokowane) ─────────
    cursor.execute("SELECT DISTINCT portal FROM auctions WHERE status = 'active'")
    all_portals = {row[0] for row in cursor.fetchall()}
    skipped = all_portals - set(scraped_portals)
    if skipped:
        logger.warning(
            "[mark_sold] Pominięto oznaczanie gone dla portali (brak danych z ostatnich 26h): %s. "
            "Sprawdź logi spiderów — prawdopodobna blokada.",
            ", ".join(sorted(skipped))
        )

    logger.info(
        "[mark_sold] Oznaczono %d ogłoszeń jako gone (portale: %s).",
        updated, ", ".join(sorted(scraped_portals))
    )

    cursor.close()
    conn.close()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    update_sold_auctions()

from dotenv import load_dotenv
from ScraperMieszkan.utils import get_db_connection


def update_sold_auctions():
    load_dotenv()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE auctions
        SET status = 'gone'
        WHERE status = 'active'
          AND last_seen < NOW() - INTERVAL '48 hours';
        """
    )
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    update_sold_auctions()

import os
import time
import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        database=os.environ.get("DB_NAME", "scraper_mieszkan"),
        user=os.environ.get("DB_USER", "admin"),
        password=os.environ.get("DB_PASSWORD", ""),
    )


# def load_parsed_ids(logger=None, max_retries=10, delay=5):
#     query = """
#         SELECT auction_id
#         FROM auctions
#         WHERE liczba_zdjec IS NOT NULL OR opis_dlugosc IS NOT NULL
#     """

#     for attempt in range(1, max_retries + 1):
#         try:
#             conn = get_db_connection()
#             cur = conn.cursor()
#             cur.execute(query)
#             ids = {row[0] for row in cur.fetchall()}
#             conn.close()
#             return ids
#         except Exception as exc:
#             if logger:
#                 logger.warning(
#                     "Problem połączenia z bazą (%s/%s): %s",
#                     attempt,
#                     max_retries,
#                     exc,
#                 )
#             if attempt < max_retries:
#                 time.sleep(delay)
#             else:
#                 if logger:
#                     logger.error("FATAL ERROR: brak połączenia z bazą po wielu próbach.")
#                 raise

# W pliku utils.py tymczasowo:
def load_parsed_ids(logger=None, max_retries=10, delay=5):
    return set()  # Zwraca pusty set, nie łączy się z bazą
import os
import logging
from itemadapter import ItemAdapter
from ScraperMieszkan.items import FlatAuctionItem
from ScraperMieszkan.utils import get_db_connection

logger = logging.getLogger(__name__)


class DatabasePipeline:
    def open_spider(self, spider):
        self.commit_every = int(os.environ.get("DB_COMMIT_EVERY", "50"))
        self._pending = 0
        self.conn = get_db_connection()
        self.cursor = self.conn.cursor()

    def close_spider(self, spider):
        try:
            if self._pending:
                self.conn.commit()
        finally:
            self.cursor.close()
            self.conn.close()

    def process_item(self, item, spider):
        if not isinstance(item, FlatAuctionItem):
            return item

        adapter = ItemAdapter(item)
        self.cursor.execute("SAVEPOINT sp_item")
        try:
            self._upsert_auction(adapter)
            self._insert_price_if_changed(adapter)
            self._pending += 1
            if self._pending >= self.commit_every:
                self.conn.commit()
                self._pending = 0
            else:
                self.cursor.execute("RELEASE SAVEPOINT sp_item")
        except Exception as exc:
            self.conn.rollback()
            self._pending = 0
            logger.exception("Błąd zapisu do bazy dla elementu: %r (error: %s)", item, exc)
        return item

    def _upsert_auction(self, adapter):
        self.cursor.execute(
            """
            INSERT INTO auctions (
                auction_id, url, portal, location_key, tytul, metraz, pokoje, pietro,
                liczba_pieter, rok_budowy, rynek, miasto, dzielnica, ulica, adres_pelny,
                zdjecie_url, liczba_zdjec, opis_dlugosc, last_seen
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (auction_id)
            DO UPDATE SET
                last_seen = EXCLUDED.last_seen,
                tytul = COALESCE(EXCLUDED.tytul, auctions.tytul),
                metraz = COALESCE(EXCLUDED.metraz, auctions.metraz),
                pokoje = COALESCE(EXCLUDED.pokoje, auctions.pokoje),
                pietro = COALESCE(EXCLUDED.pietro, auctions.pietro),
                liczba_pieter = COALESCE(EXCLUDED.liczba_pieter, auctions.liczba_pieter),
                rok_budowy = COALESCE(EXCLUDED.rok_budowy, auctions.rok_budowy),
                rynek = COALESCE(EXCLUDED.rynek, auctions.rynek),
                miasto = COALESCE(EXCLUDED.miasto, auctions.miasto),
                dzielnica = COALESCE(EXCLUDED.dzielnica, auctions.dzielnica),
                ulica = COALESCE(EXCLUDED.ulica, auctions.ulica),
                adres_pelny = COALESCE(EXCLUDED.adres_pelny, auctions.adres_pelny),
                zdjecie_url = COALESCE(EXCLUDED.zdjecie_url, auctions.zdjecie_url),
                liczba_zdjec = COALESCE(EXCLUDED.liczba_zdjec, auctions.liczba_zdjec),
                opis_dlugosc = COALESCE(EXCLUDED.opis_dlugosc, auctions.opis_dlugosc),
                status = 'active'
            """
            ,
            (
                adapter.get("auction_id"),
                adapter.get("url"),
                adapter.get("portal"),
                adapter.get("location_key"),
                adapter.get("tytul"),
                adapter.get("metraz"),
                adapter.get("pokoje"),
                adapter.get("pietro"),
                adapter.get("liczba_pieter"),
                adapter.get("rok_budowy"),
                adapter.get("rynek"),
                adapter.get("miasto"),
                adapter.get("dzielnica"),
                adapter.get("ulica"),
                adapter.get("adres_pelny"),
                adapter.get("zdjecie_url"),
                adapter.get("liczba_zdjec"),
                adapter.get("opis_dlugosc"),
                adapter.get("last_seen") or adapter.get("timestamp"),
            ),
        )

    def _insert_price_if_changed(self, adapter):
        auction_id = adapter.get("auction_id")
        cena_pln = adapter.get("cena_pln")
        cena_za_m2 = adapter.get("cena_za_m2")
        metraz = adapter.get("metraz")
        timestamp = adapter.get("timestamp")

        # Jeśli portal nie podał cena_za_m2, obliczamy sami z cena_pln / metraz
        if cena_za_m2 is None and cena_pln and metraz:
            try:
                m = float(metraz)
                if m > 0:
                    cena_za_m2 = round(int(cena_pln) / m)
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        if cena_pln is None and cena_za_m2 is None:
            return

        self.cursor.execute(
            """
            SELECT cena_pln, cena_za_m2
            FROM price_history
            WHERE auction_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (auction_id,),
        )
        last = self.cursor.fetchone()
        if last and last[0] == cena_pln and last[1] == cena_za_m2:
            return

        self.cursor.execute(
            """
            INSERT INTO price_history (auction_id, cena_pln, cena_za_m2, timestamp)
            VALUES (%s, %s, %s, %s)
            """,
            (auction_id, cena_pln, cena_za_m2, timestamp),
        )

import json
from datetime import datetime, timezone

import scrapy

from ScraperMieszkan.items import FlatAuctionItem, FlatLoader
from ScraperMieszkan.locations import LOCATIONS
from ScraperMieszkan.utils import load_parsed_ids

BASE_URL = "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/{slug}?page={page}"

# Nagłówki imitujące przeglądarkę — zmniejszają ryzyko blokady przez Cloudflare
OTODOM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class OtodomSpider(scrapy.Spider):
    name = "otodom"

    def start_requests(self):
        self.parsed_ids = load_parsed_ids(self.logger)
        for location_key, location in LOCATIONS.items():
            slug = location["otodom_slug"]
            strona = 1
            url = BASE_URL.format(slug=slug, page=strona)
            yield scrapy.Request(
                url,
                callback=self.parse,
                headers=OTODOM_HEADERS,
                cb_kwargs={"location_key": location_key, "slug": slug, "page": strona},
            )

    def parse(self, response, location_key, slug, page):
        # Wykryj blokadę Cloudflare
        if response.status in (403, 429, 503) or b"cf-browser-verification" in response.body:
            self.logger.error(
                f"[otodom] Cloudflare block (HTTP {response.status}) na stronie {page} — "
                "spróbuj uruchomić spider ręcznie lub zmień IP."
            )
            return

        raw_next_data = response.css("script#__NEXT_DATA__::text").get()
        if not raw_next_data:
            self.logger.warning(
                f"[otodom] Brak __NEXT_DATA__ na stronie {page} ({response.url}). "
                f"Status: {response.status}. "
                "Prawdopodobna blokada — brak danych otodom w tej sesji."
            )
            return

        data = json.loads(raw_next_data)
        
        # Bezpieczne pobieranie ścieżki do ofert
        page_props = data.get("props", {}).get("pageProps", {})
        search_ads = page_props.get("data", {}).get("searchAds", {})
        items = search_ads.get("items", [])
        
        # Jeśli lista jest pusta, przerywamy paginację
        if not items:
            self.logger.info("Brak wyników na tej stronie. Koniec paginacji.")
            return

        pietro_map = {
            "GROUND": "0",
            "GROUND_FLOOR": "0",
            "FIRST": "1",
            "SECOND": "2",
            "THIRD": "3",
            "FOURTH": "4",
            "FIFTH": "5",
            "SIXTH": "6",
            "SEVENTH": "7",
            "EIGHTH": "8",
            "NINTH": "9",
            "TENTH": "10",
            "ABOVE_TENTH": "10+",
        }
        pokoje_map = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "FIVE_OR_MORE": 5}

        for raw_item in items:
            try:
                auction_id = str(raw_item.get("id"))
                slug_item = raw_item.get("slug", "")
                url = f"https://www.otodom.pl/pl/oferta/{slug_item}" if slug_item else ""
                tytul = raw_item.get("title")
                
                cena_pln = raw_item.get("totalPrice", {}).get("value") if raw_item.get("totalPrice") else None
                cena_za_m2 = raw_item.get("pricePerSquareMeter", {}).get("value") if raw_item.get("pricePerSquareMeter") else None
                metraz = raw_item.get("areaInSquareMeters")
                
                images = raw_item.get("images", [])
                zdjecie_url = images[0].get("large") if images else None
                liczba_zdjec = raw_item.get("totalPossibleImages", len(images))

                # Bezpieczne wyciąganie lokalizacji
                location_data = raw_item.get("location", {})
                address_data = location_data.get("address", {})
                miasto = address_data.get("city", {}).get("name", "") if address_data.get("city") else ""
                
                # Dzielnica (z reverseGeocoding)
                reverse_geo = location_data.get("reverseGeocoding", {}).get("locations", [])
                dzielnica = next((l.get("name", "") for l in reverse_geo if l.get("locationLevel") == "district"), "")

                street_data = address_data.get("street")
                ulica = street_data.get("name", "") if street_data else ""

                pietro_raw = raw_item.get("floorNumber", "")
                pietro = pietro_map.get(pietro_raw, pietro_raw)
                pokoje = pokoje_map.get(raw_item.get("roomsNumber", ""), None)

                loader = FlatLoader(item=FlatAuctionItem())
                loader.add_value("auction_id", auction_id)
                loader.add_value("url", url)
                loader.add_value("portal", "otodom")
                loader.add_value("location_key", location_key)
                loader.add_value("tytul", tytul)
                loader.add_value("cena_pln", cena_pln)
                loader.add_value("cena_za_m2", cena_za_m2)
                loader.add_value("metraz", metraz)
                loader.add_value("pokoje", pokoje)
                loader.add_value("pietro", pietro)
                loader.add_value("miasto", miasto)
                loader.add_value("dzielnica", dzielnica)
                loader.add_value("ulica", ulica)
                loader.add_value("adres_pelny", ", ".join([x for x in [ulica, dzielnica, miasto] if x]))
                loader.add_value("zdjecie_url", zdjecie_url)
                loader.add_value("liczba_zdjec", liczba_zdjec)
                
                now = datetime.now(timezone.utc)
                loader.add_value("timestamp", now)
                loader.add_value("last_seen", now)
                item = loader.load_item()

                if auction_id in self.parsed_ids:
                    yield item
                else:
                    yield scrapy.Request(
                        url,
                        callback=self.parse_details,
                        headers={**OTODOM_HEADERS, "Referer": response.url},
                        cb_kwargs={"item": item},
                    )
            except Exception as exc:
                self.logger.warning("Błąd parsowania item %s: %s", raw_item.get("id"), exc)
                continue

        # Sprawdzenie limitu stron PRZED wygenerowaniem kolejnego zapytania
        if page >= int(getattr(self, "max_stron", 10)):
            self.logger.info(f"Osiągnięto limit stron ({page}). Zatrzymuję paginację.")
            return

        next_page = page + 1
        next_headers = {**OTODOM_HEADERS, "Referer": response.url}
        yield scrapy.Request(
            BASE_URL.format(slug=slug, page=next_page),
            callback=self.parse,
            headers=next_headers,
            cb_kwargs={"location_key": location_key, "slug": slug, "page": next_page},
        )

    def parse_details(self, response, item):
        loader = FlatLoader(item=item, response=response)
        opis = response.css("div[data-cy='adPageAdDescription']::text").getall()
        loader.add_value("opis_dlugosc", len(" ".join(opis)))
        yield loader.load_item()
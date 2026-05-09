import re
from datetime import datetime, timezone

import scrapy

from ScraperMieszkan.items import FlatAuctionItem, FlatLoader
from ScraperMieszkan.utils import load_parsed_ids


class OlxSpider(scrapy.Spider):
    name = "olx"
    miasto = "krakow"
    max_stron = 10

    def start_requests(self):
        self.parsed_ids = load_parsed_ids(self.logger)
        miasto = getattr(self, "miasto", "krakow").lower()
        url = f"https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/{miasto}/"
        yield scrapy.Request(url, callback=self.parse, cb_kwargs={"strona": 1})

    def parse(self, response, strona):
        offers = response.css('div[data-cy="l-card"]')

        if not offers:
            self.logger.warning(f"Brak ogłoszeń na stronie {strona}")
            return

        self.logger.info(f"Strona {strona}: znaleziono {len(offers)} ogłoszeń")

        for offer in offers:
            link = offer.css("a::attr(href)").get("")
            # auction_id wyciągamy z końca URL — np. "IDabc123"
            match = re.search(r"(ID[a-zA-Z0-9]+)(?:\.html)?/?$", link)
            if not match:
                continue
            auction_id = match.group(1)

            # Budujemy pełny URL
            url = response.urljoin(link)

            title = offer.css("h6::text").get("").strip()

            # Cena — usuwamy " zł", spacje, zamieniamy przecinek na kropkę
            price_raw = offer.css('p[data-testid="ad-price"]::text').get("").strip()
            cena_pln = _parse_price(price_raw)

            # Lokalizacja — format "Kraków, Krowodrza - 2 godz. temu"
            loc_raw = offer.css('p[data-testid="location-date"]::text').get("").strip()
            adres_pelny = loc_raw.split(" - ")[0].strip() if loc_raw else ""

            # Zdjęcie
            zdjecie = offer.css("img::attr(src)").get("").strip()

            now = datetime.now(timezone.utc)

            loader = FlatLoader(item=FlatAuctionItem())
            loader.add_value("auction_id", auction_id)
            loader.add_value("url", url)
            loader.add_value("portal", "olx")
            loader.add_value("location_key", getattr(self, "miasto", "krakow"))
            loader.add_value("tytul", title)
            loader.add_value("cena_pln", cena_pln)
            loader.add_value("adres_pelny", adres_pelny)
            loader.add_value("zdjecie_url", zdjecie)
            loader.add_value("timestamp", now)
            loader.add_value("last_seen", now)
            item = loader.load_item()

            # Jeśli już mamy szczegóły — nie wchodź ponownie
            if auction_id in self.parsed_ids:
                yield item
            else:
                yield scrapy.Request(
                    url,
                    callback=self.parse_details,
                    cb_kwargs={"item": item},
                )

        # Paginacja przez przycisk "następna strona"
        max_stron = int(getattr(self, "max_stron", 10))
        if strona >= max_stron:
            return

        next_page = response.css('a[data-testid="pagination-forward"]::attr(href)').get()
        if next_page:
            yield scrapy.Request(
                response.urljoin(next_page),
                callback=self.parse,
                cb_kwargs={"strona": strona + 1},
            )

    def parse_details(self, response, item):
        """Doczytuje szczegóły z podstrony ogłoszenia."""
        loader = FlatLoader(item=item, response=response)

        # Parametry w formie listy: "Powierzchnia", "Liczba pokoi", "Poziom"
        for spec in response.css('li[data-testid="ad-spec-item"]'):
            label = spec.css("p:first-child::text").get("").strip().lower()
            value = spec.css("p:last-child::text").get("").strip()

            if "powierzchnia" in label:
                loader.add_value("metraz", _parse_number(value))
            elif "liczba pokoi" in label or "pokoje" in label:
                loader.add_value("pokoje", _parse_number(value))
            elif "poziom" in label or "piętro" in label:
                loader.add_value("pietro", value)
            elif "rok budowy" in label:
                loader.add_value("rok_budowy", _parse_number(value))
            elif "rynek" in label:
                loader.add_value("rynek", value)

        # Długość opisu
        opis = " ".join(
            response.css("div[data-cy='ad_description'] *::text").getall()
        ).strip()
        if opis:
            loader.add_value("opis_dlugosc", len(opis))

        # Liczba zdjęć
        zdjecia = response.css("img[data-testid='swiper-image']::attr(src)").getall()
        if zdjecia:
            loader.add_value("liczba_zdjec", len(zdjecia))

        yield loader.load_item()


def _parse_price(tekst):
    """'1 250 000 zł' → 1250000"""
    if not tekst:
        return None
    digits = re.sub(r"[^\d]", "", tekst)
    return int(digits) if digits else None


def _parse_number(tekst):
    """'52,5 m²' → 52.5 lub '3' → 3"""
    if not tekst:
        return None
    match = re.search(r"[\d]+[,.]?[\d]*", tekst)
    if match:
        try:
            return float(match.group().replace(",", "."))
        except ValueError:
            return None
    return None
import re
from datetime import datetime, timezone

import scrapy

from ScraperMieszkan.items import FlatAuctionItem, FlatLoader
from ScraperMieszkan.utils import load_parsed_ids


class NroSpider(scrapy.Spider):
    name = "nro"
    miasto = "krakow"
    max_stron = 10

    def start_requests(self):
        self.parsed_ids = load_parsed_ids(self.logger)
        miasto = getattr(self, "miasto", "krakow").lower()
        url = f"https://{miasto}.nieruchomosci-online.pl/mieszkania,sprzedaz/"
        yield scrapy.Request(url, callback=self.parse, cb_kwargs={"strona": 1})

    def parse(self, response, strona):
        # Selektor oparty na rzeczywistym HTML: div.tile-tile z atrybutem data-id
        offers = response.css("div[data-id]")

        if not offers:
            self.logger.warning(f"Brak ogłoszeń na stronie {strona} — {response.url}")
            return
        self.logger.info(f"Strona {strona}: znaleziono {len(offers)} ogłoszeń")

        for offer in offers:
            auction_id = offer.attrib.get("data-id", "")
            if not auction_id:
                continue

            # Link i tytuł z h2 a
            link = offer.css("h2 a::attr(href)").get("")
            if not link:
                continue
            if not link.startswith("http"):
                link = response.urljoin(link)

            title = offer.css("h2 a::text").get("").strip()

            # Cena — "1 490 000 zł" jest w span wewnątrz p.primary-display
            price_raw = offer.css("p.primary-display span:first-child::text").get("").strip()
            cena_pln = _parse_price(price_raw)

            # Metraż — span.area wewnątrz p.primary-display
            area_raw = offer.css("span.area::text").get("").strip()
            metraz = _parse_number(area_raw)

            # Cena za m² — span#secondary-display_* (ukryty ale jest w HTML)
            price_m2_raw = offer.css("span[id^='secondary-display']::text").get("").strip()
            cena_za_m2 = _parse_number(price_m2_raw)

            # Lokalizacja z p.province
            location_parts = offer.css("p.province *::text").getall()
            location = ", ".join(p.strip().rstrip(",") for p in location_parts if p.strip())

            # Wyciągnij dzielnicę: ostatni człon lokalizacji, jeśli to nie jest miasto ani województwo
            MIASTA_NAZWY = {"Kraków", "Warszawa", "Wrocław", "Gdańsk", "Poznań", "Łódź", "Katowice"}
            WOJEW = {"małopolskie", "mazowieckie", "dolnośląskie", "pomorskie", "wielkopolskie",
                     "śląskie", "lubelskie", "podkarpackie", "łódzkie", "kujawsko-pomorskie"}
            SEPARATORY = {">", "›", "|", ",", "/"}
            clean_parts = [p.strip().rstrip(",") for p in location_parts
                           if p.strip() and p.strip() not in SEPARATORY]
            meaningful = [p for p in clean_parts
                          if p not in MIASTA_NAZWY and p.lower() not in WOJEW]
            dzielnica_nro = meaningful[-1] if meaningful else ""

            # Rynek — z div.abap__box
            rynek_raw = offer.css("p.abap span::text").get("").strip().lower()
            if "pierwotny" in rynek_raw:
                rynek = "pierwotny"
            elif "wtórny" in rynek_raw or "secondary" in offer.attrib.get("data-market-type", ""):
                rynek = "wtórny"
            else:
                rynek = ""

            # Piętro — "Piętro: 5 / 7"
            pietro = ""
            liczba_pieter = None
            for attr_item in offer.css("div.attributes__box--item"):
                label = attr_item.css("span::text").get("").strip().lower()
                if "piętro" in label:
                    strongs = attr_item.css("strong::text").getall()
                    if strongs:
                        pietro = strongs[0].strip()
                        if len(strongs) >= 3:
                            liczba_pieter = _parse_number(strongs[2])

            # Pokoje
            pokoje = None
            for attr_item in offer.css("div.attributes__box--item"):
                label = attr_item.css("span::text").get("").strip().lower()
                if "liczba pokoi" in label:
                    val = attr_item.css("strong::text").get("").strip()
                    pokoje = _parse_number(val)

            # Rok budowy
            rok_budowy = None
            for attr_item in offer.css("div.attributes__box--item"):
                label = attr_item.css("span::text").get("").strip().lower()
                if "rok budowy" in label:
                    val = attr_item.css("strong::text").get("").strip()
                    rok_budowy = _parse_number(val)

            # Zdjęcie — img.state--fit-type--fill__main-photo
            zdjecie = offer.css("img.state--fit-type--fill__main-photo::attr(src)").get("")

            now = datetime.now(timezone.utc)

            loader = FlatLoader(item=FlatAuctionItem())
            loader.add_value("auction_id", auction_id)
            loader.add_value("url", link)
            loader.add_value("portal", "nro")
            loader.add_value("location_key", getattr(self, "miasto", "krakow"))
            loader.add_value("tytul", title)
            loader.add_value("cena_pln", cena_pln)
            loader.add_value("cena_za_m2", cena_za_m2)
            loader.add_value("metraz", metraz)
            loader.add_value("pokoje", pokoje)
            loader.add_value("pietro", pietro)
            loader.add_value("liczba_pieter", liczba_pieter)
            loader.add_value("rok_budowy", rok_budowy)
            loader.add_value("rynek", rynek)
            loader.add_value("adres_pelny", location)
            MIASTA = {"krakow": "Kraków", "warszawa": "Warszawa", "wroclaw": "Wrocław", "gdansk": "Gdańsk", "poznan": "Poznań"}
            loader.add_value("miasto", MIASTA.get(getattr(self, "miasto", "krakow"), getattr(self, "miasto", "krakow").capitalize()))
            if dzielnica_nro:
                loader.add_value("dzielnica", dzielnica_nro)
            loader.add_value("zdjecie_url", zdjecie)
            loader.add_value("timestamp", now)
            loader.add_value("last_seen", now)
            item = loader.load_item()

            if auction_id in self.parsed_ids:
                yield item
            else:
                yield scrapy.Request(
                    link,
                    callback=self.parse_details,
                    cb_kwargs={"item": item},
                )

        # Paginacja — /?p=2, /?p=3 itd.
        max_stron = int(getattr(self, "max_stron", 10))
        if strona >= max_stron:
            return

        next_strona = strona + 1
        base = response.url.split("?")[0].rstrip("/")
        next_url = f"{base}/?p={next_strona}"
        yield scrapy.Request(
            next_url,
            callback=self.parse,
            cb_kwargs={"strona": next_strona},
            headers={"Referer": response.url},
        )

    def parse_details(self, response, item):
        loader = FlatLoader(item=item, response=response)

        # Opis
        opis = " ".join(
            response.css(".description *::text, #desc *::text, .offer-description *::text").getall()
        ).strip()
        if opis:
            loader.add_value("opis_dlugosc", len(opis))

        # Zdjęcia
        zdjecia = response.css("img[class*='main-photo']::attr(src), .gallery img::attr(src)").getall()
        if zdjecia:
            loader.add_value("liczba_zdjec", len(zdjecia))
            if not item.get("zdjecie_url"):
                loader.add_value("zdjecie_url", zdjecia[0])

        yield loader.load_item()


def _parse_price(tekst):
    """'1 490 000 zł' → 1490000  (usuwa niełamliwe spacje \xa0)"""
    if not tekst:
        return None
    tekst = tekst.replace("\xa0", "").replace(" ", "")
    digits = re.sub(r"[^\d]", "", tekst.split("zł")[0])
    return int(digits) if digits else None


def _parse_number(tekst):
    if not tekst:
        return None
    tekst = tekst.replace("\xa0", "").replace(" ", "")
    match = re.search(r"[\d]+[,.]?[\d]*", str(tekst))
    if match:
        try:
            return float(match.group().replace(",", "."))
        except ValueError:
            return None
    return None
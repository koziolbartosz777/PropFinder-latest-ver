import re
from datetime import datetime, timezone

import scrapy

from ScraperMieszkan.items import FlatAuctionItem, FlatLoader
from ScraperMieszkan.utils import load_parsed_ids

MIASTA = {
    "krakow": "Kraków",
    "warszawa": "Warszawa",
    "wroclaw": "Wrocław",
    "gdansk": "Gdańsk",
    "poznan": "Poznań",
}


class GratkaSpider(scrapy.Spider):
    name = "gratka"
    miasto = "krakow"
    max_stron = 10

    def start_requests(self):
        self.parsed_ids = load_parsed_ids(self.logger)
        miasto = getattr(self, "miasto", "krakow").lower()
        url = f"https://gratka.pl/nieruchomosci/mieszkania/{miasto}"
        yield scrapy.Request(
            url,
            callback=self.parse,
            cb_kwargs={"strona": 1},
            headers={"Referer": "https://gratka.pl/"},
        )

    def parse(self, response, strona):
        offers = response.css("a.property-card")

        if not offers:
            self.logger.warning(f"Brak ogłoszeń na stronie {strona} — {response.url}")
            return

        self.logger.info(f"Strona {strona}: znaleziono {len(offers)} ogłoszeń")

        for offer in offers:
            link = offer.css("::attr(href)").get("")
            if not link:
                continue
            if not link.startswith("http"):
                link = response.urljoin(link)

            match = re.search(r"/(\d+)(?:\.html)?/?$", link)
            auction_id = match.group(1) if match else link.split("/")[-1].replace(".html", "")
            if not auction_id:
                continue

            title = offer.css(".property-card__header *::text").get("").strip()

            price_raw = " ".join(offer.css(".property-card__price *::text").getall()).strip()
            cena_pln = _parse_price(price_raw)

            price_m2_raw = " ".join(offer.css(".property-card__price-per-m *::text").getall()).strip()
            cena_za_m2 = _parse_number(price_m2_raw)

            details_text = " ".join(offer.css(".property-card__property-description *::text").getall())

            metraz_match = re.search(r"([\d,\.]+)\s*m²", details_text)
            metraz = float(metraz_match.group(1).replace(",", ".")) if metraz_match else None

            pokoje_match = re.search(r"(\d+)\s*pok", details_text, re.IGNORECASE)
            pokoje = int(pokoje_match.group(1)) if pokoje_match else None

            pietro_match = re.search(r"piętro\s*([\d]+)", details_text, re.IGNORECASE)
            pietro = pietro_match.group(1) if pietro_match else None

            zdjecie = (
                offer.css("img.property-card__image::attr(src)").get()
                or offer.css("img::attr(src)").get("")
            )

            now = datetime.now(timezone.utc)
            miasto_key = getattr(self, "miasto", "krakow")

            loader = FlatLoader(item=FlatAuctionItem())
            loader.add_value("auction_id", auction_id)
            loader.add_value("url", link)
            loader.add_value("portal", "gratka")
            loader.add_value("location_key", miasto_key)
            loader.add_value("tytul", title)
            loader.add_value("cena_pln", cena_pln)
            loader.add_value("cena_za_m2", cena_za_m2)
            loader.add_value("metraz", metraz)
            loader.add_value("pokoje", pokoje)
            loader.add_value("pietro", pietro)
            loader.add_value("miasto", MIASTA.get(miasto_key, miasto_key.capitalize()))
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
                    headers={"Referer": response.url},
                )

        max_stron = int(getattr(self, "max_stron", 10))
        if strona >= max_stron:
            return

        next_strona = strona + 1
        base = response.url.split("?")[0]
        next_url = f"{base}?page={next_strona}"
        yield scrapy.Request(
            next_url,
            callback=self.parse,
            cb_kwargs={"strona": next_strona},
            headers={"Referer": response.url},
        )

    def parse_details(self, response, item):
        loader = FlatLoader(item=item, response=response)

        # ── Nowa struktura Gratki: .information-table__row ────────────────
        for row in response.css(".information-table__row"):
            label = row.css("[data-cy='informationTableLabel']::text").get("").strip().lower()
            value = row.css("[data-cy='itemValue']::text").get("").strip()
            if not label or not value:
                continue
            if "pow." in label or "powierzchnia" in label:
                loader.add_value("metraz", _parse_number(value))
            elif "liczba pokoi" in label or "pokoi" in label:
                loader.add_value("pokoje", _parse_number(value))
            elif "piętro" in label and "liczba" not in label:
                _load_pietro(loader, value)
            elif "liczba pięter" in label:
                loader.add_value("liczba_pieter", _parse_number(value))
            elif "rok budowy" in label:
                loader.add_value("rok_budowy", _parse_number(value))
            elif "rynek" in label:
                loader.add_value("rynek", value)

        # ── Piętro z wyróżnionych parametrów (fallback) ───────────────────
        floor_el = response.css(".details-highlighted-parameters__item--floor")
        if floor_el:
            texts = [t.strip() for t in floor_el.css("::text").getall()
                     if t.strip() and t.strip().lower() != "piętro"]
            if texts:
                _load_pietro(loader, texts[0])

        # Lokalizacja ze strony szczegółów
        ulica = response.css("span[data-cy='locationRowTitle']::text").get("").strip()
        if ulica:
            loader.add_value("ulica", ulica)

        main_loc = response.css("div.location-row__main-location *::text").getall()
        main_loc = [t.strip().strip(",") for t in main_loc if t.strip().strip(",")]
        # Usuń duplikaty zachowując kolejność
        seen = set()
        main_loc = [x for x in main_loc if not (x in seen or seen.add(x))]
        # main_loc np.: ["małopolskie", "Kraków", "Podgórze Duchackie"]
        # Ostatni element to dzielnica — ale tylko jeśli NIE jest nazwą miasta
        MIASTA_NAZWY = {"Kraków", "Warszawa", "Wrocław", "Gdańsk", "Poznań", "Łódź", "Katowice",
                        "Szczecin", "Bydgoszcz", "Lublin", "Białystok", "Rzeszów", "Toruń"}
        WOJEW = {"małopolskie", "mazowieckie", "dolnośląskie", "pomorskie", "wielkopolskie",
                 "śląskie", "lubelskie", "podkarpackie", "łódzkie", "kujawsko-pomorskie",
                 "warmińsko-mazurskie", "zachodniopomorskie", "opolskie", "podlaskie",
                 "świętokrzyskie", "lubuskie"}
        dzielnica_raw = main_loc[-1] if main_loc else ""
        dzielnica = dzielnica_raw if (dzielnica_raw
                                      and dzielnica_raw not in MIASTA_NAZWY
                                      and dzielnica_raw.lower() not in WOJEW) else ""
        miasto_loc = next((x for x in reversed(main_loc[:-1]) if x not in WOJEW and x.lower() not in WOJEW), "")
        if dzielnica:
            loader.add_value("dzielnica", dzielnica)
        if dzielnica and miasto_loc:
            loader.add_value("adres_pelny", f"{dzielnica}, {miasto_loc}")
        elif dzielnica:
            loader.add_value("adres_pelny", dzielnica)
        elif miasto_loc:
            loader.add_value("adres_pelny", miasto_loc)


        # Opis
        opis = " ".join(
            response.css(".property-description *::text, .description__content *::text").getall()
        ).strip()
        if opis:
            loader.add_value("opis_dlugosc", len(opis))

        item = loader.load_item()

        # Zdjęcia na podstronie /photo
        photo_url = response.url.rstrip("/") + "/photo"
        yield scrapy.Request(
            photo_url,
            callback=self.parse_photos,
            cb_kwargs={"item": item},
            headers={"Referer": response.url},
        )

    def parse_photos(self, response, item):
        loader = FlatLoader(item=item, response=response)

        zdjecia = response.css("img[data-cy='thumbnail']::attr(src)").getall()
        if zdjecia:
            loader.add_value("liczba_zdjec", len(zdjecia))
            loader.add_value("zdjecie_url", zdjecia[0])

        yield loader.load_item()


def _load_pietro(loader, value: str):
    """Parsuje piętro z wartości np. '1 z 5', '1/5', 'parter', '10', 'D'."""
    v = value.strip().lower()
    if v in ("parter", "przyziemie", "0"):
        loader.add_value("pietro", "0")
    else:
        m = re.search(r"\d+", v)
        if m:
            loader.add_value("pietro", m.group())


def _parse_price(tekst):
    if not tekst:
        return None
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
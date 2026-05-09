import re
import scrapy
from scrapy.loader import ItemLoader
from itemloaders.processors import MapCompose, TakeFirst


def parse_int(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def parse_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    return float(match.group(0)) if match else None


def normalize_city(value):
    if not isinstance(value, str) or not value.strip():
        return value
    value = " ".join(value.split())
    return value.title() if value.isupper() else value


class FlatLoader(ItemLoader):
    default_output_processor = TakeFirst()


class FlatAuctionItem(scrapy.Item):
    auction_id = scrapy.Field()
    url = scrapy.Field()
    portal = scrapy.Field()
    location_key = scrapy.Field()
    tytul = scrapy.Field()
    cena_pln = scrapy.Field(input_processor=MapCompose(parse_int))
    cena_za_m2 = scrapy.Field(input_processor=MapCompose(parse_int))
    metraz = scrapy.Field(input_processor=MapCompose(parse_float))
    pokoje = scrapy.Field(input_processor=MapCompose(parse_int))
    pietro = scrapy.Field()
    liczba_pieter = scrapy.Field(input_processor=MapCompose(parse_int))
    rok_budowy = scrapy.Field(input_processor=MapCompose(parse_int))
    rynek = scrapy.Field()
    miasto = scrapy.Field(input_processor=MapCompose(normalize_city))
    dzielnica = scrapy.Field()
    ulica = scrapy.Field()
    adres_pelny = scrapy.Field()
    zdjecie_url = scrapy.Field()
    liczba_zdjec = scrapy.Field(input_processor=MapCompose(parse_int))
    opis_dlugosc = scrapy.Field(input_processor=MapCompose(parse_int))
    timestamp = scrapy.Field()
    last_seen = scrapy.Field()

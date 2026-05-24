"""
districts.py — Normalizacja nazw dzielnic Krakowa
==================================================
Mapuje wszystkie warianty nazw (z portali Otodom / Gratka / NRO)
na oficjalne nazwy 18 dzielnic administracyjnych Krakowa.

Aby dodać nowe mapowanie: dodaj wpis do DISTRICT_ALIASES.
None jako wartość = wyklucz z rankingu (miasto spoza Krakowa, województwo itp.)
"""

# ── 18 oficjalnych dzielnic ────────────────────────────────────────────────
OFFICIAL_DISTRICTS = [
    "Stare Miasto",          # I
    "Grzegórzki",            # II
    "Prądnik Czerwony",      # III
    "Prądnik Biały",         # IV
    "Krowodrza",             # V
    "Bronowice",             # VI
    "Zwierzyniec",           # VII
    "Dębniki",               # VIII
    "Łagiewniki-Borek Fałęcki",  # IX
    "Swoszowice",            # X
    "Podgórze Duchackie",    # XI
    "Bieżanów-Prokocim",     # XII
    "Podgórze",              # XIII
    "Czyżyny",               # XIV
    "Mistrzejowice",         # XV
    "Bieńczyce",             # XVI
    "Wzgórza Krzesławickie", # XVII
    "Nowa Huta",             # XVIII
]

# ── Słownik alias → nazwa kanoniczna ──────────────────────────────────────
# None jako wartość = wyklucz (nie jest dzielnicą Krakowa)
DISTRICT_ALIASES: dict[str, str | None] = {

    # ── Suffix " Kraków" ──────────────────────────────────────────────────
    "Prądnik Biały Kraków":         "Prądnik Biały",
    "Prądnik Czerwony Kraków":      "Prądnik Czerwony",
    "Krowodrza Kraków":             "Krowodrza",
    "Bronowice Nowe Kraków":        "Bronowice",
    "Bronowice Małe Wschód Kraków": "Bronowice",
    "Mistrzejowice Nowe Kraków":    "Mistrzejowice",
    "Płaszów Kraków":               "Podgórze",
    "Górka Narodowa Kraków":        "Wzgórza Krzesławickie",
    "Ruczaj Kraków":                "Dębniki",
    "Skotniki Kraków":              "Dębniki",
    "Kobierzyn Kraków":             "Dębniki",
    "Prokocim Kraków":              "Bieżanów-Prokocim",
    "Łęg Kraków":                   "Podgórze",
    "Zesławice Kraków":             "Wzgórza Krzesławickie",
    "Złocień Kraków":               "Podgórze Duchackie",
    "Piaski Wielkie Kraków":        "Bieżanów-Prokocim",
    "Swoszowice Kraków":            "Swoszowice",
    "Grzegórzki Stare Kraków":      "Grzegórzki",
    "Stare Podgórze Kraków":        "Podgórze",

    # ── Prefix "Dzielnica [cyfry rzymskie] " ──────────────────────────────
    # Obsługiwane dynamicznie w normalize() — nie trzeba wymieniać każdej

    # ── Warianty historyczne ──────────────────────────────────────────────
    "Stare Miasto (historyczne)":   "Stare Miasto",
    "Nowa Huta (historyczna)":      "Nowa Huta",

    # ── Podgórze / Stare Podgórze ─────────────────────────────────────────
    "Stare Podgórze":               "Podgórze",
    "Podgórze Stare":               "Podgórze",
    "Stare Miasto (historyczne)":   "Stare Miasto",

    # ── Osiedla → dzielnica ───────────────────────────────────────────────
    "Os. Prądnik Biały":            "Prądnik Biały",
    "Os. Prądnik Czerwony":         "Prądnik Czerwony",
    "Os. Ruczaj":                   "Dębniki",
    "Os. Złocień":                  "Podgórze Duchackie",
    "Os. Krowodrza Górka":          "Krowodrza",
    "Os. Na Kozłówce":              "Krowodrza",
    "Os. Piastów":                  "Krowodrza",
    "Os. Nowy Prokocim":            "Bieżanów-Prokocim",
    "Os. Cegielniana":              "Bieżanów-Prokocim",
    "Krowodrza Górka":              "Krowodrza",
    "Ruczaj":                       "Dębniki",
    "Płaszów":                      "Podgórze",
    "Łagiewniki":                   "Łagiewniki-Borek Fałęcki",
    "Łagiewniki-Borek Fałęcki":     "Łagiewniki-Borek Fałęcki",
    "Borek Fałęcki":                "Łagiewniki-Borek Fałęcki",
    "Kliny Borkowskie":             "Łagiewniki-Borek Fałęcki",
    "Pychowice":                    "Dębniki",
    "Skotniki":                     "Dębniki",
    "Kobierzyn":                    "Dębniki",
    "Salwator":                     "Zwierzyniec",
    "Wola Justowska":               "Zwierzyniec",
    "Przegorzały":                  "Zwierzyniec",
    "Bielany":                      "Zwierzyniec",
    "Olsza":                        "Prądnik Czerwony",
    "Olszyny":                      "Prądnik Czerwony",
    "Rakowice":                     "Prądnik Czerwony",
    "Dąbie":                        "Grzegórzki",
    "Wesoła":                       "Grzegórzki",
    "Zabłocie":                     "Grzegórzki",
    "Kazimierz":                    "Stare Miasto",
    "Kleparz":                      "Stare Miasto",
    "Piasek":                       "Stare Miasto",
    "Śródmieście":                  "Stare Miasto",
    "Stradom":                      "Stare Miasto",
    "Podwawelskie":                 "Stare Miasto",
    "Wawel":                        "Stare Miasto",
    "Grzegórzki Stare":             "Grzegórzki",
    "Czyżyny Stare":                "Czyżyny",
    "Bieżanów":                     "Bieżanów-Prokocim",
    "Prokocim":                     "Bieżanów-Prokocim",
    "Nowy Prokocim":                "Bieżanów-Prokocim",
    "Swoszowice":                   "Swoszowice",
    "Kliny":                        "Swoszowice",
    "Kliny Zaciście":               "Swoszowice",
    "Opatkowice":                   "Swoszowice",
    "Wróblowice":                   "Swoszowice",
    "Wola Duchacka":                "Podgórze Duchackie",
    "Kurdwanów":                    "Podgórze Duchackie",
    "Złocień":                      "Podgórze Duchackie",
    "Piaski Wielkie":               "Bieżanów-Prokocim",
    "Rybitwy":                      "Podgórze",
    "Ludwinów":                     "Podgórze",
    "Płaszów":                      "Podgórze",
    "Bonarka":                      "Podgórze",
    "Wzgórza Krzesławickie":        "Wzgórza Krzesławickie",
    "Kantorowice":                  "Wzgórza Krzesławickie",
    "Zesławice":                    "Wzgórza Krzesławickie",
    "Górka Narodowa":               "Wzgórza Krzesławickie",
    "Mistrzejowice Nowe":           "Mistrzejowice",
    "Bieńczyce":                    "Bieńczyce",
    "Azory":                        "Bronowice",
    "Bronowice Małe":               "Bronowice",
    "Bronowice Wielkie":            "Bronowice",

    # ── Dodatkowe osiedla → oficjalna dzielnica ───────────────────────────
    "Albertyńskie":                 "Dębniki",
    "Os. Albertyńskie":             "Dębniki",
    "Czarna Wieś":                  "Krowodrza",
    "Czerwone Maki":                "Dębniki",
    "Kliny Zaciście":               "Swoszowice",
    "Kurdwanów Nowy":               "Podgórze Duchackie",
    "Łobzów":                       "Krowodrza",
    "Mały Płaszów":                 "Podgórze",
    "Mateczny":                     "Dębniki",
    "Mydlniki":                     "Krowodrza",
    "Nowa Wieś":                    "Krowodrza",
    "Nowy Świat":                   "Stare Miasto",
    "Os. Bohaterów Września":       "Nowa Huta",
    "Os. Centrum C":                "Nowa Huta",
    "Os. Centrum D":                "Nowa Huta",
    "Os. Dywizjonu 303":            "Nowa Huta",
    "Os. Hutnicze":                 "Nowa Huta",
    "Os. Kazimierzowskie":          "Nowa Huta",
    "Os. Kombatantów":              "Nowa Huta",
    "Os. Na Lotnisku":              "Czyżyny",
    "Os. Oświecenia":               "Wzgórza Krzesławickie",
    "Os. Podlesie":                 "Swoszowice",
    "Os. Podwawelskie":             "Stare Miasto",
    "Os. Przy Arce":                "Nowa Huta",
    "Os. Szkolne":                  "Bieńczyce",
    "Os. Tysiąclecia":              "Bieńczyce",
    "Os. Złotego Wieku":            "Nowa Huta",
    "Przewóz":                      "Podgórze",
    "Rżąka":                        "Łagiewniki-Borek Fałęcki",
    "Teatralne":                    "Nowa Huta",
    "Tonie":                        "Wzgórza Krzesławickie",
    "Ugorek":                       "Nowa Huta",
    "Witkowice":                    "Wzgórza Krzesławickie",
    "Wola Duchacka":                "Podgórze Duchackie",
    "Zakrzówek":                    "Dębniki",
    "Żabiniec":                     "Prądnik Biały",
    "Żabiniec Kraków":              "Prądnik Biały",
    "Zielone":                      "Bieżanów-Prokocim",
    "Kolorowe":                     "Bieżanów-Prokocim",
    "Kalinowe":                     "Bieżanów-Prokocim",
    "Łęg":                          "Podgórze",
    "Mochnaniec":                   "Swoszowice",
    "Opatkowice":                   "Swoszowice",
    "Wróblowice":                   "Swoszowice",
    "Olsza":                        "Prądnik Czerwony",
    "Wandy":                        "Nowa Huta",
    "Piaski Nowe":                  "Bieżanów-Prokocim",
    "Kurdwanów":                    "Podgórze Duchackie",
    "Kliny Borkowskie":             "Łagiewniki-Borek Fałęcki",
    "Rybitwy":                      "Podgórze",

    # ── Szum — nie-krakowskie / do wykluczenia ────────────────────────────
    "małopolskie":                  None,
    "Wieliczka":                    None,
    "Skawina":                      None,
    "Niepołomice":                  None,
    "Bogucice Wieliczka":           None,
    "Zdrojowe Wieliczka":           None,
    "Zadory Wieliczka":             None,
    "Sidzina":                      None,
    "Branice":                      None,
    "Modlnica":                     None,
    "Czarnochowice":                None,
    "Michałowice":                  None,
    "Krzyszkowice":                 None,
    "Libertów":                     None,
}


import re as _re
_ROMAN_PREFIX = _re.compile(r"^Dzielnica [IVXLC]+ ")

# Numer porządkowy oficjalnych dzielnic (do sortowania)
_OFFICIAL_ORDER: dict[str, int] = {d: i + 1 for i, d in enumerate(OFFICIAL_DISTRICTS)}


def normalize(name: str | None) -> str | None:
    """
    Zwraca kanoniczną nazwę dzielnicy lub None (wyklucz).
    Kolejność sprawdzania:
    1. Słownik DISTRICT_ALIASES
    2. Dynamiczne reguły (suffix ' Kraków', prefix 'Dzielnica X ')
    3. Oryginalna nazwa (passthrough)
    """
    if not name:
        return None

    # 1. Explicit alias
    if name in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name]

    # 2. Suffix " Kraków"
    if name.endswith(" Kraków"):
        stripped = name[:-7]  # len(" Kraków") == 7
        return DISTRICT_ALIASES.get(stripped, stripped)

    # 3. Prefix "Dzielnica [cyfry rzymskie] "
    if _ROMAN_PREFIX.match(name):
        stripped = _ROMAN_PREFIX.sub("", name)
        return DISTRICT_ALIASES.get(stripped, stripped)

    return name


def sql_case(col: str = "dzielnica") -> str:
    """
    Generuje fragment SQL CASE ... END normalizujący kolumnę 'col'.
    Używaj w zapytaniach app.py zamiast hardcodowanego CASE.

    Przykład:
        sql = f"SELECT {sql_case('a.dzielnica')} AS dzielnica ..."
    """
    lines = ["CASE"]

    # Explicit aliases (None = NULL = wyklucz)
    for raw, canonical in DISTRICT_ALIASES.items():
        escaped_raw = raw.replace("'", "''")
        if canonical is None:
            lines.append(f"  WHEN {col} = '{escaped_raw}' THEN NULL")
        else:
            escaped_can = canonical.replace("'", "''")
            lines.append(f"  WHEN {col} = '{escaped_raw}' THEN '{escaped_can}'")

    # Dynamiczne reguły (stosowane gdy brak jawnego aliasu)
    lines.append(f"  WHEN {col} ~ '^Dzielnica [IVXLC]+ '")
    lines.append(f"    THEN REGEXP_REPLACE({col}, '^Dzielnica [IVXLC]+ ', '')")
    lines.append(f"  WHEN {col} LIKE '%% Kraków'")
    lines.append(f"    THEN TRIM(REGEXP_REPLACE({col}, ' Kraków$', ''))")

    lines.append(f"  ELSE {col}")
    lines.append("END")
    return "\n".join(lines)


def sql_order_case(col: str = "dzielnica") -> str:
    """
    Generuje SQL CASE przypisujący numer porządkowy oficjalnej dzielnicy (1–18).
    Nieoficjalne sub-dzielnice dostają 99 → lądują na końcu posortowane alfabetycznie.

    Użycie w ORDER BY:
        ORDER BY {sql_order_case('dzielnica')}, dzielnica
    """
    lines = ["CASE"]
    for district, order_num in _OFFICIAL_ORDER.items():
        escaped = district.replace("'", "''")
        lines.append(f"  WHEN {col} = '{escaped}' THEN {order_num}")
    lines.append(f"  ELSE 99")
    lines.append("END")
    return "\n".join(lines)

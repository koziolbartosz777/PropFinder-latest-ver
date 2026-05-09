CREATE TABLE auctions (
    auction_id      TEXT PRIMARY KEY,
    url             TEXT,
    portal          TEXT,
    location_key    TEXT,
    tytul           TEXT,
    metraz          NUMERIC,
    pokoje          SMALLINT,
    pietro          TEXT,
    liczba_pieter   SMALLINT,
    rok_budowy      SMALLINT,
    rynek           TEXT,
    miasto          TEXT,
    dzielnica       TEXT,
    ulica           TEXT,
    adres_pelny     TEXT,
    zdjecie_url     TEXT,
    liczba_zdjec    SMALLINT,
    opis_dlugosc    INTEGER,
    status          TEXT DEFAULT 'active',
    first_seen      TIMESTAMPTZ DEFAULT NOW(),
    last_seen       TIMESTAMPTZ
);

CREATE TABLE price_history (
    id          SERIAL PRIMARY KEY,
    auction_id  TEXT REFERENCES auctions(auction_id),
    cena_pln    INTEGER,
    cena_za_m2  INTEGER,
    timestamp   TIMESTAMPTZ
);

CREATE INDEX idx_auctions_location ON auctions(location_key);
CREATE INDEX idx_auctions_status   ON auctions(status);
CREATE INDEX idx_price_auction     ON price_history(auction_id);

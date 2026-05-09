Projekt jest w pełni gotowy. Oto kompletny overview:

---

# PropAgent — Dokumentacja projektu

## Status projektu: ✅ Gotowy do wdrożenia

---

## 1. Czym jest PropAgent?

PropAgent to **autonomiczny agregator i analizator rynku nieruchomości** dla Krakowa. System codziennie pobiera oferty sprzedaży mieszkań z trzech największych portali ogłoszeniowych, przechowuje ich historię cenową i udostępnia je przez przejrzysty interfejs webowy z zaawansowaną analityką i wskaźnikami atrakcyjności każdej oferty.

Cel: dać kupującemu przewagę informacyjną — wiedzieć, czy dana oferta jest tania czy droga względem rynku, zanim w ogóle zadzwoni do agenta.

---

## 2. Architektura systemu

```
┌─────────────────────────────────────────────────────┐
│              Windows Task Scheduler                  │
│         (uruchamia run_scraper.py codziennie)        │
└────────────────────┬────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │     run_scraper.py    │
         │  sekwencyjny runner   │
         └───────────┬───────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───▼───┐      ┌─────▼──┐      ┌─────▼──┐
│OtoDom │      │ Gratka │      │  NRO   │
│Spider │      │ Spider │      │ Spider │
└───┬───┘      └────┬───┘      └────┬───┘
    └────────────────┼────────────────┘
                     │
         ┌───────────▼───────────┐
         │  DatabasePipeline     │
         │  (pipelines.py)       │
         │  upsert + price hist  │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │     PostgreSQL        │
         │  (Docker container)   │
         │  auctions             │
         │  price_history        │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │      Flask app        │
         │      (app.py)         │
         │  + Jinja2 templates   │
         └───────────────────────┘
```

**Stack technologiczny:**
- **Scraping:** Python 3, Scrapy
- **Baza danych:** PostgreSQL 15 (Docker)
- **Backend:** Flask + psycopg2
- **Frontend:** Vanilla JS, Leaflet.js, CSS custom
- **Automatyzacja:** Windows Task Scheduler
- **Geocoding:** Nominatim (OpenStreetMap) + localStorage cache

---

## 3. Funkcje — pełna lista

### 3.1 Scraping i zbieranie danych

| Portal | Źródło | Scraped fields |
|---|---|---|
| **OtoDom** | JSON embed w HTML (`reverseGeocoding`) | Cena, metraż, pokoje, piętro, rok budowy, rynek, dzielnica z GPS, ulica, zdjęcia |
| **Gratka** | CSS selektory ze szczegółów oferty | Cena, metraż, pokoje, piętro, rok budowy, rynek, lokalizacja z breadcrumba |
| **NRO** (Nieruchomości Online) | CSS z listy + szczegóły | Cena, metraż, pokoje, piętro, rok budowy, rynek, lokalizacja z `p.province` |

**Konfiguracja:**
- Scraper uruchamia się codziennie o 21:00 przez Task Scheduler
- Parametryzowany: zmiana miast i liczby stron w 3 liniach `run_scraper.py`
- Timeout 1h per spider, błąd jednego nie zatrzymuje kolejnych
- Log każdego uruchomienia w `scraper_log.txt`

**Baza danych:**
- Tabela `auctions` — dane ogłoszenia (upsert przy każdym scrapowaniu)
- Tabela `price_history` — historia cen: nowy wpis tylko gdy cena się zmienia
- Pole `status` (`active`/`sold`) — automatycznie ustawiane przez `mark_sold.py`

---

### 3.2 Interfejs webowy — strona główna

**Filtry (sidebar):**
- Portal (OtoDom / Gratka / NRO / Wszystkie)
- Cena PLN (zakres od–do)
- Cena za m² (zakres od–do)
- Metraż (zakres od–do)
- Liczba pokoi (multi-select: 1, 2, 3, 4, 5+)
- Rynek (pierwotny / wtórny / wszystkie)
- Rok budowy (zakres)
- Piętro (zakres)
- Wyszukiwanie tekstowe (tytuł, adres, dzielnica, ulica)

**Sortowanie:**
- Najnowsze / Cena / Metraż / Cena za m² / Rok budowy
- Rosnąco / Malejąco

**Widoki:**
- **Siatka (grid)** — karty z dużym zdjęciem
- **Lista** — poziome karty z więcej danymi jednocześnie
- Wybór zapisany w `localStorage` — przetrwa paginację i przeładowanie

**Mieszanie portali (round-robin):**
- Zamiast grupować oferty po portalu, system przeplatuje je: OtoDom → Gratka → NRO → OtoDom…
- Rozwiązanie: `ROW_NUMBER() OVER (PARTITION BY portal ORDER BY ...)` + `ORDER BY _rn, portal`

**Paginacja:** 24 oferty na stronie, nawigacja z zachowaniem wszystkich filtrów.

---

### 3.3 Mapa interaktywna (Leaflet.js)

- Przyciski „Pokaż na mapie" na każdej karcie — otwiera mapę i centruje na konkretnej ofercie
- Geokodowanie adresów przez Nominatim (OpenStreetMap) — bez płatnego API
- **Cache geokodowania w `localStorage`** — każdy adres geokodowany tylko raz, kolejne wyświetlenia natychmiastowe
- **Kolejka sieciowa** — odstęp 1150ms między zapytaniami (limit Nominatim: 1 req/s)
- **Klastry** — wiele ofert pod tym samym adresem łączy się w jeden marker ze scrollowalnym popupem
- Kolory markerów według portalu (czerwony OtoDom, niebieski Gratka, zielony NRO)
- „Przenieś do oferty" w popupie mapy — scrolluje do karty na liście i podświetla ją
- Korelacja mapa↔karty: otwarcie popupu podświetla odpowiednie karty, zamknięcie zdejmuje podświetlenie

---

### 3.4 Wskaźnik atrakcyjności cenowej

Każda oferta z min. 3 bliźniaczymi ogłoszeniami otrzymuje kolorowy badge:

**Metodologia:**
1. Znalezienie bliźniaków: ta sama dzielnica + ta sama liczba pokoi + metraż ±20%
2. Policzenie ilu bliźniaków ma niższą cenę za m² (`pct_tanszych`)
3. Wyświetlenie percentyla w grupie

| Badge | Kolor | Znaczenie |
|---|---|---|
| Tańsza niż 80%+ podobnych | 🟢 | Bardzo atrakcyjna cena |
| Tańsza niż 60–79% podobnych | 🟩 | Dobra cena |
| Blisko średniej rynku | 🟡 | Typowa cena |
| Droższa niż 60–79% podobnych | 🟠 | Powyżej rynku |
| Droższa niż 80%+ podobnych | 🔴 | Znacząco przeszacowana |

**Gwarancje jakości:**
- Badge nie pojawia się gdy brak ceny (`cena do uzgodnienia`)
- Badge nie pojawia się gdy brak dzielnicy (brak możliwości precyzyjnego porównania)
- Badge nie pojawia się gdy mniej niż 3 bliźniaki
- Cena za m² obliczana automatycznie gdy portal jej nie podaje (`cena_pln / metraz`)

**Toggle w sidebarze** — można wyłączyć badge'e, stan zapamiętany w `localStorage`.

---

### 3.5 Zakładka „Analiza rynku"

**Ranking dzielnic:**
- Tabela TOP 20 dzielnic posortowanych po medianie ceny za m²
- Kolumny: liczba ofert, mediana zł/m², średnia zł/m², śr. metraż, śr. dni na rynku
- Mediana (nie średnia) — odporna na luksusowe penthouse'y zaburzające ocenę
- Gradient kolorów na kolumnie mediany

**Rozkład cenowy:**
- Horyzontalne słupki pokazujące liczbę ofert w przedziałach: do 400k, 400–600k, 600–800k, 800k–1mln, 1–1,5mln, powyżej 1,5mln

**Najlepsze okazje:**
- TOP 20 ofert najtańszych względem bliźniaków (min. 3 porównywalne)
- Te same kryteria co badge na kartach

**Statystyki per portal:**
- Liczba aktywnych ofert, średnia cena, średnia cena za m² dla każdego portalu

---

### 3.6 Automatyzacja i utrzymanie danych

**Codzienny runner (`run_scraper.py`)** wykonuje sekwencyjnie:
1. Scraping każdego portalu dla każdego miasta
2. **Migracja `cena_za_m2`** — uzupełnia NULL-e w `price_history` dla rekordów historycznych
3. **Migracja `dzielnica` NRO** — wyciąga dzielnicę z `adres_pelny` dla ofert bez dzielnicy
4. **Czyszczenie błędnych dzielnic Gratki** — usuwa przypadki gdzie `dzielnica = "Kraków"` (nazwa miasta zamiast dzielnicy)
5. **`mark_sold`** — oferty niewidziane od ostatniego scrapowania otrzymują `status = 'sold'`

**Task Scheduler (`setup_task_scheduler.bat`):**
- Instalacja jednym klikiem (jako Administrator)
- Uruchamia `run_scraper.py` codziennie o 21:00
- Używa `pythonw.exe` — brak okna konsoli w tle

---

## 4. Napotkane problemy i ich rozwiązania

### Problem 1: OtoDom dominował w wynikach
**Objaw:** Pierwsze 3+ strony wyników to wyłącznie OtoDom, inne portale dopiero na końcu.  
**Przyczyna:** Prosty `ORDER BY last_seen DESC` zgrupował oferty chronologicznie, a OtoDom był najnowiej scrapowany.  
**Rozwiązanie:** SQL `ROW_NUMBER() OVER (PARTITION BY portal ORDER BY ...)` + zewnętrzny `ORDER BY _rn ASC, portal ASC` — round-robin gwarantuje przeplatanie portali na każdej stronie niezależnie od kolejności scrapowania.

---

### Problem 2: Gratka nie podaje ceny za m²
**Objaw:** Kolumna `cena_za_m2` NULL dla wszystkich ofert Gratki → brak badge'a, brak sortowania po cenie/m², brak w statystykach.  
**Przyczyna:** Portal nie wyświetla ceny za m² w CSS selektorze używanym przez spider.  
**Rozwiązanie (3-warstwowe):**
1. `pipelines.py` — oblicza `cena_za_m2 = round(cena_pln / metraz)` przy zapisie nowych danych
2. `app.py` — COALESCE w każdym zapytaniu SQL: `COALESCE(cena_za_m2, ROUND(cena_pln/metraz))`
3. `run_scraper.py` — migracja backfilluje historyczne rekordy z NULL

---

### Problem 3: Wskaźnik atrakcyjności miał odwróconą logikę
**Objaw:** Oferta za 14 850 zł/m² przy medianie dzielnicy 16 213 zł/m² pokazywała „Droższa niż 95% podobnych" (czerwony badge) zamiast zielonego.  
**Przyczyna:** `pct_tanszych` = % bliźniaków *tańszych* od danej oferty. Niski wynik (5%) = mało tańszych od nas = **my jesteśmy tani**. Kod interpretował to odwrotnie.  
**Rozwiązanie:** Inwersja progu: `pct <= 20` → zielony (nie `pct >= 80`), label `"Tańsza niż {{ 100 - pct }}%"` (nie `pct%`).

---

### Problem 4: NRO nie scrapowal dzielnicy
**Objaw:** ~44% wszystkich ofert (458 z ~1045) to NRO — żadna bez dzielnicy nie dostawała badge'a.  
**Przyczyna:** Spider NRO zapisywał `adres_pelny = "Kraków, Grzegórzki"`, ale nie parsował dzielnicy do osobnego pola.  
**Rozwiązanie:**
1. Spider: wyciąga `dzielnica_nro` filtrując `location_parts` z wykluczeniem nazw miast i województw
2. Migracja: `REGEXP_REPLACE(adres_pelny, '^.*,\s*', '')` wyciąga ostatni człon dla istniejących rekordów

---

### Problem 5: Gratka ustawiała `dzielnica = "Kraków"` (nazwa miasta)
**Objaw:** Oferty Gratki bez konkretnej dzielnicy w breadcrumbie tworzyły fałszywą grupę porównawczą `dzielnica = "Kraków"` — porównywały się ze sobą zamiast z prawdziwymi sąsiadami.  
**Przyczyna:** `dzielnica = main_loc[-1]` bez sprawdzenia czy ostatni człon to miasto.  
**Rozwiązanie:** Guard `MIASTA_NAZWY` — jeśli ostatni człon jest nazwą miasta, `dzielnica = ""`. Migracja czyści historyczne błędy w bazie.

---

### Problem 6: Fallback „cały Kraków" był mylący
**Objaw:** Oferty bez dzielnicy (historyczne NRO + Gratka bez powiatu) porównywane ze wszystkimi ofertami w mieście — wynik mało miarodajny (centrum vs. obrzeża).  
**Decyzja:** Usunięcie fallbacku. Badge pojawia się **tylko** przy precyzyjnym dopasowaniu dzielnicy. Brak danych = brak badge'a. Uczciwe > przybliżone.

---

### Problem 7: Widok grid/lista resetował się przy paginacji
**Przyczyna:** Stan JS (wybór widoku) był tracony przy każdym przeładowaniu strony przez paginację.  
**Rozwiązanie:** `localStorage.setItem('propView', v)` przy zmianie + IIFE przywracający stan na każdym load.

---

### Problem 8: Mapa geocodowała adresy przy każdej wizycie
**Objaw:** Przy każdym wejściu na stronę 24 zapytania do Nominatim z 1150ms odstępem = ~28 sekund oczekiwania na piny.  
**Rozwiązanie:** Cache geocodingu w `localStorage` z kluczem `geo:adres` — każdy adres geokodowany dokładnie raz, potem pojawia się natychmiast.

---

## 5. Co dalej — możliwe rozszerzenia

| Funkcja | Złożoność | Wartość |
|---|---|---|
| Powiadomienia e-mail / push gdy pojawi się oferta pasująca do zapisanych filtrów | Średnia | Wysoka |
| Wykres historii ceny dla konkretnej oferty | Niska | Wysoka |
| Więcej miast (Warszawa, Wrocław, Gdańsk) | Niska — 1 linia config | Wysoka |
| Analiza trendów cenowych w czasie (ceny miesięcznie per dzielnica) | Średnia | Wysoka |
| Eksport do CSV/Excel | Niska | Średnia |
| Dodanie OLX (spider już częściowo napisany) | Niska | Średnia |
| Kalkulator zdolności kredytowej inline | Niska | Średnia |
| Porównywarka ofert side-by-side | Średnia | Średnia |
| API publiczne (REST) | Średnia | Wysoka dla B2B |

---

## 6. Liczby

- **~1 350 aktywnych ofert** z 3 portali w bazie (Kraków)
- **Dzienny przyrost:** ~50–150 nowych ogłoszeń
- **Czas scrapowania:** ~15–30 min / dzień (3 pająki × ~5–10 min)
- **Czas odpowiedzi UI:** <200ms (zapytania SQL z LATERAL join)
- **Geocoding:** pierwsze wejście ~28s (24 piny ×1.15s), każde kolejne <1s (cache)
- **Koszt infrastruktury:** 0 zł (lokalnie) lub ~20–50 zł/mies. (VPS + Docker)
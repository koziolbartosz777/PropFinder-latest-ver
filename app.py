import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")
app = Flask(__name__)


def get_db():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        database=os.environ.get("DB_NAME", "scraper_mieszkan"),
        user=os.environ.get("DB_USER", "admin"),
        password=os.environ.get("DB_PASSWORD", "admin123"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def build_query(f, sort_col, sort_dir, limit, offset):
    w = ["a.status = 'active'"]
    p = []

    if f.get("q"):
        w.append("(LOWER(a.tytul) LIKE %s OR LOWER(a.adres_pelny) LIKE %s OR LOWER(a.miasto) LIKE %s OR LOWER(a.dzielnica) LIKE %s)")
        q = f"%{f['q'].lower()}%"
        p += [q, q, q, q]

    if f.get("portal") and f["portal"] != "wszystkie":
        w.append("a.portal = %s")
        p.append(f["portal"])

    if f.get("cena_min"):
        w.append("ph.cena_pln >= %s")
        p.append(int(f["cena_min"]))

    if f.get("cena_max"):
        w.append("ph.cena_pln <= %s")
        p.append(int(f["cena_max"]))

    if f.get("cena_m2_min"):
        w.append("ph.cena_za_m2 >= %s")
        p.append(int(f["cena_m2_min"]))

    if f.get("cena_m2_max"):
        w.append("ph.cena_za_m2 <= %s")
        p.append(int(f["cena_m2_max"]))

    if f.get("metraz_min"):
        w.append("a.metraz >= %s")
        p.append(float(f["metraz_min"]))

    if f.get("metraz_max"):
        w.append("a.metraz <= %s")
        p.append(float(f["metraz_max"]))

    # Pokoje — wiele wartości np. "1,2,3"
    pokoje_vals = [x.strip() for x in f.get("pokoje", "").split(",") if x.strip().isdigit()]
    if pokoje_vals:
        placeholders = ",".join(["%s"] * len(pokoje_vals))
        w.append(f"a.pokoje IN ({placeholders})")
        p += [int(v) for v in pokoje_vals]

    if f.get("rynek") and f["rynek"] != "wszystkie":
        w.append("a.rynek = %s")
        p.append(f["rynek"])

    if f.get("rok_min"):
        w.append("a.rok_budowy >= %s")
        p.append(int(f["rok_min"]))

    if f.get("rok_max"):
        w.append("a.rok_budowy <= %s")
        p.append(int(f["rok_max"]))

    if f.get("pietro_min"):
        w.append("a.pietro ~ '^[0-9]+$' AND a.pietro::integer >= %s")
        p.append(int(f["pietro_min"]))

    if f.get("pietro_max"):
        w.append("a.pietro ~ '^[0-9]+$' AND a.pietro::integer <= %s")
        p.append(int(f["pietro_max"]))

    sort_map = {
        "cena_pln":   "ph.cena_pln",
        "metraz":     "a.metraz",
        "cena_za_m2": "ph.cena_za_m2",
        "last_seen":  "a.last_seen",
        "pokoje":     "a.pokoje",
        "rok_budowy": "a.rok_budowy",
    }
    sc = sort_map.get(sort_col, "a.last_seen")
    sd = "DESC" if sort_dir == "desc" else "ASC"
    where = " AND ".join(w)

    # Używamy LATERAL JOIN żeby mieć ceny dostępne w WHERE
    base = f"""
        FROM auctions a
        LEFT JOIN LATERAL (
            SELECT cena_pln, cena_za_m2 FROM price_history
            WHERE auction_id = a.auction_id
            ORDER BY timestamp DESC LIMIT 1
        ) ph ON true
        WHERE {where}
    """

    sql_count = f"SELECT COUNT(*) as total {base}"
    sql_data  = f"""
        SELECT a.*, ph.cena_pln, ph.cena_za_m2 {base}
        ORDER BY {sc} {sd} NULLS LAST, a.portal  -- dodatkowy sort żeby mieszać portale
        LIMIT %s OFFSET %s
    """
    return sql_count, sql_data, p, limit, offset


@app.route("/")
def index():
    f = {
        "q":          request.args.get("q", ""),
        "portal":     request.args.get("portal", "wszystkie"),
        "cena_min":   request.args.get("cena_min", ""),
        "cena_max":   request.args.get("cena_max", ""),
        "cena_m2_min":request.args.get("cena_m2_min", ""),
        "cena_m2_max":request.args.get("cena_m2_max", ""),
        "metraz_min": request.args.get("metraz_min", ""),
        "metraz_max": request.args.get("metraz_max", ""),
        "pokoje":     request.args.get("pokoje", ""),
        "rynek":      request.args.get("rynek", "wszystkie"),
        "rok_min":    request.args.get("rok_min", ""),
        "rok_max":    request.args.get("rok_max", ""),
        "pietro_min": request.args.get("pietro_min", ""),
        "pietro_max": request.args.get("pietro_max", ""),
    }
    sort_col   = request.args.get("sort", "last_seen")
    sort_dir   = request.args.get("kierunek", "desc")
    strona     = max(1, int(request.args.get("strona", 1)))
    na_stronie = 24
    offset     = (strona - 1) * na_stronie

    sql_count, sql_data, params, lim, off = build_query(f, sort_col, sort_dir, na_stronie, offset)

    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute(sql_count, params)
        lacznie = cur.fetchone()["total"]
        cur.execute(sql_data, params + [lim, off])
        mieszkania = cur.fetchall()
        conn.close()
    except Exception as e:
        import traceback; traceback.print_exc()
        mieszkania, lacznie = [], 0

    return render_template("index.html",
        mieszkania=mieszkania, filtry=f,
        sort=sort_col, kierunek=sort_dir,
        strona=strona, liczba_stron=max(1, -(-lacznie // na_stronie)),
        lacznie=lacznie,
    )


@app.route("/analiza")
def analiza():
    try:
        conn = get_db()
        cur  = conn.cursor()

        # Średnia cena za m² per dzielnica
        cur.execute("""
            SELECT a.dzielnica,
                   COUNT(*) as liczba,
                   ROUND(AVG(ph.cena_pln)) as avg_cena,
                   ROUND(AVG(ph.cena_za_m2)) as avg_m2,
                   ROUND(AVG(a.metraz), 1) as avg_metraz
            FROM auctions a
            LEFT JOIN LATERAL (
                SELECT cena_pln, cena_za_m2 FROM price_history
                WHERE auction_id = a.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) ph ON true
            WHERE a.status = 'active'
              AND a.dzielnica IS NOT NULL AND a.dzielnica != ''
              AND ph.cena_pln IS NOT NULL AND ph.cena_za_m2 IS NOT NULL
            GROUP BY a.dzielnica
            HAVING COUNT(*) >= 3
            ORDER BY avg_m2 DESC NULLS LAST
            LIMIT 20
        """)
        dzielnice = cur.fetchall()

        # Per portal
        cur.execute("""
            SELECT a.portal,
                   COUNT(*) as liczba,
                   ROUND(AVG(ph.cena_pln)) as avg_cena,
                   ROUND(AVG(ph.cena_za_m2)) as avg_m2
            FROM auctions a
            LEFT JOIN LATERAL (
                SELECT cena_pln, cena_za_m2 FROM price_history
                WHERE auction_id = a.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) ph ON true
            WHERE a.status = 'active' AND ph.cena_pln IS NOT NULL
            GROUP BY a.portal
            ORDER BY liczba DESC
        """)
        portale = cur.fetchall()

        # Rozkład cen
        cur.execute("""
            SELECT
                CASE
                    WHEN ph.cena_pln < 400000  THEN 'do 400 tys.'
                    WHEN ph.cena_pln < 600000  THEN '400–600 tys.'
                    WHEN ph.cena_pln < 800000  THEN '600–800 tys.'
                    WHEN ph.cena_pln < 1000000 THEN '800 tys.–1 mln'
                    WHEN ph.cena_pln < 1500000 THEN '1–1,5 mln'
                    ELSE 'powyżej 1,5 mln'
                END as przedział,
                COUNT(*) as liczba
            FROM auctions a
            LEFT JOIN LATERAL (
                SELECT cena_pln FROM price_history
                WHERE auction_id = a.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) ph ON true
            WHERE a.status = 'active' AND ph.cena_pln IS NOT NULL
            GROUP BY przedział
            ORDER BY MIN(ph.cena_pln)
        """)
        rozklad = cur.fetchall()

        conn.close()
    except Exception as e:
        import traceback; traceback.print_exc()
        dzielnice, portale, rozklad = [], [], []

    return render_template("analiza.html",
        dzielnice=dzielnice, portale=portale, rozklad=rozklad)


@app.route("/api/markers")
def markers():
    """Markery dla aktualnie widocznych ofert (przekazane jako auction_ids)."""
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT a.auction_id, a.tytul, a.metraz, a.pokoje,
                   a.adres_pelny, a.dzielnica, a.miasto,
                   a.zdjecie_url, a.url, a.portal,
                   ph.cena_pln
            FROM auctions a
            LEFT JOIN LATERAL (
                SELECT cena_pln FROM price_history
                WHERE auction_id = a.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) ph ON true
            WHERE a.status = 'active'
              AND (a.dzielnica IS NOT NULL OR a.adres_pelny IS NOT NULL)
            LIMIT 24
        """)
        rows = cur.fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify([])


if __name__ == "__main__":
    print("PropAgent — http://localhost:5000")
    app.run(debug=True, port=5000)
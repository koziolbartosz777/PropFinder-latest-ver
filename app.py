import os
import json
from decimal import Decimal
from datetime import datetime, date
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")
app = Flask(__name__)


def to_json_safe(rows):
    """Convert psycopg2 RealDictRow list to JSON-serialisable plain dicts."""
    out = []
    for row in rows:
        d = {}
        for k, v in dict(row).items():
            if isinstance(v, Decimal):
                d[k] = float(v)
            elif isinstance(v, (datetime, date)):
                d[k] = v.isoformat()
            else:
                d[k] = v
        out.append(d)
    return out


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

    # COUNT — prosta forma bez okna
    base_from = f"""
        FROM auctions a
        LEFT JOIN LATERAL (
            SELECT cena_pln,
                   COALESCE(cena_za_m2,
                     CASE WHEN cena_pln IS NOT NULL
                               AND a.metraz IS NOT NULL AND a.metraz > 0
                          THEN ROUND(cena_pln::numeric / a.metraz)
                     END
                   ) AS cena_za_m2
            FROM price_history
            WHERE auction_id = a.auction_id
            ORDER BY timestamp DESC LIMIT 1
        ) ph ON true
        WHERE {where}
    """
    sql_count = f"SELECT COUNT(*) as total {base_from}"

    # DATA — round-robin po portalu: sortujemy wg numeru wiersza wewnątrz każdego
    # portalu, dzięki czemu otodom/gratka/nro przeplatają się zamiast grupować.
    # score LATERAL is in the outer SELECT so it can reference ph from base_from.
    sql_data = f"""
        SELECT sub.*,
               score.tanszych,
               score.lacznie_blizniatow,
               ROUND(100.0 * score.tanszych / NULLIF(score.lacznie_blizniatow, 0)) AS pct_tanszych
        FROM (
            SELECT a.*, ph.cena_pln, ph.cena_za_m2,
                   GREATEST(0, ROUND(EXTRACT(EPOCH FROM (NOW() - a.first_seen))/86400))::integer AS dni_na_rynku,
                   ROW_NUMBER() OVER (
                       PARTITION BY a.portal
                       ORDER BY {sc} {sd} NULLS LAST
                   ) AS _rn
            {base_from}
        ) sub
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE ph2.cena_za_m2 < sub.cena_za_m2) AS tanszych,
                COUNT(*) AS lacznie_blizniatow
            FROM auctions a2
            LEFT JOIN LATERAL (
                SELECT COALESCE(cena_za_m2,
                         CASE WHEN cena_pln IS NOT NULL
                                   AND a2.metraz IS NOT NULL AND a2.metraz > 0
                              THEN ROUND(cena_pln::numeric / a2.metraz)
                         END
                       ) AS cena_za_m2
                FROM price_history
                WHERE auction_id = a2.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) ph2 ON true
            WHERE a2.status = 'active'
              AND a2.dzielnica = sub.dzielnica
              AND a2.pokoje = sub.pokoje
              AND a2.metraz BETWEEN sub.metraz * 0.8 AND sub.metraz * 1.2
              AND ph2.cena_za_m2 IS NOT NULL
              AND a2.auction_id != sub.auction_id
        ) score ON true
        ORDER BY sub._rn ASC, sub.portal ASC
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

    mieszkania_safe = to_json_safe(mieszkania)
    return render_template("index.html",
        mieszkania=mieszkania_safe,
        mieszkania_json=json.dumps(mieszkania_safe, ensure_ascii=False),
        filtry=f,
        sort=sort_col, kierunek=sort_dir,
        strona=strona, liczba_stron=max(1, -(-lacznie // na_stronie)),
        lacznie=lacznie,
    )


@app.route("/analiza")
def analiza():
    try:
        conn = get_db()
        cur  = conn.cursor()

        # a) Enhanced district stats with median
        cur.execute("""
            SELECT a.dzielnica,
                   COUNT(*) as liczba,
                   ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ph.cena_za_m2)) as mediana_m2,
                   ROUND(AVG(ph.cena_za_m2)) as avg_m2,
                   ROUND(AVG(a.metraz), 1) as avg_metraz,
                   ROUND(AVG(EXTRACT(EPOCH FROM (NOW() - a.first_seen))/86400)) as avg_dni_na_rynku
            FROM auctions a
            LEFT JOIN LATERAL (
                SELECT cena_pln,
                       COALESCE(cena_za_m2,
                         CASE WHEN cena_pln IS NOT NULL
                                   AND a.metraz IS NOT NULL AND a.metraz > 0
                              THEN ROUND(cena_pln::numeric / a.metraz)
                         END
                       ) AS cena_za_m2
                FROM price_history
                WHERE auction_id = a.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) ph ON true
            WHERE a.status = 'active'
              AND a.dzielnica IS NOT NULL AND a.dzielnica != ''
              AND ph.cena_za_m2 IS NOT NULL
            GROUP BY a.dzielnica
            HAVING COUNT(*) >= 3
            ORDER BY mediana_m2 DESC NULLS LAST
            LIMIT 20
        """)
        dzielnice = cur.fetchall()

        # b) Price brackets
        cur.execute("""
            SELECT
                CASE
                    WHEN ph.cena_pln < 400000  THEN 'do 400 tys.'
                    WHEN ph.cena_pln < 600000  THEN '400–600 tys.'
                    WHEN ph.cena_pln < 800000  THEN '600–800 tys.'
                    WHEN ph.cena_pln < 1000000 THEN '800 tys.–1 mln'
                    WHEN ph.cena_pln < 1500000 THEN '1–1,5 mln'
                    ELSE 'powyżej 1,5 mln'
                END as przedzial,
                COUNT(*) as liczba
            FROM auctions a
            LEFT JOIN LATERAL (
                SELECT cena_pln FROM price_history
                WHERE auction_id = a.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) ph ON true
            WHERE a.status = 'active' AND ph.cena_pln IS NOT NULL
            GROUP BY przedzial
            ORDER BY MIN(ph.cena_pln)
        """)
        rozklad = cur.fetchall()

        # c) Best value listings — cheapest vs similar twins
        cur.execute("""
            SELECT a.auction_id, a.url, a.portal, a.tytul, a.metraz, a.pokoje, a.dzielnica,
                   a.adres_pelny, a.zdjecie_url, a.rynek, a.rok_budowy,
                   ph.cena_pln, ph.cena_za_m2,
                   score.tanszych, score.lacznie_blizniatow,
                   ROUND(100.0 * score.tanszych / NULLIF(score.lacznie_blizniatow, 0)) as pct_tanszych
            FROM auctions a
            LEFT JOIN LATERAL (
                SELECT cena_pln,
                       COALESCE(cena_za_m2,
                         CASE WHEN cena_pln IS NOT NULL
                                   AND a.metraz IS NOT NULL AND a.metraz > 0
                              THEN ROUND(cena_pln::numeric / a.metraz)
                         END
                       ) AS cena_za_m2
                FROM price_history
                WHERE auction_id = a.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) ph ON true
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) FILTER (WHERE ph2.cena_za_m2 < ph.cena_za_m2) AS tanszych,
                    COUNT(*) AS lacznie_blizniatow
                FROM auctions a2
                LEFT JOIN LATERAL (
                    SELECT COALESCE(cena_za_m2,
                             CASE WHEN cena_pln IS NOT NULL
                                       AND a2.metraz IS NOT NULL AND a2.metraz > 0
                                  THEN ROUND(cena_pln::numeric / a2.metraz)
                             END
                           ) AS cena_za_m2
                    FROM price_history
                    WHERE auction_id = a2.auction_id
                    ORDER BY timestamp DESC LIMIT 1
                ) ph2 ON true
                WHERE a2.status = 'active'
                  AND a2.dzielnica = a.dzielnica
                  AND a2.pokoje = a.pokoje
                  AND a2.metraz BETWEEN a.metraz * 0.8 AND a.metraz * 1.2
                  AND ph2.cena_za_m2 IS NOT NULL
                  AND a2.auction_id != a.auction_id
            ) score ON true
            WHERE a.status = 'active'
              AND ph.cena_za_m2 IS NOT NULL
              AND score.lacznie_blizniatow >= 3
            ORDER BY pct_tanszych ASC NULLS LAST
            LIMIT 20
        """)
        best_value = cur.fetchall()

        # d) Per portal stats — cena_za_m2 obliczana z cena_pln/metraz gdy brak w bazie
        cur.execute("""
            SELECT a.portal,
                   COUNT(*) as liczba,
                   ROUND(AVG(ph.cena_pln)) as avg_cena,
                   ROUND(AVG(ph.cena_za_m2)) as avg_m2
            FROM auctions a
            LEFT JOIN LATERAL (
                SELECT cena_pln,
                       COALESCE(cena_za_m2,
                         CASE WHEN cena_pln IS NOT NULL
                                   AND a.metraz IS NOT NULL AND a.metraz > 0
                              THEN ROUND(cena_pln::numeric / a.metraz)
                         END
                       ) AS cena_za_m2
                FROM price_history
                WHERE auction_id = a.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) ph ON true
            WHERE a.status = 'active' AND ph.cena_pln IS NOT NULL
            GROUP BY a.portal
            ORDER BY liczba DESC
        """)
        portale = cur.fetchall()

        conn.close()
    except Exception as e:
        import traceback; traceback.print_exc()
        dzielnice, portale, rozklad, best_value = [], [], [], []

    return render_template("analiza.html",
        dzielnice=to_json_safe(dzielnice),
        portale=to_json_safe(portale),
        rozklad=to_json_safe(rozklad),
        best_value=to_json_safe(best_value),
    )


@app.route("/api/markers")
def markers():
    """Markery dla listy auction_ids z bieżącej strony (ids[]=... query params)."""
    ids = request.args.getlist("ids")
    if not ids:
        return jsonify([])
    try:
        conn = get_db()
        cur  = conn.cursor()
        ph   = ",".join(["%s"] * len(ids))
        cur.execute(f"""
            SELECT a.auction_id, a.tytul, a.metraz, a.pokoje,
                   a.adres_pelny, a.dzielnica, a.miasto,
                   a.zdjecie_url, a.url, a.portal,
                   pr.cena_pln
            FROM auctions a
            LEFT JOIN LATERAL (
                SELECT cena_pln FROM price_history
                WHERE auction_id = a.auction_id
                ORDER BY timestamp DESC LIMIT 1
            ) pr ON true
            WHERE a.auction_id IN ({ph})
        """, ids)
        rows = cur.fetchall()
        conn.close()
        return jsonify(to_json_safe(rows))
    except Exception:
        return jsonify([])


if __name__ == "__main__":
    print("PropAgent — http://localhost:5000")
    app.run(debug=True, port=5000)
// ── analiza.js — PropAgent market analysis page ────────────────────────────
// TRENDY (JSON array) is injected inline by the template before this script loads.

// ── TREND CHART — mediana zł/m² miesięcznie ───────────────────────────────
(function () {
  const months    = [...new Set(TRENDY.map(r => r.miesiac))].sort();
  const districts = [...new Set(TRENDY.map(r => r.dzielnica))];
  if (!months.length || !districts.length) return;

  const COLORS = ['#C0392B', '#1D4ED8', '#047857', '#D97706', '#7C3AED', '#0891B2'];

  const datasets = districts.map((d, i) => ({
    label: d,
    data: months.map(m => {
      const row = TRENDY.find(r => r.miesiac === m && r.dzielnica === d);
      return row ? row.mediana_m2 : null;
    }),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length] + '18',
    tension: 0.35,
    pointRadius: 4,
    pointHoverRadius: 6,
    spanGaps: true,
    fill: false,
  }));

  new Chart(document.getElementById('trendChart'), {
    type: 'line',
    data: { labels: months, datasets },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { font: { family: 'Inter', size: 12 } } },
        tooltip: {
          callbacks: {
            label: ctx => ctx.parsed.y != null
              ? `${ctx.dataset.label}: ${new Intl.NumberFormat('pl').format(ctx.parsed.y)} zł/m²`
              : null,
          }
        }
      },
      scales: {
        x: { grid: { color: '#F0F0EE' }, ticks: { font: { family: 'Inter', size: 11 } } },
        y: {
          grid: { color: '#F0F0EE' },
          ticks: {
            font: { family: 'Inter', size: 11 },
            callback: v => new Intl.NumberFormat('pl').format(v) + ' zł'
          }
        }
      }
    }
  });
})();

// ── MODAL — Historia cen konkretnej oferty ─────────────────────────────────
let phChartInstance = null;

function openPriceHistory(auctionId, title) {
  document.getElementById('ph-modal-title').textContent = 'Historia cen';
  document.getElementById('ph-modal-sub').textContent   = title || '';
  document.getElementById('ph-empty').style.display     = 'none';
  document.getElementById('ph-chart-wrap').style.display = 'block';
  document.getElementById('ph-modal-bg').classList.add('on');

  if (phChartInstance) { phChartInstance.destroy(); phChartInstance = null; }

  fetch('/api/price_history/' + encodeURIComponent(auctionId))
    .then(r => r.json())
    .then(data => {
      if (!data.length) {
        document.getElementById('ph-chart-wrap').style.display = 'none';
        document.getElementById('ph-empty').style.display      = 'block';
        return;
      }
      const labels = data.map(r => r.timestamp.slice(0, 10));
      phChartInstance = new Chart(document.getElementById('phChart'), {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Cena (zł)',
              data: data.map(r => r.cena_pln),
              borderColor: '#C0392B', backgroundColor: '#C0392B18',
              tension: 0.2, pointRadius: 5, fill: true, yAxisID: 'yCena',
            },
            {
              label: 'Cena za m² (zł)',
              data: data.map(r => r.cena_za_m2),
              borderColor: '#1D4ED8', backgroundColor: 'transparent',
              tension: 0.2, pointRadius: 4, borderDash: [5, 3], yAxisID: 'yM2',
            },
          ]
        },
        options: {
          responsive: true,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { labels: { font: { family: 'Inter', size: 12 } } },
            tooltip: {
              callbacks: {
                label: ctx => ctx.parsed.y != null
                  ? `${ctx.dataset.label}: ${new Intl.NumberFormat('pl').format(ctx.parsed.y)} zł`
                  : null
              }
            }
          },
          scales: {
            yCena: {
              type: 'linear', position: 'left',
              ticks: { font: { family: 'Inter', size: 11 }, callback: v => new Intl.NumberFormat('pl').format(v) + ' zł' },
              grid: { color: '#F0F0EE' },
            },
            yM2: {
              type: 'linear', position: 'right', grid: { drawOnChartArea: false },
              ticks: { font: { family: 'Inter', size: 11 }, callback: v => new Intl.NumberFormat('pl').format(v) + ' zł' },
            },
          }
        }
      });
    })
    .catch(() => {
      document.getElementById('ph-chart-wrap').style.display = 'none';
      document.getElementById('ph-empty').style.display      = 'block';
    });
}

function closePriceHistory(event) {
  // Zamknij jeśli kliknięto tło modalu (nie jego zawartość) lub brak eventu
  if (event && event.target !== document.getElementById('ph-modal-bg')) return;
  document.getElementById('ph-modal-bg').classList.remove('on');
  if (phChartInstance) { phChartInstance.destroy(); phChartInstance = null; }
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.getElementById('ph-modal-bg').classList.remove('on');
    if (phChartInstance) { phChartInstance.destroy(); phChartInstance = null; }
  }
});

// ── DISTRICT HEAT MAP ──────────────────────────────────────────────────────
let mapInstance  = null;
let mapVisible   = false;
let mapGeoLayer  = null;

function toggleDistrictMap() {
  const container = document.getElementById('district-map-container');
  const btn       = document.getElementById('map-toggle-btn');

  if (mapVisible) {
    container.style.display = 'none';
    mapVisible = false;
    btn.textContent = '🗺️ Mapa cieplna';
    btn.classList.remove('active');
    return;
  }

  container.style.display = 'block';
  mapVisible = true;
  btn.textContent = '✕ Ukryj mapę';
  btn.classList.add('active');

  if (mapInstance) {
    // already loaded — just resize in case container was hidden
    setTimeout(() => mapInstance.invalidateSize(), 120);
    return;
  }

  initDistrictMap();
}

function retryMap() {
  if (mapInstance) { mapInstance.remove(); mapInstance = null; }
  document.getElementById('map-error').style.display = 'none';
  initDistrictMap();
}

async function initDistrictMap() {
  const loadingEl = document.getElementById('map-loading');
  const errorEl   = document.getElementById('map-error');

  loadingEl.style.display = 'flex';
  errorEl.style.display   = 'none';

  try {
    // 1. Init Leaflet map
    mapInstance = L.map('district-map', { zoomControl: true }).setView([50.055, 19.970], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(mapInstance);

    // 2. Fetch Kraków district polygons from Overpass API
    const query = `[out:json][timeout:60];
area["name"="Kraków"]["wikidata"="Q31487"]->.krakow;
(
  relation["boundary"="administrative"]["admin_level"="9"](area.krakow);
);
out body;
>;
out skel qt;`;

    const resp = await fetch('https://overpass-api.de/api/interpreter', {
      method: 'POST',
      body:   'data=' + encodeURIComponent(query),
    });
    if (!resp.ok) throw new Error('Overpass HTTP ' + resp.status);

    const osmData = await resp.json();
    if (!osmData.elements || osmData.elements.length === 0)
      throw new Error('Brak danych z Overpass');

    const geojson = osmtogeojson(osmData);

    // 3. Build price lookup from backend data
    const priceMap = {};
    DZIELNICE.forEach(d => {
      if (d.dzielnica && d.mediana_m2 != null) priceMap[d.dzielnica] = +d.mediana_m2;
    });

    const prices   = Object.values(priceMap);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);

    // 4. Normalize OSM names to match OFFICIAL_DISTRICTS keys
    function normOSM(name) {
      if (!name) return '';
      return name
        .replace(/^Dzielnica [IVXLC]+ /, '')
        .replace(/ Kraków$/, '')
        .trim();
    }

    // 5. Color scale: green (cheap) → yellow → red (expensive)
    function getColor(price) {
      if (price == null) return '#d4d4d4';
      const pct = (price - minPrice) / ((maxPrice - minPrice) || 1);
      const hue = Math.round(120 - pct * 120);   // 120=green … 0=red
      return `hsl(${hue}, 62%, 52%)`;
    }

    // 6. Render GeoJSON layer
    mapGeoLayer = L.geoJSON(geojson, {
      filter: f =>
        f.geometry &&
        (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon') &&
        f.properties && f.properties.name,

      style: f => {
        const price = priceMap[normOSM(f.properties.name)];
        return {
          fillColor:   getColor(price),
          fillOpacity: 0.72,
          weight:      1.5,
          color:       'rgba(0,0,0,0.25)',
        };
      },

      onEachFeature: (f, lyr) => {
        const name     = normOSM(f.properties.name);
        const rawName  = f.properties.name;
        const price    = priceMap[name];
        const priceStr = price != null
          ? `<strong>${new Intl.NumberFormat('pl-PL').format(price)} zł/m²</strong>`
          : '<span style="color:#999">brak danych</span>';

        lyr.bindTooltip(
          `<div style="font-family:Inter,sans-serif;font-size:13px;line-height:1.6;padding:2px 4px">
             <strong>${rawName}</strong><br>${priceStr}
           </div>`,
          { sticky: true, direction: 'top', offset: [0, -4] }
        );

        lyr.on({
          mouseover: e => e.target.setStyle({ weight: 2.5, fillOpacity: 0.9 }),
          mouseout:  e => mapGeoLayer.resetStyle(e.target),
        });
      },
    }).addTo(mapInstance);

    mapInstance.fitBounds(mapGeoLayer.getBounds(), { padding: [16, 16] });

    // 7. Legend
    _addMapLegend(minPrice, maxPrice);

  } catch (err) {
    console.error('Heat map error:', err);
    if (mapInstance) { mapInstance.remove(); mapInstance = null; }
    errorEl.style.display = 'flex';
  } finally {
    loadingEl.style.display = 'none';
  }
}

function _addMapLegend(minPrice, maxPrice) {
  const legend = L.control({ position: 'bottomright' });
  legend.onAdd = function () {
    const div   = L.DomUtil.create('div', 'map-legend');
    const steps = 5;
    let rows    = '';
    for (let i = 0; i <= steps; i++) {
      const pct   = i / steps;
      const price = Math.round(minPrice + pct * (maxPrice - minPrice));
      const hue   = Math.round(120 - pct * 120);
      rows += `
        <div class="legend-item">
          <span class="legend-swatch" style="background:hsl(${hue},62%,52%)"></span>
          <span>${new Intl.NumberFormat('pl-PL').format(price)} zł</span>
        </div>`;
    }
    div.innerHTML = `<div class="legend-title">Mediana zł/m²</div>${rows}`;
    return div;
  };
  legend.addTo(mapInstance);
}

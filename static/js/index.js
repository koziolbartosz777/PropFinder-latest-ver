// ── index.js — PropAgent main listings page ────────────────────────────────
// PAGE_LISTINGS is injected inline by the template before this script loads.

// ── PORTAL ─────────────────────────────────────────────────────────────────
function setPortal(v) {
  document.getElementById('portal-val').value = v;
  document.querySelectorAll('.portal-btn').forEach(b => {
    b.className = 'portal-btn';
    const label = b.textContent.trim().toLowerCase();
    const pid = { 'wszystkie': 'wszystkie', 'otodom': 'otodom', 'gratka': 'gratka', 'nro': 'nro' }[label] || '';
    if (pid === v) b.classList.add('on-' + v);
  });
}

// ── POKOJE — multi-select ───────────────────────────────────────────────────
let selRooms = new Set(
  (document.getElementById('room-val').value || '').split(',').filter(x => x.trim())
);
function toggleRoom(v) {
  selRooms.has(v) ? selRooms.delete(v) : selRooms.add(v);
  document.getElementById('room-val').value = [...selRooms].join(',');
  document.querySelectorAll('.room-btn').forEach(b => {
    b.classList.toggle('on', selRooms.has(b.textContent.trim().replace('+', '')));
  });
}

// ── WIDOK (grid / list) ────────────────────────────────────────────────────
function setView(v) {
  const wrap = document.getElementById('cards');
  if (v === 'list') {
    wrap.className = 'list';
    document.querySelectorAll('.card') .forEach(c => c.style.display = 'none');
    document.querySelectorAll('.lcard').forEach(c => c.style.display = 'flex');
    document.getElementById('vl').classList.add('on');
    document.getElementById('vg').classList.remove('on');
  } else {
    wrap.className = 'grid';
    document.querySelectorAll('.card') .forEach(c => c.style.display = 'flex');
    document.querySelectorAll('.lcard').forEach(c => c.style.display = 'none');
    document.getElementById('vg').classList.add('on');
    document.getElementById('vl').classList.remove('on');
  }
  try { localStorage.setItem('propView', v); } catch {}
}

// Przywróć widok po przeładowaniu
(function () {
  try { if (localStorage.getItem('propView') === 'list') setView('list'); } catch {}
})();

// ── SCORE TOGGLE ───────────────────────────────────────────────────────────
function toggleScore(on) {
  document.querySelectorAll('.bpct-badge').forEach(b => {
    b.style.display = on ? '' : 'none';
  });
  try { localStorage.setItem('propScore', on ? '1' : '0'); } catch {}
}

(function () {
  try {
    const saved = localStorage.getItem('propScore');
    const on = saved !== '0';
    const chk = document.getElementById('score-toggle');
    if (chk) chk.checked = on;
    if (!on) document.querySelectorAll('.bpct-badge').forEach(b => b.style.display = 'none');
  } catch {}
})();

// ── MAPA ───────────────────────────────────────────────────────────────────
const PORTAL_COLORS = { otodom: '#C0392B', gratka: '#1D4ED8', nro: '#047857' };
let mapObj     = null;
let mapVisible = false;
const markerById = {};
const clusters   = {};

function geoRead(addr) {
  try { const v = localStorage.getItem('geo:' + addr); return v ? JSON.parse(v) : null; } catch { return null; }
}
function geoWrite(addr, coords) {
  try { localStorage.setItem('geo:' + addr, JSON.stringify(coords)); } catch {}
}

function makeIcon(color, size = 10, opacity = 1) {
  return L.divIcon({
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 1px 5px rgba(0,0,0,.35);opacity:${opacity};transition:all .15s"></div>`,
    className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
  });
}

function buildPopup(listings) {
  const multi = listings.length > 1;
  const parts = listings.map(m => {
    const c    = PORTAL_COLORS[m.portal] || '#888';
    const cena = m.cena_pln ? new Intl.NumberFormat('pl').format(m.cena_pln) + ' zł' : '—';
    const meta = [m.metraz ? Math.round(m.metraz) + ' m²' : null, m.pokoje ? m.pokoje + ' pok.' : null].filter(Boolean).join(' · ');
    const img  = m.zdjecie_url ? `<img src="${m.zdjecie_url}" style="width:100%;height:72px;object-fit:cover;border-radius:5px;margin-bottom:5px">` : '';
    return `<div style="border-top:${multi ? '1px solid #eee' : 'none'};padding-top:${multi ? '8px' : '0'}">
      ${img}
      <strong style="font-size:13px">${cena}</strong>
      <span style="margin-left:5px;font-size:9px;font-weight:700;text-transform:uppercase;background:${c};color:#fff;padding:1px 5px;border-radius:3px">${m.portal}</span><br>
      <span style="font-size:11px;color:#555">${meta}</span><br>
      ${m.adres_pelny ? `<span style="font-size:10.5px;color:#888">${m.adres_pelny}</span><br>` : ''}
      <div style="display:flex;gap:8px;align-items:center;margin-top:5px;flex-wrap:wrap">
        <a href="${m.url}" target="_blank" style="font-size:11px;color:${c};font-weight:600">Otwórz ofertę →</a>
        <button onclick="scrollToCard('${m.auction_id}')"
          style="font-size:10.5px;font-weight:600;padding:3px 8px;border-radius:5px;border:1.5px solid #059669;color:#059669;background:#F0FDF4;cursor:pointer;font-family:Inter,sans-serif;white-space:nowrap">
          ↓ Przenieś do oferty
        </button>
      </div>
    </div>`;
  });
  const header = multi ? `<div style="font-size:11.5px;font-weight:700;color:#111;margin-bottom:6px">${listings.length} oferty w tym miejscu</div>` : '';
  return `<div style="font-family:Inter,sans-serif;min-width:170px;max-width:220px;max-height:320px;overflow-y:auto">${header}${parts.join('')}</div>`;
}

function addOrMergeMarker(m, lat, lng) {
  const key = lat.toFixed(4) + ',' + lng.toFixed(4);
  if (clusters[key]) {
    clusters[key].listings.push(m);
    const cl = clusters[key];
    cl.marker.setPopupContent(buildPopup(cl.listings));
    cl.marker.setIcon(makeIcon('#555', 13));
  } else {
    const c  = PORTAL_COLORS[m.portal] || '#888';
    const mk = L.marker([lat, lng], { icon: makeIcon(c, 10) }).addTo(mapObj)
                .bindPopup(buildPopup([m]), { maxWidth: 240 });
    clusters[key] = { marker: mk, listings: [m] };
    markerById[m.auction_id] = mk;
    mk.on('popupopen',  () => highlightCards(clusters[key].listings, true));
    mk.on('popupclose', () => highlightCards(clusters[key].listings, false));
  }
  if (!markerById[m.auction_id]) markerById[m.auction_id] = clusters[key].marker;
}

function geocodeOne(m, delay) {
  setTimeout(() => {
    const addr   = (m.adres_pelny || m.dzielnica || '') + ', Kraków, Poland';
    const cached = geoRead(addr);
    if (cached) { addOrMergeMarker(m, cached.lat, cached.lng); return; }
    fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(addr)}&format=json&limit=1`)
      .then(r => r.json()).then(res => {
        if (!res.length) return;
        const lat = +res[0].lat, lng = +res[0].lon;
        geoWrite(addr, { lat, lng });
        addOrMergeMarker(m, lat, lng);
      }).catch(() => {});
  }, delay);
}

function initMap() {
  mapObj = L.map('map').setView([50.0614, 19.9366], 12);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CARTO', maxZoom: 19
  }).addTo(mapObj);
  let networkIdx = 0;
  PAGE_LISTINGS.forEach(m => {
    const addr = (m.adres_pelny || m.dzielnica || '') + ', Kraków, Poland';
    if (geoRead(addr)) { geocodeOne(m, 0); }
    else { geocodeOne(m, networkIdx * 1150); networkIdx++; }
  });
}

function toggleMap() {
  const wrap = document.getElementById('map-wrap');
  const btn  = document.getElementById('map-btn');
  mapVisible = !mapVisible;
  wrap.classList.toggle('on', mapVisible);
  btn.classList.toggle('on', mapVisible);
  if (mapVisible && !mapObj) initMap();
  if (mapVisible && mapObj) setTimeout(() => mapObj.invalidateSize(), 50);
}

function highlightCards(listings, on) {
  listings.forEach(m => {
    document.querySelectorAll(`[data-id="${m.auction_id}"]`).forEach(el => el.classList.toggle('map-active', on));
  });
}

function scrollToCard(id) {
  document.querySelectorAll(`[data-id="${id}"]`).forEach(el => {
    if (el.offsetParent === null) return;
    el.classList.add('map-active');
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    clearTimeout(el._mapTimer);
    el._mapTimer = setTimeout(() => el.classList.remove('map-active'), 3000);
  });
}

function showOnMap(id, event) {
  event.stopPropagation();
  if (!mapVisible) toggleMap();
  const mapWrap = document.getElementById('map-wrap');
  setTimeout(() => mapWrap.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
  function tryOpen(attempts) {
    const mk = markerById[id];
    if (mk) { mapObj.panTo(mk.getLatLng(), { animate: true }); setTimeout(() => mk.openPopup(), 300); return; }
    if (attempts > 0) setTimeout(() => tryOpen(attempts - 1), 600);
  }
  setTimeout(() => tryOpen(8), mapObj ? 0 : 350);
}

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

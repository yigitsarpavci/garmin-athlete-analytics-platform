/* Garmin Athlete IQ — Editorial Telemetry Charts (Dark Mode Only) */
function getChartThemeColors() {
  return {
    isDark: true,
    text: '#ADA698',
    grid: 'rgba(243, 239, 230, 0.08)',
    primary: '#E85B35',
    secondary: '#4AB984',
    accent: '#F3EFE6',
    barBg: 'rgba(232, 91, 53, 0.28)'
  };
}


function updateChartThemes(isDark) {
  const theme = getChartThemeColors();
  Object.values(chartInstances).forEach(chart => {
    if (!chart || !chart.options) return;
    if (chart.options.scales) {
      Object.values(chart.options.scales).forEach(scale => {
        if (!scale) return;
        if (scale.ticks) scale.ticks.color = theme.text;
        if (scale.grid) scale.grid.color = theme.grid;
        if (scale.title) scale.title.color = theme.text;
      });
    }
    if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
      chart.options.plugins.legend.labels.color = theme.text;
    }
    if (chart.data && chart.data.datasets) {
      if (chart.data.datasets[0]) {
        if (chart.data.datasets[0].type === 'bar' || chart.config.type === 'bar') {
          chart.data.datasets[0].backgroundColor = theme.barBg;
        } else {
          chart.data.datasets[0].borderColor = theme.primary;
        }
      }
      if (chart.data.datasets[1]) {
        chart.data.datasets[1].borderColor = theme.secondary;
      }
    }
    chart.update();
  });
}


let chartsLoadingPromise = null;

async function renderCharts(forceRefresh = false) {
  if (!document.getElementById('chart-hrv')) return;
  if (!forceRefresh && chartInstances.hrv) return;
  if (chartsLoadingPromise) return chartsLoadingPromise;
  chartsLoadingPromise = (async () => {
    try {
      const res = await fetch('/api/charts');
      const c = await res.json();
      const runsTitleEl = document.getElementById('analyticsRunsTitle');
      if (runsTitleEl && Array.isArray(c.runs)) {
        runsTitleEl.textContent = `${c.runs.length} Koşuda Tempo ve Kadans Gelişimi`;
      }
      const theme = getChartThemeColors();
      const fontMeta = { family: '"IBM Plex Mono", monospace', size: 10 };

      ['chart-hrv', 'chart-runs', 'chart-bb', 'chart-sleep'].forEach(id => {
        const el = document.getElementById(id);
        const existing = el && window.Chart && Chart.getChart ? Chart.getChart(el) : null;
        if (existing) existing.destroy();
        chartInstances = {};
      });

      // 1. HRV & RHR
      chartInstances.hrv = new Chart(document.getElementById('chart-hrv'), {
        type: 'line',
        data: {
          labels: c.dates,
          datasets: [
            { label: 'Gece HRV (ms)', data: c.hrv, borderColor: theme.primary, borderWidth: 2, pointRadius: 0.5, tension: 0.25, yAxisID: 'y' },
            { label: 'Dinlenik Nabız (bpm)', data: c.rhr, borderColor: theme.secondary, borderDash: [4, 4], borderWidth: 1.5, pointRadius: 0.5, tension: 0.25, yAxisID: 'y1' }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            y: { min: 20, max: 70, ticks: { color: theme.text, font: fontMeta }, grid: { color: theme.grid }, title: { display: true, text: 'HRV (ms)', color: theme.text, font: fontMeta } },
            y1: { min: 40, max: 70, position: 'right', ticks: { color: theme.text, font: fontMeta }, grid: { drawOnChartArea: false }, title: { display: true, text: 'RHR (bpm)', color: theme.text, font: fontMeta } },
            x: { ticks: { maxTicksLimit: 10, color: theme.text, font: fontMeta }, grid: { color: theme.grid } }
          },
          plugins: { legend: { labels: { boxWidth: 10, color: theme.text, font: fontMeta } } }
        }
      });

      // 2. Koşu Temposu ve Kadans
      chartInstances.runs = new Chart(document.getElementById('chart-runs'), {
        type: 'line',
        data: {
          labels: c.runs.map(r => r.date),
          datasets: [
            { label: 'Tempo (dk/km)', data: c.runs.map(r => r.pace_sec ? (r.pace_sec / 60) : null), borderColor: theme.primary, borderWidth: 2, pointRadius: 2.5, yAxisID: 'y' },
            { label: 'Kadans (adım/dk)', data: c.runs.map(r => r.cadence), borderColor: theme.secondary, borderDash: [4, 4], borderWidth: 1.5, pointRadius: 2, yAxisID: 'y1' }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            y: { reverse: true, min: 5.0, max: 9.0, ticks: { color: theme.text, font: fontMeta }, grid: { color: theme.grid }, title: { display: true, text: 'Tempo (dk/km)', color: theme.text, font: fontMeta } },
            y1: { min: 120, max: 180, position: 'right', ticks: { color: theme.text, font: fontMeta }, grid: { drawOnChartArea: false }, title: { display: true, text: 'Kadans', color: theme.text, font: fontMeta } },
            x: { ticks: { color: theme.text, font: fontMeta }, grid: { color: theme.grid } }
          },
          plugins: { legend: { labels: { boxWidth: 10, color: theme.text, font: fontMeta } } }
        }
      });

      // 3. Body Battery ve Stres
      chartInstances.bb = new Chart(document.getElementById('chart-bb'), {
        type: 'line',
        data: {
          labels: c.dates,
          datasets: [
            { label: 'Sabah Body Battery', data: c.bb_wake, borderColor: theme.primary, borderWidth: 2, pointRadius: 0.5, tension: 0.25 },
            { label: 'Günlük Stres Puanı', data: c.stress, borderColor: theme.secondary, borderDash: [4, 4], borderWidth: 1.5, pointRadius: 0.5, tension: 0.25 }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            y: { min: 0, max: 100, ticks: { color: theme.text, font: fontMeta }, grid: { color: theme.grid } },
            x: { ticks: { maxTicksLimit: 10, color: theme.text, font: fontMeta }, grid: { color: theme.grid } }
          },
          plugins: { legend: { labels: { boxWidth: 10, color: theme.text, font: fontMeta } } }
        }
      });

      // 4. Uyku ve Uyku Puanı
      chartInstances.sleep = new Chart(document.getElementById('chart-sleep'), {
        type: 'bar',
        data: {
          labels: c.dates,
          datasets: [
            { label: 'Uyku Süresi (Saat)', data: c.sleep_durations, backgroundColor: theme.barBg, borderRadius: 2, yAxisID: 'y' },
            { label: 'Uyku Skoru (0-100)', data: c.sleep_scores, type: 'line', borderColor: theme.primary, borderWidth: 2, pointRadius: 0.5, yAxisID: 'y1' }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            y: { min: 0, max: 10, ticks: { color: theme.text, font: fontMeta }, grid: { color: theme.grid }, title: { display: true, text: 'Saat', color: theme.text, font: fontMeta } },
            y1: { min: 0, max: 100, position: 'right', ticks: { color: theme.text, font: fontMeta }, grid: { drawOnChartArea: false }, title: { display: true, text: 'Puan', color: theme.text, font: fontMeta } },
            x: { ticks: { maxTicksLimit: 10, color: theme.text, font: fontMeta }, grid: { color: theme.grid } }
          },
          plugins: { legend: { labels: { boxWidth: 10, color: theme.text, font: fontMeta } } }
        }
      });

    } catch (err) {
      console.error(err);
    } finally {
      chartsLoadingPromise = null;
    }
  })();
  return chartsLoadingPromise;
}

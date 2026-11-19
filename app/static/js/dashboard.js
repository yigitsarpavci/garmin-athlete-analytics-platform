/* Garmin Athlete IQ — Overview, Sports Guidance, Training Load & Dynamic Activity Log */

function getDynamicSportLabel(sport, sportTr = null) {
  if (sportTr) return sportTr;
  const spNames = {
    running: 'Koşu',
    sailing_v2: 'Yelken',
    strength_training: 'Kuvvet',
    basketball: 'Basketbol',
    hiking: 'Doğa Yürüyüşü',
    rowing_v2: 'Kürek',
    walking: 'Yürüyüş',
    resort_skiing: 'Kayak',
    skiing: 'Kayak',
    swimming: 'Yüzme',
    cycling: 'Bisiklet',
    tennis: 'Tenis',
    yoga: 'Yoga'
  };
  if (spNames[sport]) return spNames[sport];
  return String(sport || 'Branş')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function formatTrInt(val) {
  if (val === undefined || val === null || Number.isNaN(Number(val))) return '--';
  return Math.round(Number(val)).toLocaleString('tr-TR');
}

function formatHm(hoursFloat) {
  if (hoursFloat === undefined || hoursFloat === null || Number.isNaN(Number(hoursFloat))) return '--';
  const totalMin = Math.round(Number(hoursFloat) * 60);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return `${h}s ${String(m).padStart(2, '0')}dk`;
}

function _piecewiseGaugePct(val, breaks, segments) {
  const num = Number(val);
  if (Number.isNaN(num)) return 0;
  const totalFlex = segments.reduce((acc, s) => acc + (s.flex ?? 1), 0) || 1;
  let startPct = 0;
  for (let i = 0; i < segments.length; i++) {
    const segPct = ((segments[i].flex ?? 1) / totalFlex) * 100;
    const lo = breaks[i];
    const hi = breaks[i + 1];
    if (num <= hi || i === segments.length - 1) {
      const ratio = hi > lo ? Math.max(0, Math.min(1, (num - lo) / (hi - lo))) : 0;
      return startPct + ratio * segPct;
    }
    startPct += segPct;
  }
  return 0;
}

function _renderGarminGauge(containerId, segments, activeIdx, markerPct, leftLbl, midLbl, rightLbl, secondMarkerPct = null, secondTitle = '') {
  const el = document.getElementById(containerId);
  if (!el) return;
  const clamped = Math.max(3, Math.min(97, Number(markerPct) || 0));
  el.innerHTML = `
    <div class="garmin-gauge">
      <div class="garmin-gauge-track">
        ${segments.map((s, idx) => `<div class="garmin-seg ${s.cls} ${idx === activeIdx ? 'active' : ''}" style="flex:${s.flex ?? 1}"></div>`).join('')}
        ${secondMarkerPct === null ? '' : `<span class="garmin-gauge-pin garmin-gauge-pin-alt" style="left:${Math.max(3, Math.min(97, Number(secondMarkerPct) || 0))}%" title="${escapeHtml(secondTitle)}"></span>`}
        <span class="garmin-gauge-pin" style="left:${clamped}%"></span>
      </div>
      <div class="garmin-gauge-scale">
        <span>${escapeHtml(leftLbl)}</span>
        ${midLbl ? `<span>${escapeHtml(midLbl)}</span>` : ''}
        <span>${escapeHtml(rightLbl)}</span>
      </div>
    </div>
  `;
}

function renderFirstScreenTelemetryCards(data, vo2, curLoad, acuteVal, chronicVal, acwrNum, tMin, tMax) {
  const setText = (id, txt) => {
    const el = document.getElementById(id);
    if (el) el.textContent = txt;
  };
  const fmtDec = (val, dec = 1) => (
    val === undefined || val === null || Number.isNaN(Number(val))
      ? '--'
      : Number(val).toFixed(dec).replace('.', ',')
  );

  const formatTrDateShort = (iso) => {
    if (!iso || typeof iso !== 'string' || iso.length < 10) return '--';
    const months = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
    const parts = iso.slice(0, 10).split('-');
    if (parts.length !== 3) return iso;
    const mIdx = Number(parts[1]) - 1;
    const day = Number(parts[2]);
    return `${day} ${months[mIdx] || parts[1]} ${parts[0]}`;
  };
  setText('firstScreenDateBadge', `Son Güncelleme: ${formatTrDateShort(data.date)}${data.is_partial_day ? ' · Bugün' : ''}`);

  // 01. HRV (Garmin kişisel baseline aralığına göre son gün gauge barı)
  const hrvVal = Number(data.overnight_hrv ?? data.hrv_7d ?? 0);
  const hrvBase = Number(data.hrv_7d ?? data.overnight_hrv ?? 0);
  const hrvHasBase = data.hrv_baseline_low != null && data.hrv_baseline_high != null;
  const hrvLow = hrvHasBase ? Number(data.hrv_baseline_low) : Math.round(hrvBase * 0.8);
  const hrvHigh = hrvHasBase ? Number(data.hrv_baseline_high) : Math.round(hrvBase * 1.25);
  const hrvStLower = String(data.hrv_status || '').toLowerCase();
  const hrvAvgColor = (hrvStLower.includes('zayıf') || hrvStLower.includes('poor') || hrvBase < hrvLow - 6)
    ? '#C96A5B'
    : ((hrvStLower.includes('düşük') || hrvStLower.includes('low') || hrvBase < hrvLow) ? '#C99A49' : '#5E8F74');
  setText('fs-hrv-val', `${data.overnight_hrv !== undefined ? Math.round(data.overnight_hrv) : '--'} ms`);
  const hrvSubEl = document.getElementById('fs-hrv-sub');
  if (hrvSubEl) {
    hrvSubEl.innerHTML = `<span class="inline-flex items-center gap-1"><span style="width:6px;height:6px;border-radius:9999px;background:${hrvAvgColor};display:inline-block" aria-hidden="true"></span><span>7G Ort: <strong style="color:${hrvAvgColor}">${escapeHtml(String(data.hrv_7d ?? '--'))} ms</strong></span></span> ${hrvHasBase ? ` · Baz: ${hrvLow}–${hrvHigh}` : ''} · RHR: ${escapeHtml(String(data.resting_hr ?? '--'))}`;
  }
  const hrvSegs = [{ cls: 'seg-red', flex: 1 }, { cls: 'seg-amber', flex: 1 }, { cls: 'seg-green', flex: 1.8 }, { cls: 'seg-amber', flex: 0.8 }];
  const hrvThresholds = [Math.max(15, hrvLow - 16), Math.max(20, hrvLow - 7), hrvLow, hrvHigh, hrvHigh + 10];
  const hrvPct = _piecewiseGaugePct(hrvVal, hrvThresholds, hrvSegs);
  const hrvActive = hrvVal < hrvThresholds[1]
    ? 0
    : (hrvVal < hrvThresholds[2] ? 1 : (hrvVal <= hrvThresholds[3] ? 2 : 3));
  _renderGarminGauge('fs-hrv-bar', hrvSegs, hrvActive, hrvPct, 'Zayıf', 'Dengeli', 'Yüksek');

  // 02. VO2 Max (+ Trend Yönü)
  const vo2Num = Number(vo2) || 0;
  const vo2Segs = [{ cls: 'seg-red' }, { cls: 'seg-amber' }, { cls: 'seg-green' }, { cls: 'seg-blue' }, { cls: 'seg-purple' }];
  const vo2Pct = _piecewiseGaugePct(vo2Num, [34, 38, 44, 50, 55, 60], vo2Segs);
  const vo2Active = vo2Num < 38 ? 0 : (vo2Num < 44 ? 1 : (vo2Num < 50 ? 2 : (vo2Num < 55 ? 3 : 4)));
  const vt = data.vo2max_trend || {};
  const vtArrow = vt.arrow || '→';
  const vtLabel = vt.label || 'Sabit';
  const vtDelta = vt.delta !== undefined && vt.delta !== null
    ? `${Number(vt.delta) > 0 ? '+' : ''}${fmtDec(vt.delta, 1)}`
    : '0,0';
  setText('fs-vo2-val', fmtDec(vo2, 1));
  setText('fs-vo2-sub', `Trend: ${vtArrow} ${vtDelta} (${fmtDec(vt.prev ?? vo2Num, 1)}→${fmtDec(vo2Num, 1)})`);
  _renderGarminGauge('fs-vo2-bar', vo2Segs, vo2Active, vo2Pct, 'Zayıf', 'İyi', 'Üstün');

  // 03. Sleep Score
  const sc = data.sleep_score !== undefined ? Math.round(data.sleep_score) : null;
  const scNum = Number(sc ?? 0);
  const scSegs = [{ cls: 'seg-red', flex: 1.5 }, { cls: 'seg-amber', flex: 1.3 }, { cls: 'seg-green', flex: 1.2 }, { cls: 'seg-blue', flex: 1 }];
  const scPct = _piecewiseGaugePct(scNum, [0, 60, 80, 90, 100], scSegs);
  const scActive = scNum < 60 ? 0 : (scNum < 80 ? 1 : (scNum < 90 ? 2 : 3));
  setText('fs-sleepscore-val', sc !== null ? `${sc} / 100` : '-- / 100');
  setText('fs-sleepscore-sub', `7G Ort: ${fmtDec(data.sleep_score_7d, 1)}`);
  _renderGarminGauge('fs-sleepscore-bar', scSegs, scActive, scPct, '0', '80 İyi', '100');

  // 04. Sleep Süre
  const slpH = Number(data.sleep_hours ?? 0);
  const slpSegs = [{ cls: 'seg-red', flex: 1 }, { cls: 'seg-amber', flex: 1.2 }, { cls: 'seg-green', flex: 1.6 }, { cls: 'seg-blue', flex: 0.7 }];
  const slpPct = _piecewiseGaugePct(slpH, [4.0, 5.5, 7.0, 9.0, 9.5], slpSegs);
  const slpActive = slpH < 5.5 ? 0 : (slpH < 7.0 ? 1 : (slpH <= 9.0 ? 2 : 3));
  setText('fs-sleephours-val', formatHm(data.sleep_hours));
  setText('fs-sleephours-sub', `7G Ort: ${formatHm(data.sleep_hours_7d)} · 93G Ort: ${fmtDec(data.sleep_duration_hours, 2)} sa`);
  _renderGarminGauge('fs-sleephours-bar', slpSegs, slpActive, slpPct, '<5.5s', '7–9s Optimal', '9.5s');

  // 05. REM Oranı
  const remPct = data.rem_sleep_pct !== undefined
    ? data.rem_sleep_pct
    : (data.sleep_hours > 0 && data.rem_hours !== undefined ? (data.rem_hours / data.sleep_hours) * 100 : undefined);
  const remNum = Number(remPct ?? 0);
  const remSegs = [{ cls: 'seg-red', flex: 0.9 }, { cls: 'seg-amber', flex: 1.2 }, { cls: 'seg-green', flex: 1.5 }, { cls: 'seg-blue', flex: 0.9 }];
  const remBarPct = _piecewiseGaugePct(remNum, [8, 12, 18, 25, 30], remSegs);
  const remActive = remNum < 12 ? 0 : (remNum < 18 ? 1 : (remNum <= 25 ? 2 : 3));
  const rem7 = Number(data.rem_sleep_pct_7d);
  const rem7Pct = Number.isFinite(rem7) ? _piecewiseGaugePct(rem7, [8, 12, 18, 25, 30], remSegs) : null;
  const remValEl = document.getElementById('fs-rem-val');
  if (remValEl) {
    remValEl.innerHTML = `%${escapeHtml(fmtDec(remPct, 1))} <span class="text-[11px] font-medium text-[var(--text-secondary)]">Günlük</span>`
      + ` <span class="rem-7d-dot" aria-hidden="true"></span> <span class="text-[13px]">%${escapeHtml(fmtDec(data.rem_sleep_pct_7d, 1))}</span> <span class="text-[11px] font-medium text-[var(--text-secondary)]">7G</span>`;
  }
  setText('fs-rem-sub', `Derin (Günlük): %${fmtDec(data.deep_sleep_pct, 1)} · 7G Derin: %${fmtDec(data.deep_sleep_pct_7d, 1)}`);
  _renderGarminGauge('fs-rem-bar', remSegs, remActive, remBarPct, '%10', '%20–25 Optimal', '%30', rem7Pct, '7 günlük ortalama REM');

  // 06. Günlük Adım
  const stepCur = Number(data.steps ?? 0);
  const stepGoal = Math.max(1, Number(data.step_goal ?? 0));
  const stepPct = Math.max(0, Math.min(100, (stepCur / stepGoal) * 100));
  setText('fs-steps-val', formatTrInt(data.steps));
  setText('fs-steps-sub', `Son Tam Gün: ${formatTrInt(data.steps_prev_full_day)} · Hedef: ${formatTrInt(data.step_goal)} (%${fmtDec(data.steps_pct, 0)})`);
  const stepsSubEl = document.getElementById('fs-steps-sub');
  if (stepsSubEl) stepsSubEl.style.color = '';
  const stepBarEl = document.getElementById('fs-steps-bar');
  if (stepBarEl) {
    const pinLeft = Math.max(2, Math.min(98, stepPct));
    stepBarEl.innerHTML = `
      <div class="garmin-gauge">
        <div class="garmin-fill-track" style="overflow:visible">
          <div class="seg-green h-full rounded-[2px]" style="width:${stepPct.toFixed(1)}%"></div>
          <span class="garmin-gauge-pin" style="left:${pinLeft.toFixed(1)}%" title="Bugün: ${formatTrInt(stepCur)} adım (%${Math.round(stepPct)})"></span>
        </div>
        <div class="garmin-gauge-scale">
          <span>0</span>
          <span>Bugün %${Math.round(stepPct)}</span>
          <span>${formatTrInt(stepGoal)}</span>
        </div>
      </div>
    `;
  }

  // 07. Acute Load
  const acwrSegs = [{ cls: 'seg-amber', flex: 0.9 }, { cls: 'seg-green', flex: 1.8 }, { cls: 'seg-amber', flex: 0.8 }, { cls: 'seg-red', flex: 0.9 }];
  const acwrBarPct = _piecewiseGaugePct(acwrNum, [0.5, 0.8, 1.3, 1.5, 1.8], acwrSegs);
  const acwrActive = acwrNum < 0.8 ? 0 : (acwrNum <= 1.3 ? 1 : (acwrNum <= 1.5 ? 2 : 3));
  setText('fs-acuteload-val', formatTrInt(acuteVal));
  setText('fs-acuteload-sub', `Kronik (28G): ${formatTrInt(chronicVal)}`);
  _renderGarminGauge('fs-acuteload-bar', acwrSegs, acwrActive, acwrBarPct, '<0.8', '0.8–1.3 Optimal', '>1.5');

  // 08. Load Focus
  const lf = data.load_focus_summary || (data.training_load && data.training_load.load_focus) || {};
  const lowPct = Number(lf.low_aerobic_pct ?? (lf.aerobic_low && lf.aerobic_low.pct_of_target) ?? 0);
  const highPct = Number(lf.high_aerobic_pct ?? (lf.aerobic_high && lf.aerobic_high.pct_of_target) ?? 0);
  const anPct = Number(lf.anaerobic_pct ?? (lf.anaerobic && lf.anaerobic.pct_of_target) ?? 0);
  setText('fs-loadfocus-val', lf.recommended_focus_label || 'Anaerobik (İnterval)');
  const lfBarEl = document.getElementById('fs-loadfocus-bar');
  if (lfBarEl) {
    const drift = lf.weekly_bar_drift || null;
    const bar = (cls, label, pct, dObj) => {
      const w = Math.min(100, Math.max(6, pct));
      const pin = Math.max(3, Math.min(97, w));
      const endPct = dObj ? Number(dObj.week_end_pct ?? pct) : pct;
      const endPin = Math.max(3, Math.min(97, Math.min(100, Math.max(4, endPct))));
      const showEndDot = dObj && dObj.expiring_pct > 0;
      const endDotHtml = showEndDot
        ? `<span title="Pazar 28G düşüşü sonrası: %${Math.round(endPct)} (-%${Math.round(dObj.expiring_pct)})" style="position:absolute;left:${endPin}%;top:50%;transform:translate(-50%,-50%);width:8px;height:8px;border-radius:9999px;background:#E57368;border:1.5px solid #131a16;z-index:2;pointer-events:auto;" aria-hidden="true"></span>`
        : '';
      return `
        <div>
          <div class="garmin-fill-track garmin-fill-track--pin">
            <div class="${cls} h-full" style="width:${w}%"></div>
            ${endDotHtml}
            <span class="garmin-gauge-pin" style="left:${pin}%"></span>
          </div>
          <div class="garmin-gauge-scale mt-0.5"><span>${label}</span><span>%${Math.round(pct)}</span></div>
        </div>`;
    };
    const hasAnyDrop = drift && [drift.low_aerobic, drift.high_aerobic, drift.anaerobic].some(d => d && d.expiring_pct > 0);
    const driftLegend = hasAnyDrop
      ? `<div class="flex items-center justify-end gap-3 mt-1 font-mono text-[10px] text-[var(--text-muted)]">
          <span class="inline-flex items-center gap-1"><span style="width:6px;height:6px;border-radius:9999px;background:#f0ede4;display:inline-block" aria-hidden="true"></span>Güncel</span>
          <span class="inline-flex items-center gap-1"><span style="width:6px;height:6px;border-radius:9999px;background:#E57368;display:inline-block" aria-hidden="true"></span>Pazar 28G düşüşü</span>
        </div>`
      : '';
    lfBarEl.innerHTML = `
      <div class="garmin-focus-mini">
        ${bar('seg-blue', 'Düşük', lowPct, drift?.low_aerobic)}
        ${bar('seg-amber', 'Yüksek', highPct, drift?.high_aerobic)}
        ${bar('seg-purple', 'Anaer', anPct, drift?.anaerobic)}
      </div>
      ${driftLegend}
    `;
  }
}

function renderOverview(data) {
  if (!data) return;
  const curLoad = (data.training_load && data.training_load.current_status) || {};
  const vo2 = data.training_load && data.training_load.vo2max_current ? data.training_load.vo2max_current : (curLoad.vo2max || data.vo2max || 0);
  const acuteVal = curLoad.acute_load !== undefined ? curLoad.acute_load : (data.acute_load || 0);
  const chronicVal = curLoad.chronic_load !== undefined ? curLoad.chronic_load : (data.chronic_load || 0);
  const acwrNum = curLoad.acwr !== undefined ? Number(curLoad.acwr) : Number(data.acwr || 1.0);
  const tMin = curLoad.tunnel_min ? Math.round(curLoad.tunnel_min) : (data.tunnel_min || 0);
  const tMax = curLoad.tunnel_max ? Math.round(curLoad.tunnel_max) : (data.tunnel_max || 0);

  renderFirstScreenTelemetryCards(data, vo2, curLoad, acuteVal, chronicVal, acwrNum, tMin, tMax);

  const ifsStatus = document.getElementById('inFocusTrainingStatus');
  if (ifsStatus && (curLoad.status_tr || data.training_status)) {
    const trMon = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
    const asOf = curLoad.status_is_fallback && curLoad.status_as_of ? String(curLoad.status_as_of).split('-') : null;
    const asOfTxt = asOf && asOf.length === 3 ? ` · ${Number(asOf[2])} ${trMon[Number(asOf[1]) - 1]} verisi` : '';
    ifsStatus.textContent = (curLoad.status_tr || data.training_status) + asOfTxt;
    ifsStatus.title = asOfTxt ? 'Garmin bugün için antrenman durumu döndürmedi; son bilinen durum gösteriliyor.' : '';
  }
  const ifsSub = document.getElementById('inFocusStatusSub');
  if (ifsSub) {
    ifsSub.innerHTML = `Kondisyon: <span class="moss-text font-medium">${escapeHtml(curLoad.fitness_trend || '--')}</span> · ACWR ${acwrNum.toFixed(2)}`;
  }

  const kw = document.getElementById('kpi-weight');
  if (kw && data.weight !== undefined) kw.textContent = String(data.weight).replace('.', ',') + ' kg';
  const kwb = document.getElementById('kpi-weight-badge');
  if (kwb && data.total_loss_kg !== undefined) kwb.textContent = `-${String(data.total_loss_kg).replace('.', ',')} kg`;

  const k5 = document.getElementById('kpi-5k');
  const k5p = document.getElementById('kpi-5k-pace');
  if (k5 && data.latest_5k) {
    const parts = data.latest_5k.split(' ');
    k5.textContent = parts[0] || '--:--';
    if (k5p && parts.length > 1) k5p.textContent = parts.slice(1).join(' ');
  }

  if (data.biometrics_93d && typeof render93dBiometrics === 'function') {
    render93dBiometrics(data.biometrics_93d);
  }
  if (data.weekly_quota) renderWeeklyQuotaPanels(data.weekly_quota);
}

function _decisionStamp(dec) {
  if (dec === 'CONSOLIDATE' || dec === 'READINESS_HOLD') {
    return '<span class="stamp-tag stamp-ochre">KONSOLİDASYON</span>';
  }
  if (dec === 'DELOAD_10PCT' || dec === 'DETRAINING_RESET') {
    return '<span class="stamp-tag stamp-crimson">%10 DELOAD</span>';
  }
  return '<span class="stamp-tag stamp-moss">ARTIŞ (+kg)</span>';
}

/* Salon geçmişi tablosu: sunucu en yeni N seansı sayfa sayfa verir; "Daha eski seansları göster" ile eklenir (binlerce kayıtta DOM şişmez) */
let _gymHistoryState = { loaded: 0, total: 0, limit: 50, busy: false };

function _gymHistoryRow(sess) {
  const tr = document.createElement('tr');
  tr.className = "hover:bg-[var(--bg-subtle)] transition";
  const exSummary = `<div class="flex flex-wrap gap-x-2.5 gap-y-0.5 text-[12px] leading-tight">` + (sess.exercises || []).map(ex => {
    const setStr = (ex.sets || []).map(s => `${s.reps}x${s.weight_kg}kg`).join(', ');
    return `<span><strong class="font-semibold">${escapeHtml(ex.name)}</strong>: <span class="font-mono accent-text">${escapeHtml(setStr)}</span></span>`;
  }).join('') + `</div>`;
  tr.innerHTML = `
<td class="py-1 px-2 text-[11px] font-mono font-medium whitespace-nowrap">${escapeHtml(sess.date)} <span class="text-[var(--text-muted)] text-[11px]">${escapeHtml(sess.time || '')}</span></td>
<td class="py-1 px-2 text-[11px] font-semibold whitespace-nowrap ${sess.workout_type === 'Workout A' ? 'accent-text' : ''}">${escapeHtml(sess.workout_type)}</td>
<td class="py-1 px-2 text-[11px] font-mono text-[var(--text-secondary)] whitespace-nowrap">${sess.duration_min} dk · ${sess.calories} kcal</td>
<td class="py-1 px-2 text-[11px] font-mono font-semibold whitespace-nowrap">${(sess.total_volume_kg / 1000.0).toFixed(2)} Ton</td>
<td class="py-1 px-2">${exSummary}</td>
  `;
  return tr;
}

function _appendGymHistoryRows(sessions) {
  const tableBody = document.getElementById('gymHistoryTableBody');
  if (!tableBody) return;
  const frag = document.createDocumentFragment();
  sessions.forEach(sess => frag.appendChild(_gymHistoryRow(sess)));
  tableBody.appendChild(frag);
  _gymHistoryState.loaded += sessions.length;
  const countEl = document.getElementById('gymHistoryCount');
  if (countEl) countEl.textContent = _gymHistoryState.total ? `${_gymHistoryState.loaded} / ${_gymHistoryState.total} seans` : 'Kayıtlı seans yok';
  const btn = document.getElementById('gymHistoryMoreBtn');
  if (btn) btn.classList.toggle('hidden', _gymHistoryState.loaded >= _gymHistoryState.total);
}

async function loadMoreGymHistory() {
  const st = _gymHistoryState;
  if (st.busy || st.loaded >= st.total) return;
  st.busy = true;
  const btn = document.getElementById('gymHistoryMoreBtn');
  if (btn) btn.textContent = 'Yükleniyor...';
  try {
    const res = await fetch(`/api/gym-history?limit=${st.limit}&offset=${st.loaded}`, { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      st.total = Number(data.sessions_total ?? st.total);
      _appendGymHistoryRows(data.sessions || []);
    }
  } catch (_) {
    /* ağ hatası: kullanıcı düğmeye tekrar basabilir */
  } finally {
    st.busy = false;
    if (btn) btn.textContent = 'Daha eski seansları göster';
  }
}

function renderGymHistory(gym) {
  if (!gym) return;

  const activeSplit = (gym.program_state || {}).active_split || '5x5_linear';
  const catalog = gym.split_catalog || {};
  const splitInfo = catalog[activeSplit] || { short_name: '5x5 Doğrusal', name: 'StrongLifts 5x5' };
  const activeBadge = document.getElementById('gymActiveSplitBadge');
  if (activeBadge) activeBadge.textContent = (splitInfo.short_name || '5x5').toUpperCase();

  const evoBar = document.getElementById('gymProgramEvolutionBar');
  if (evoBar) {
    const pa = gym.plateau_analysis || { plateau_score: 0, tier_label: 'Doğrusal İvme Aktif', recommendation: '', signals: [], recommended_split: '5x5_linear' };
    const pScore = pa.plateau_score || 0;
    evoBar.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="space-y-0.5">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-mono text-[11px] uppercase tracking-wider font-semibold accent-text">Aktif Program: ${escapeHtml(splitInfo.name || splitInfo.short_name || '')}</span>
            <span class="stamp-tag stamp-accent">Haftada 2 Gün A/B</span>
            <span class="stamp-tag ${pScore >= 55 ? 'stamp-ochre' : 'stamp-moss'}">Plato Skoru: ${pScore}/100</span>
          </div>
          <p class="text-[11px] text-[var(--text-secondary)] leading-snug">${escapeHtml(pa.tier_label || '')} · ${escapeHtml(pa.recommendation || '')}</p>
        </div>
      </div>
      <div class="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] font-mono text-[var(--text-muted)]">
        ${(pa.signals || []).map(sig => `<span>• ${escapeHtml(sig)}</span>`).join('')}
      </div>
    `;
  }

  const progGrid = document.getElementById('gymProgressionGrid');
  if (progGrid && gym.progression) {
    progGrid.innerHTML = '';
    const coreKeys = ['squat', 'bench', 'row', 'ohp', 'deadlift', 'lat_pulldown', 'lateral_raise', 'shrug'];
    const allKeys = Object.keys(gym.progression);
    const newestDate = allKeys.map(k => gym.progression[k].last_full_date || '').sort().pop() || '';
    const dayGap = (d) => (d && newestDate) ? Math.round((new Date(newestDate) - new Date(d)) / 86400000) : 0;
    const extraKeys = allKeys
      .filter(k => !coreKeys.includes(k) && dayGap(gym.progression[k].last_full_date) <= 56)
      .sort((a, b) => (gym.progression[b].last_full_date || '').localeCompare(gym.progression[a].last_full_date || ''));
    [...coreKeys, ...extraKeys].forEach(k => {
      const item = gym.progression[k];
      if (!item) return;
      const div = document.createElement('div');
      div.className = "tint-panel p-3.5 space-y-1.5 flex flex-col justify-between";
      const hist = Array.isArray(item.history) ? item.history : [];
      const projList = Array.isArray(item.projected_weights) ? item.projected_weights.slice(0, 3).map(w => `${Number(w).toFixed(1)}`).join(' → ') : '';
      div.innerHTML = `
<div class="space-y-1">
  <div class="flex flex-wrap items-center justify-between gap-1.5">
    <span class="font-semibold text-xs">${escapeHtml(item.name)}${item.is_core === false ? ' <span class="stamp-tag stamp-sky">YENİ</span>' : ''}</span>
    ${_decisionStamp(item.decision)}
  </div>
  <div class="flex flex-wrap items-center justify-between gap-1 font-mono text-[11px] text-[var(--text-secondary)]">
    <span>e1RM: <strong class="text-[var(--text-primary)]">${item.e1rm_kg ?? '--'} kg</strong> (${item.bw_ratio ?? '--'}x BW)</span>
    <span>${escapeHtml(item.delta)}</span>
  </div>
  <p class="font-mono text-[12px] text-[var(--text-secondary)] leading-snug" title="${escapeHtml(hist.join(' → '))}">${escapeHtml(hist.slice(-2).join(' → '))}</p>
  ${item.decision_reason ? `<p class="text-[11px] text-[var(--text-muted)] leading-snug">${escapeHtml(item.decision_reason)}</p>` : ''}
</div>
<div class="pt-1.5 border-t border-[var(--border-subtle)] space-y-0.5">
  <p class="font-mono text-[11px] font-medium moss-text flex items-center gap-1">${lucideSvg('target', 'w-3 h-3 shrink-0')}<span>Hedef: ${escapeHtml(item.next_target)}</span></p>
  ${projList ? `<p class="font-mono text-[11px] accent-text">Projeksiyon: ${escapeHtml(projList)} kg</p>` : ''}
</div>
      `;
      progGrid.appendChild(div);
    });
  }

  const tableBody = document.getElementById('gymHistoryTableBody');
  if (tableBody && gym.sessions) {
    tableBody.innerHTML = '';
    _gymHistoryState = { loaded: 0, total: Number(gym.sessions_total ?? gym.sessions.length), limit: Number(gym.sessions_limit || gym.sessions.length || 50), busy: false };
    _appendGymHistoryRows(gym.sessions);
  }
  if (typeof refreshIcons === 'function') refreshIcons();
}

// AKTİVİTELER & DİNAMİK BRANŞ FİLTRELEME
let currentSportFilter = 'all';

function updateActivityStatsSummary(acts) {
  const sumCount = document.getElementById('actSumCount');
  const sumDur = document.getElementById('actSumDur');
  const sumDist = document.getElementById('actSumDist');
  const sumLoad = document.getElementById('actSumLoad');
  const sumCal = document.getElementById('actSumCal');

  if (!sumCount) return;

  const list = acts || [];
  let totalDurMin = 0;
  let totalDistKm = 0;
  let totalLoad = 0;
  let totalCal = 0;

  list.forEach(a => {
    totalDurMin += (a.dur_m || 0);
    totalDistKm += (a.dist_km || 0);
    totalLoad += (a.load || 0);
    totalCal += (a.cal || 0);
  });

  sumCount.textContent = list.length + " Seans";
  if (sumDur) sumDur.textContent = (totalDurMin / 60).toFixed(1) + " Saat";
  if (sumDist) sumDist.textContent = totalDistKm.toFixed(1) + " km";
  if (sumLoad) sumLoad.textContent = Math.round(totalLoad).toLocaleString('tr-TR');
  if (sumCal) sumCal.textContent = Math.round(totalCal).toLocaleString('tr-TR') + " kcal";
}

function renderActivityFilters(allActs) {
  const bar = document.getElementById('activityFilterBar');
  if (!bar || !Array.isArray(allActs)) return;

  const counts = {};
  allActs.forEach(a => {
    const sp = a.sport || 'other';
    counts[sp] = (counts[sp] || 0) + 1;
  });

  const sortedSports = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
  const buttons = [
    `<button type="button" data-calls="[[&quot;filterActivities&quot;, &quot;all&quot;]]" id="af-all" class="${currentSportFilter === 'all' ? 'btn-primary' : 'btn-secondary'} text-xs px-3 py-1.5">Tümü (${allActs.length})</button>`
  ];
  sortedSports.forEach(sp => {
    const sample = allActs.find(a => a.sport === sp) || {};
    const label = getDynamicSportLabel(sp, sample.sport_tr);
    const cls = currentSportFilter === sp ? 'btn-primary' : 'btn-secondary';
    buttons.push(`<button type="button" data-calls="${escapeHtml(JSON.stringify([['filterActivities', sp]]))}" id="af-${escapeHtml(sp)}" class="${cls} text-xs px-3 py-1.5">${escapeHtml(label)} (${counts[sp]})</button>`);
  });
  bar.innerHTML = buttons.join('');
}

function normalizeSearchText(str) {
  return (str || '')
    .toLowerCase()
    .replace(/ğ/g, 'g')
    .replace(/ü/g, 'u')
    .replace(/ş/g, 's')
    .replace(/ı/g, 'i')
    .replace(/i̇/g, 'i')
    .replace(/ö/g, 'o')
    .replace(/ç/g, 'c');
}

function searchActivities(term) {
  if (!globalActivities) return;
  const rawQ = (term || '').trim();
  const q = normalizeSearchText(rawQ);

  const filtered = globalActivities.filter(a => {
    if (currentSportFilter !== 'all' && a.sport !== currentSportFilter) {
      return false;
    }
    if (!q) return true;

    const spTr = getDynamicSportLabel(a.sport, a.sport_tr);
    const searchable = normalizeSearchText(`${a.name || ''} ${a.date || ''} ${a.sport || ''} ${spTr} ${a.pace_str || ''} ${a.te_label || ''}`);
    return searchable.includes(q);
  });

  renderActivities(filtered, false, true);
}

function filterActivities(sport) {
  currentSportFilter = sport;
  if (globalActivities) renderActivityFilters(globalActivities);
  const searchInput = document.getElementById('actSearchInput');
  const term = searchInput ? searchInput.value : '';
  searchActivities(term);
}

const ACT_PAGE_SIZE = 5;
let currentActivityPage = 1;
let lastRenderedActivities = [];

function changeActivityPage(delta) {
  const totalPages = Math.max(1, Math.ceil((lastRenderedActivities || []).length / ACT_PAGE_SIZE));
  currentActivityPage = Math.max(1, Math.min(totalPages, currentActivityPage + delta));
  renderActivities(lastRenderedActivities, false, false);
}

function renderActivities(acts, rebuildFilters = true, resetPage = true) {
  if (rebuildFilters && Array.isArray(acts)) {
    renderActivityFilters(acts);
  }
  const fullList = Array.isArray(acts) ? acts : [];
  lastRenderedActivities = fullList;
  if (resetPage) currentActivityPage = 1;

  updateActivityStatsSummary(fullList);

  const totalPages = Math.max(1, Math.ceil(fullList.length / ACT_PAGE_SIZE));
  currentActivityPage = Math.max(1, Math.min(totalPages, currentActivityPage));
  const startIdx = (currentActivityPage - 1) * ACT_PAGE_SIZE;
  const pageItems = fullList.slice(startIdx, startIdx + ACT_PAGE_SIZE);

  const pageInfo = document.getElementById('activitiesPageInfo');
  const prevBtn = document.getElementById('actPrevBtn');
  const nextBtn = document.getElementById('actNextBtn');
  if (pageInfo) pageInfo.textContent = `Sayfa ${currentActivityPage} / ${totalPages} (${fullList.length} seans)`;
  if (prevBtn) prevBtn.disabled = currentActivityPage <= 1;
  if (nextBtn) nextBtn.disabled = currentActivityPage >= totalPages;

  const aBody = document.getElementById('activitiesTableBody');
  if (!aBody) return;
  aBody.innerHTML = '';
  pageItems.forEach((a) => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-[var(--bg-subtle)] transition cursor-pointer group text-[12px]";
    tr.title = "Aktivite detaylarını ve sensör telemetrisini açmak için tıklayın";
    tr.onclick = () => openActivityModal(a);
    const teDisplay = a.aTE ? `<span class="font-mono text-[10.5px] font-semibold moss-text">A:${Number(a.aTE).toFixed(1)}</span>/<span class="font-mono text-[10.5px] font-semibold crimson-text">An:${Number(a.anTE || 0).toFixed(1)}</span>` : '--';
    const durStr = a.dur_m !== null && a.dur_m !== undefined ? `${Number(a.dur_m).toFixed(0)} dk` : '--';
    const hrStr = `${a.avg_hr ?? '--'}/${a.max_hr ?? '--'}`;
    const spLower = String(a.sport || '').toLowerCase();
    const spBadgeCls = spLower === 'running' ? 'stamp-sky' : (spLower === 'strength_training' ? 'stamp-ochre' : 'stamp-violet');
    tr.innerHTML = `
      <td class="py-1 px-1.5 text-[10.5px] font-mono font-medium whitespace-nowrap">${escapeHtml(a.date)} <span class="text-[var(--text-muted)]">${escapeHtml(a.time || '')}</span></td>
      <td class="py-1 px-1.5 whitespace-nowrap"><span class="stamp-tag ${spBadgeCls}">${escapeHtml(getDynamicSportLabel(a.sport, a.sport_tr))}</span></td>
      <td class="py-1 px-1.5 text-[10.5px] font-medium group-hover:text-[var(--accent)] transition max-w-[140px] truncate">${escapeHtml(a.name || '--')}</td>
      <td class="py-1 px-1.5 text-[10.5px] font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${durStr}</td>
      <td class="py-1 px-1.5 text-[10.5px] font-mono font-semibold accent-text tabular-nums whitespace-nowrap">${a.dist_km > 0 ? Number(a.dist_km).toFixed(2) + ' km' : '--'}</td>
      <td class="py-1 px-1.5 text-[10.5px] font-mono font-semibold tabular-nums whitespace-nowrap">${escapeHtml(a.pace_str || '--')}</td>
      <td class="py-1 px-1.5 text-[10.5px] font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${hrStr}</td>
      <td class="py-1 px-1.5 text-[10.5px] font-mono font-semibold tabular-nums whitespace-nowrap">${a.load ? Number(a.load).toFixed(1) : '0'}</td>
      <td class="py-1 px-1.5 whitespace-nowrap">${teDisplay}</td>
      <td class="py-1 px-1.5 text-[10.5px] font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${a.cal ?? 0} kcal</td>
    `;
    aBody.appendChild(tr);
  });
}

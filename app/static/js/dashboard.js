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

function _renderGarminGauge(containerId, segments, activeIdx, markerPct, leftLbl, midLbl, rightLbl) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const clamped = Math.max(3, Math.min(97, Number(markerPct) || 0));
  el.innerHTML = `
    <div class="garmin-gauge">
      <div class="garmin-gauge-track">
        ${segments.map((s, idx) => `<div class="garmin-seg ${s.cls} ${idx === activeIdx ? 'active' : ''}" style="flex:${s.flex ?? 1}"></div>`).join('')}
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

  // 01. HRV (7 Günlük Bar Chart + 7G Ort Renk İndikatörü)
  const hrvVal = Number(data.overnight_hrv ?? 43);
  const hrvBase = Number(data.hrv_7d ?? 46) || 46;
  const hrvStLower = String(data.hrv_status || '').toLowerCase();
  const hrvAvgColor = (hrvStLower.includes('zayıf') || hrvStLower.includes('poor') || hrvBase < 32)
    ? '#C96A5B'
    : ((hrvStLower.includes('düşük') || hrvStLower.includes('low') || hrvBase < 38) ? '#C99A49' : '#5E8F74');
  setText('fs-hrv-val', `${data.overnight_hrv !== undefined ? Math.round(data.overnight_hrv) : '--'} ms`);
  const hrvSubEl = document.getElementById('fs-hrv-sub');
  if (hrvSubEl) {
    hrvSubEl.innerHTML = `<span class="inline-flex items-center gap-1"><span style="width:6px;height:6px;border-radius:9999px;background:${hrvAvgColor};display:inline-block" aria-hidden="true"></span><span>7G Ort: <strong style="color:${hrvAvgColor}">${escapeHtml(String(data.hrv_7d ?? '--'))} ms</strong></span></span> · RHR (Günlük): ${escapeHtml(String(data.resting_hr ?? '--'))} bpm`;
  }
  const hrvSeries = Array.isArray(data.hrv_7d_series) ? data.hrv_7d_series : [];
  const hrvBarEl = document.getElementById('fs-hrv-bar');
  if (hrvBarEl) {
    if (hrvSeries.length) {
      const vals = hrvSeries.map(d => Number(d.hrv) || 0).filter(v => v > 0);
      const minV = vals.length ? Math.max(10, Math.min(...vals) - 6) : 25;
      const maxV = vals.length ? Math.max(...vals, hrvBase + 5) : 65;
      const span = Math.max(10, maxV - minV);
      const barsHtml = hrvSeries.map((d, idx) => {
        const v = Number(d.hrv) || 0;
        const hPct = v > 0 ? Math.max(18, Math.min(100, ((v - minV) / span) * 100)) : 12;
        const stLower = String(d.status || '').toLowerCase();
        const cls = v <= 0
          ? 'bg-[var(--border-medium)]'
          : (stLower.includes('zayıf') || stLower.includes('poor') || v < hrvBase * 0.8
            ? 'seg-red'
            : (stLower.includes('düşük') || stLower.includes('low') || v < hrvBase * 0.92 ? 'seg-amber' : 'seg-green'));
        const dayLbl = d.date ? String(d.date).slice(8, 10) : String(idx + 1);
        const isLast = idx === hrvSeries.length - 1;
        return `<div class="hrv-7d-col" title="${escapeHtml(d.date || '')}: ${v > 0 ? Math.round(v) + ' ms' : '--'}">
          <div class="hrv-7d-bar ${cls}" style="height:${hPct.toFixed(0)}%;${isLast ? 'outline:1px solid #f0ede4;' : ''}"></div>
          <span class="hrv-7d-lbl">${escapeHtml(dayLbl)}</span>
        </div>`;
      }).join('');
      hrvBarEl.innerHTML = `<div class="hrv-7d-wrap"><div class="hrv-7d-bars">${barsHtml}</div></div>`;
    } else {
      const hrvRatioPct = Math.max(8, Math.min(92, 50 + ((hrvVal - hrvBase) / Math.max(10, hrvBase * 0.4)) * 35));
      const hrvSt = String(data.hrv_status || '').toLowerCase();
      const hrvActive = hrvSt.includes('zayıf') || hrvSt.includes('poor') ? 0 : (hrvSt.includes('düşük') || hrvSt.includes('low') ? 1 : 2);
      _renderGarminGauge('fs-hrv-bar',
        [{ cls: 'seg-red', flex: 1 }, { cls: 'seg-amber', flex: 1 }, { cls: 'seg-green', flex: 1.8 }, { cls: 'seg-amber', flex: 0.8 }],
        hrvActive, hrvRatioPct, 'Zayıf', 'Dengeli', 'Yüksek'
      );
    }
  }

  // 02. VO2 Max (+ Trend Yönü)
  const vo2Num = Number(vo2) || 45.4;
  const vo2Pct = ((vo2Num - 34) / (60 - 34)) * 100;
  const vo2Active = vo2Num < 38 ? 0 : (vo2Num < 44 ? 1 : (vo2Num < 50 ? 2 : (vo2Num < 55 ? 3 : 4)));
  const vt = data.vo2max_trend || {};
  const vtArrow = vt.arrow || '→';
  const vtLabel = vt.label || 'Sabit';
  const vtDelta = vt.delta !== undefined && vt.delta !== null
    ? `${Number(vt.delta) > 0 ? '+' : ''}${fmtDec(vt.delta, 1)}`
    : '0,0';
  setText('fs-vo2-val', fmtDec(vo2, 1));
  setText('fs-vo2-sub', `Trend: ${vtArrow} ${vtDelta} (${fmtDec(vt.prev ?? vo2Num, 1)}→${fmtDec(vo2Num, 1)})`);
  _renderGarminGauge('fs-vo2-bar',
    [{ cls: 'seg-red' }, { cls: 'seg-amber' }, { cls: 'seg-green' }, { cls: 'seg-blue' }, { cls: 'seg-purple' }],
    vo2Active, vo2Pct, 'Zayıf', 'İyi', 'Üstün'
  );

  // 03. Sleep Score
  const sc = data.sleep_score !== undefined ? Math.round(data.sleep_score) : null;
  const scNum = sc ?? 80;
  const scActive = scNum < 60 ? 0 : (scNum < 80 ? 1 : (scNum < 90 ? 2 : 3));
  setText('fs-sleepscore-val', sc !== null ? `${sc} / 100` : '-- / 100');
  setText('fs-sleepscore-sub', `7G Ort: ${fmtDec(data.sleep_score_7d, 1)}`);
  _renderGarminGauge('fs-sleepscore-bar',
    [{ cls: 'seg-red', flex: 1.5 }, { cls: 'seg-amber', flex: 1.3 }, { cls: 'seg-green', flex: 1.2 }, { cls: 'seg-blue', flex: 1 }],
    scActive, scNum, '0', '80 İyi', '100'
  );

  // 04. Sleep Süre
  const slpH = Number(data.sleep_hours ?? 6.5);
  const slpPct = ((slpH - 4.0) / (9.5 - 4.0)) * 100;
  const slpActive = slpH < 5.5 ? 0 : (slpH < 7.0 ? 1 : (slpH <= 9.0 ? 2 : 3));
  setText('fs-sleephours-val', formatHm(data.sleep_hours));
  setText('fs-sleephours-sub', `7G Ort: ${formatHm(data.sleep_hours_7d)} · 93G Ort: ${fmtDec(data.sleep_duration_hours, 2)} sa`);
  _renderGarminGauge('fs-sleephours-bar',
    [{ cls: 'seg-red', flex: 1 }, { cls: 'seg-amber', flex: 1.2 }, { cls: 'seg-green', flex: 1.6 }, { cls: 'seg-blue', flex: 0.7 }],
    slpActive, slpPct, '<5.5s', '7–9s Optimal', '9.5s'
  );

  // 05. REM Oranı
  const remPct = data.rem_sleep_pct !== undefined
    ? data.rem_sleep_pct
    : (data.sleep_hours > 0 && data.rem_hours !== undefined ? (data.rem_hours / data.sleep_hours) * 100 : undefined);
  const remNum = Number(remPct ?? 18);
  const remBarPct = ((remNum - 8) / (30 - 8)) * 100;
  const remActive = remNum < 12 ? 0 : (remNum < 18 ? 1 : (remNum <= 25 ? 2 : 3));
  setText('fs-rem-val', `%${fmtDec(remPct, 1)}`);
  setText('fs-rem-sub', `7G REM: %${fmtDec(data.rem_sleep_pct_7d, 1)} · Derin (Günlük): %${fmtDec(data.deep_sleep_pct, 1)} (${fmtDec(data.deep_hours, 1)}s)`);
  _renderGarminGauge('fs-rem-bar',
    [{ cls: 'seg-red', flex: 0.9 }, { cls: 'seg-amber', flex: 1.2 }, { cls: 'seg-green', flex: 1.5 }, { cls: 'seg-blue', flex: 0.9 }],
    remActive, remBarPct, '%10', '%20–25 Optimal', '%30'
  );

  // 06. Günlük Adım
  const stepCur = Number(data.steps ?? 0);
  const stepGoal = Math.max(1, Number(data.step_goal ?? 10000));
  const stepPct = Math.max(0, Math.min(100, (stepCur / stepGoal) * 100));
  setText('fs-steps-val', formatTrInt(data.steps));
  setText('fs-steps-sub', `Son Tam Gün: ${formatTrInt(data.steps_prev_full_day)} · Hedef: ${formatTrInt(data.step_goal)} (%${fmtDec(data.steps_pct, 0)})`);
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
  const acwrBarPct = ((acwrNum - 0.5) / (1.8 - 0.5)) * 100;
  const acwrActive = acwrNum < 0.8 ? 0 : (acwrNum <= 1.3 ? 1 : (acwrNum <= 1.5 ? 2 : 3));
  setText('fs-acuteload-val', formatTrInt(acuteVal));
  setText('fs-acuteload-sub', `Kronik (28G): ${formatTrInt(chronicVal)} · Tünel: ${tMin}–${tMax}`);
  _renderGarminGauge('fs-acuteload-bar',
    [{ cls: 'seg-amber', flex: 0.9 }, { cls: 'seg-green', flex: 1.8 }, { cls: 'seg-amber', flex: 0.8 }, { cls: 'seg-red', flex: 0.9 }],
    acwrActive, acwrBarPct, '<0.8', '0.8–1.3 Optimal', '>1.5'
  );

  // 08. Load Focus
  const lf = data.load_focus_summary || (data.training_load && data.training_load.load_focus) || {};
  const lowPct = Number(lf.low_aerobic_pct ?? (lf.aerobic_low && lf.aerobic_low.pct_of_target) ?? 0);
  const highPct = Number(lf.high_aerobic_pct ?? (lf.aerobic_high && lf.aerobic_high.pct_of_target) ?? 0);
  const anPct = Number(lf.anaerobic_pct ?? (lf.anaerobic && lf.anaerobic.pct_of_target) ?? 0);
  setText('fs-loadfocus-val', lf.recommended_focus_label || 'Anaerobik & Laktat İntervali');
  setText('fs-loadfocus-sub', `Düşük %${fmtDec(lowPct, 0)} · Yüksek %${fmtDec(highPct, 0)} · Anaer %${fmtDec(anPct, 0)}`);
  const lfBarEl = document.getElementById('fs-loadfocus-bar');
  if (lfBarEl) {
    lfBarEl.innerHTML = `
      <div class="garmin-focus-mini">
        <div>
          <div class="garmin-fill-track"><div class="seg-blue h-full" style="width:${Math.min(100, Math.max(6, lowPct))}%"></div></div>
          <div class="garmin-gauge-scale mt-0.5"><span>Düşük</span><span>%${Math.round(lowPct)}</span></div>
        </div>
        <div>
          <div class="garmin-fill-track"><div class="seg-amber h-full" style="width:${Math.min(100, Math.max(6, highPct))}%"></div></div>
          <div class="garmin-gauge-scale mt-0.5"><span>Yüksek</span><span>%${Math.round(highPct)}</span></div>
        </div>
        <div>
          <div class="garmin-fill-track"><div class="seg-purple h-full" style="width:${Math.min(100, Math.max(6, anPct))}%"></div></div>
          <div class="garmin-gauge-scale mt-0.5"><span>Anaer</span><span>%${Math.round(anPct)}</span></div>
        </div>
      </div>
    `;
  }
}

function renderOverview(data) {
  if (!data) return;
  const curLoad = (data.training_load && data.training_load.current_status) || {};
  const vo2 = data.training_load && data.training_load.vo2max_current ? data.training_load.vo2max_current : (curLoad.vo2max || data.vo2max || '45.4');
  const acuteVal = curLoad.acute_load !== undefined ? curLoad.acute_load : (data.acute_load || 279);
  const chronicVal = curLoad.chronic_load !== undefined ? curLoad.chronic_load : (data.chronic_load || 279);
  const acwrNum = curLoad.acwr !== undefined ? Number(curLoad.acwr) : Number(data.acwr || 1.0);
  const tMin = curLoad.tunnel_min ? Math.round(curLoad.tunnel_min) : (data.tunnel_min || 223);
  const tMax = curLoad.tunnel_max ? Math.round(curLoad.tunnel_max) : (data.tunnel_max || 419);

  renderFirstScreenTelemetryCards(data, vo2, curLoad, acuteVal, chronicVal, acwrNum, tMin, tMax);

  const ifsStatus = document.getElementById('inFocusTrainingStatus');
  if (ifsStatus && (curLoad.status_tr || data.training_status)) {
    const rawSt = curLoad.status_tr || data.training_status;
    const paren = rawSt.match(/\(([^)]+)\)/);
    ifsStatus.textContent = paren ? paren[1] : rawSt;
  }
  const ifsSub = document.getElementById('inFocusStatusSub');
  if (ifsSub) {
    const lf = data.load_focus_summary || {};
    const lowP = lf.low_aerobic_pct !== undefined ? Math.round(Number(lf.low_aerobic_pct)) : '--';
    const highP = lf.high_aerobic_pct !== undefined ? Math.round(Number(lf.high_aerobic_pct)) : '--';
    const anP = lf.anaerobic_pct !== undefined ? Math.round(Number(lf.anaerobic_pct)) : '--';
    ifsSub.textContent = `ACWR ${acwrNum.toFixed(2)} · Düşük %${lowP} / Yüksek %${highP} / Anaer %${anP}`;
  }

  const kw = document.getElementById('kpi-weight');
  if (kw && data.weight !== undefined) kw.textContent = String(data.weight).replace('.', ',') + ' kg';
  const kwb = document.getElementById('kpi-weight-badge');
  if (kwb && data.total_loss_kg !== undefined) kwb.textContent = `-${String(data.total_loss_kg).replace('.', ',')} kg`;
  const kwbmi = document.getElementById('kpi-weight-bmi');
  if (kwbmi && data.bmi !== undefined) kwbmi.innerHTML = `VKİ: <strong class="text-[var(--text-primary)] font-semibold">${data.bmi}</strong>`;
  const kwbar = document.getElementById('kpi-weight-bar');
  if (kwbar && data.loss_pct !== undefined) {
    kwbar.style.width = `${Math.max(5, Math.min(100, Number(data.loss_pct)))}%`;
  }

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

function _renderBranchSummaryInto(containerId, sp, iconName) {
  const container = document.getElementById(containerId);
  if (!container || !sp) return;

  const extraKpis = [];
  if (sp.current_pace) extraKpis.push({ label: 'Mevcut 5K / Tempo', val: sp.current_pace });
  if (sp.efficiency_factor !== undefined && sp.efficiency_factor !== null) extraKpis.push({ label: 'Verimlilik (EF)', val: `${sp.efficiency_factor} m/atım` });
  if (sp.cadence) extraKpis.push({ label: 'Kadans Formu', val: sp.cadence });
  if (sp.current_status) extraKpis.push({ label: 'Rutin Durumu', val: sp.current_status });
  if (sp.goal) extraKpis.push({ label: 'Branş Hedefi', val: sp.goal });

  const extraGridHtml = extraKpis.length
    ? `<div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        ${extraKpis.map(k => `
          <div class="tint-panel p-2.5">
            <span class="font-mono text-[9.5px] uppercase tracking-wider text-[var(--text-secondary)] block">${escapeHtml(k.label)}</span>
            <span class="text-xs font-semibold text-[var(--text-primary)] break-words">${escapeHtml(String(k.val))}</span>
          </div>
        `).join('')}
      </div>`
    : '';

  const tipsHtml = (sp.how_to_improve || []).length
    ? `<div class="text-[11px] text-[var(--text-secondary)] space-y-1 tint-panel p-2.5 leading-snug">
        <p class="font-mono text-[9.5px] font-semibold uppercase tracking-wider text-[var(--text-primary)] mb-0.5">Öneriler</p>
        ${(sp.how_to_improve || []).map(item => `<p class="flex items-start gap-1.5"><span class="accent-text">·</span><span>${escapeHtml(item)}</span></p>`).join('')}
      </div>`
    : '';

  const lastHtml = sp.last_workout
    ? `<div class="text-[11px] tint-moss-panel p-2.5 space-y-1">
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <span class="font-semibold">${escapeHtml(sp.last_workout.date || '')}</span>
          <span class="stamp-tag stamp-moss">${escapeHtml(sp.last_workout.title || '')}</span>
        </div>
        <p class="text-[11px] moss-text leading-snug">${sp.last_workout.exercises ? sp.last_workout.exercises.map(escapeHtml).join(' · ') : ''}</p>
      </div>`
    : '';

  const upcomingList = Array.isArray(sp.upcoming_sessions) && sp.upcoming_sessions.length
    ? sp.upcoming_sessions.map(sess => `
        <div class="tint-panel p-2.5 text-[11px] space-y-0.5">
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <span class="font-semibold">${escapeHtml(sess.day || '')}</span>
            <span class="stamp-tag stamp-accent">${escapeHtml(sess.type || 'Seans')}</span>
          </div>
          <p class="font-medium text-xs">${escapeHtml(sess.title || '')} <span class="font-mono text-[10.5px] text-[var(--text-muted)]">(${escapeHtml(sess.duration || '')})</span></p>
          ${(sess.target_hr || sess.target_pace) ? `<p class="font-mono text-[10px] accent-text">${[sess.target_hr, sess.target_pace].filter(Boolean).map(escapeHtml).join(' · ')}</p>` : ''}
          <p class="text-[10.5px] text-[var(--text-secondary)] leading-snug">${escapeHtml(sess.details || '')}</p>
        </div>
      `).join('')
    : (sp.next_workout ? `
        <div class="text-[11px] tint-panel p-2.5">
          <p class="font-semibold">${escapeHtml(sp.next_workout.day)}: ${escapeHtml(sp.next_workout.title)} <span class="font-mono text-[var(--text-muted)]">(${escapeHtml(sp.next_workout.duration || '')})</span></p>
          <p class="text-[10.5px] text-[var(--text-secondary)] mt-0.5">${escapeHtml(sp.next_workout.details || (sp.next_workout.exercises ? sp.next_workout.exercises.join(', ') : ''))}</p>
        </div>
      ` : '');

  container.innerHTML = `
    <div class="space-y-2.5 min-w-0 flex flex-col justify-between">
      <div class="space-y-1">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <div class="icon-box w-7 h-7 shrink-0">${lucideSvg(iconName, 'w-3.5 h-3.5')}</div>
            <h4 class="font-editorial text-base font-medium tracking-tight leading-snug">${escapeHtml(sp.name || '')}</h4>
          </div>
          <span class="stamp-tag stamp-accent">${escapeHtml(sp.schedule_status || 'Aktif')}</span>
        </div>
        <p class="font-mono text-[10.5px] text-[var(--text-secondary)] leading-snug">${escapeHtml(sp.stats_summary || '')}</p>
      </div>
      ${extraGridHtml}
      ${tipsHtml}
      ${lastHtml}
    </div>
    <div class="space-y-2 min-w-0 lg:border-l lg:border-[var(--border-subtle)] lg:pl-4">
      <p class="font-mono text-[10px] uppercase tracking-wider font-semibold text-[var(--text-secondary)] flex items-center gap-1.5">
        ${lucideSvg('calendar', 'w-3.5 h-3.5 accent-text')}
        <span>Bu Hafta Kalan / Sıradaki Seçenekler</span>
      </p>
      <div class="space-y-2">${upcomingList}</div>
    </div>
  `;
}

function renderSports(sports) {
  if (!sports) return;
  if (sports.running) {
    _renderBranchSummaryInto('runningBranchSummaryContainer', sports.running, 'footprints');
  }
  if (sports.strength) {
    _renderBranchSummaryInto('gymBranchSummaryContainer', sports.strength, 'dumbbell');
  }
  if (typeof refreshIcons === 'function') refreshIcons();
}

function renderGymHistory(gym) {
  if (!gym) return;

  const badgeRow = document.getElementById('gymHeaderBadges');
  if (badgeRow && gym.progression) {
    const p = gym.progression;
    const shortDelta = (d) => String(d || '').split('(')[0].trim();
    const sq = p.squat ? `Squat ${p.squat.max_kg} kg (${shortDelta(p.squat.delta)})` : 'Squat --';
    const bn = p.bench ? `Bench ${p.bench.max_kg} kg 5x5` : 'Bench --';
    const rw = p.row ? `Row ${p.row.max_kg} kg 5x5` : 'Row --';
    badgeRow.innerHTML = `
      <span class="stamp-tag stamp-moss">${escapeHtml(sq)}</span>
      <span class="stamp-tag stamp-accent">${escapeHtml(bn)}</span>
      <span class="stamp-tag">${escapeHtml(rw)}</span>
    `;
  }

  const progGrid = document.getElementById('gymProgressionGrid');
  if (progGrid && gym.progression) {
    progGrid.innerHTML = '';
    const coreKeys = ['squat', 'bench', 'row', 'ohp', 'deadlift', 'lat_pulldown', 'lateral_raise', 'shrug'];
    coreKeys.forEach(k => {
      const item = gym.progression[k];
      if (!item) return;
      const div = document.createElement('div');
      div.className = "tint-panel p-3.5 space-y-1.5";
      const hist = Array.isArray(item.history) ? item.history : [];
      div.innerHTML = `
<div class="flex flex-wrap items-center justify-between gap-1.5">
  <span class="font-semibold text-xs">${escapeHtml(item.name)}</span>
  <span class="stamp-tag stamp-accent">${escapeHtml(item.delta)}</span>
</div>
<p class="font-mono text-[11px] text-[var(--text-secondary)] leading-snug" title="${escapeHtml(hist.join(' → '))}">${escapeHtml(hist.slice(-2).join(' → '))}</p>
<p class="font-mono text-[11px] font-medium moss-text pt-1.5 border-t border-[var(--border-subtle)] flex items-center gap-1">${lucideSvg('target', 'w-3 h-3 shrink-0')}<span>Hedef: ${escapeHtml(item.next_target)}</span></p>
      `;
      progGrid.appendChild(div);
    });
  }

  const tableBody = document.getElementById('gymHistoryTableBody');
  if (tableBody && gym.sessions) {
    tableBody.innerHTML = '';
    gym.sessions.forEach(sess => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-[var(--bg-subtle)] transition";
      const exSummary = `<div class="flex flex-wrap gap-x-2.5 gap-y-0.5 text-[10.5px] leading-tight">` + (sess.exercises || []).map(ex => {
        const setStr = (ex.sets || []).map(s => `${s.reps}x${s.weight_kg}kg`).join(', ');
        return `<span><strong class="font-semibold">${escapeHtml(ex.name)}</strong>: <span class="font-mono accent-text">${escapeHtml(setStr)}</span></span>`;
      }).join('') + `</div>`;

      tr.innerHTML = `
<td class="py-1 px-2 text-[11px] font-mono font-medium whitespace-nowrap">${escapeHtml(sess.date)} <span class="text-[var(--text-muted)] text-[10px]">${escapeHtml(sess.time || '')}</span></td>
<td class="py-1 px-2 text-[11px] font-semibold whitespace-nowrap ${sess.workout_type === 'Workout A' ? 'accent-text' : ''}">${escapeHtml(sess.workout_type)}</td>
<td class="py-1 px-2 text-[11px] font-mono text-[var(--text-secondary)] whitespace-nowrap">${sess.duration_min} dk · ${sess.calories} kcal</td>
<td class="py-1 px-2 text-[11px] font-mono font-semibold whitespace-nowrap">${(sess.total_volume_kg / 1000.0).toFixed(2)} Ton</td>
<td class="py-1 px-2">${exSummary}</td>
      `;
      tableBody.appendChild(tr);
    });
  }
  if (typeof refreshIcons === 'function') refreshIcons();
}

function renderTrainingLoad(tl) {
  if (!tl) return;
  const cur = tl.current_status;
  const foc = tl.load_focus;

  if (cur) {
    document.getElementById('tl-status').textContent = cur.status_tr;
    document.getElementById('tl-acute').textContent = cur.acute_load;
    document.getElementById('tl-chronic').textContent = cur.chronic_load;
    document.getElementById('tl-tunnel').textContent = Math.round(cur.tunnel_min) + " – " + Math.round(cur.tunnel_max);
    document.getElementById('tl-acwr').textContent = Number(cur.acwr || 1.0).toFixed(2);
    const badge = document.getElementById('tl-acwr-badge');
    if (cur.acwr >= 0.8 && cur.acwr <= 1.3) {
      badge.textContent = "SWEET SPOT";
      badge.className = "stamp-tag stamp-moss";
    } else if (cur.acwr > 1.5) {
      badge.textContent = "AŞIRI YÜK";
      badge.className = "stamp-tag stamp-crimson";
    } else {
      badge.textContent = cur.acwr_status || 'TAKİPTE';
      badge.className = "stamp-tag stamp-ochre";
    }
  }

  if (foc) {
    const low = foc.aerobic_low || {};
    const high = foc.aerobic_high || {};
    const ana = foc.anaerobic || {};

    const balBadge = document.getElementById('tl-focus-balance-badge');
    if (balBadge) balBadge.textContent = foc.balance_phrase || 'Dengeli';

    const setFocusBar = (prefix, obj) => {
      const valEl = document.getElementById(`tl-focus-${prefix}`);
      const barEl = document.getElementById(`tl-focus-${prefix}-bar`);
      const tgtEl = document.getElementById(`tl-focus-${prefix}-target`);
      const stEl = document.getElementById(`tl-focus-${prefix}-status`);
      if (valEl) valEl.textContent = `${obj.actual ?? 0} birim`;
      const pct = obj.pct_of_target !== undefined ? obj.pct_of_target : (obj.target_max > 0 ? Math.round((obj.actual / obj.target_max) * 100) : 0);
      if (barEl) barEl.style.width = `${Math.max(4, Math.min(100, pct))}%`;
      if (tgtEl) tgtEl.textContent = `Hedef: ${obj.target_min ?? 0}–${obj.target_max ?? 0}`;
      if (stEl) {
        stEl.textContent = obj.status || 'Optimal';
        const isDeficit = foc.primary_deficit && ((prefix === 'low' && foc.primary_deficit === 'aerobic_low') || (prefix === 'high' && foc.primary_deficit === 'aerobic_high') || (prefix === 'anaerobic' && foc.primary_deficit === 'anaerobic'));
        stEl.className = isDeficit ? 'ochre-text font-semibold' : 'moss-text';
      }
    };

    setFocusBar('low', low);
    setFocusBar('high', high);
    setFocusBar('anaerobic', ana);

    const recBox = document.getElementById('tl-focus-recommendation');
    if (recBox) {
      recBox.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-2">
          <span class="font-mono text-[10px] font-semibold uppercase tracking-wider accent-text">Öncelikli Enerji Odağı: ${escapeHtml(foc.recommended_focus_label || 'Dengeli İdman')}</span>
          <span class="stamp-tag stamp-accent">Düşük ${low.pct_of_target ?? '--'}% · Yüksek ${high.pct_of_target ?? '--'}% · Anaerobik ${ana.pct_of_target ?? '--'}%</span>
        </div>
        <p class="text-[var(--text-primary)] leading-relaxed">${escapeHtml(foc.recommended_workout || foc.balance_note || '')}</p>
      `;
    }
  }

  const wBody = document.getElementById('trainingLoadWeeklyBody');
  if (wBody && tl.weekly_progression) {
    wBody.innerHTML = '';
    tl.weekly_progression.forEach(w => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-[var(--bg-subtle)] transition";
      const acwrColor = (w.acwr >= 0.8 && w.acwr <= 1.3) ? "moss-text font-semibold" : ((w.acwr > 1.5) ? "crimson-text font-semibold" : "ochre-text font-semibold");
      tr.innerHTML = `
<td class="py-2.5 px-3 font-mono font-medium whitespace-nowrap">${escapeHtml(w.date)}</td>
<td class="py-2.5 px-3 font-semibold accent-text">${escapeHtml(w.status_tr)}</td>
<td class="py-2.5 px-3 font-mono font-semibold tabular-nums">${w.acute_load}</td>
<td class="py-2.5 px-3 font-mono text-[var(--text-secondary)] tabular-nums">${w.chronic_load}</td>
<td class="py-2.5 px-3 font-mono ${acwrColor} tabular-nums">${Number(w.acwr || 1.0).toFixed(2)}</td>
<td class="py-2.5 px-3 text-[var(--text-secondary)]">${escapeHtml(w.acwr_status)}</td>
<td class="py-2.5 px-3 font-mono accent-text tabular-nums">${w.low_aero}</td>
<td class="py-2.5 px-3 font-mono ochre-text tabular-nums">${w.high_aero}</td>
<td class="py-2.5 px-3 font-mono crimson-text tabular-nums">${w.anaerobic}</td>
<td class="py-2.5 px-3 font-medium">${escapeHtml(w.balance_tr)}</td>
      `;
      wBody.appendChild(tr);
    });
  }

  const tBody = document.getElementById('trainingLoadTopActsBody');
  if (tBody && tl.top_load_acts) {
    tBody.innerHTML = '';
    tl.top_load_acts.forEach(a => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-[var(--bg-subtle)] transition cursor-pointer group";
      tr.title = "Aktivite telemetrisini incelemek için tıklayın";
      tr.onclick = () => openActivityModal(a);
      tr.innerHTML = `
<td class="py-3 px-4 font-mono font-medium group-hover:text-[var(--accent)] transition">
  <div class="flex items-center justify-between gap-2">
    <span>${escapeHtml(a.date)}</span>
    ${lucideSvg('arrow-up-right', 'w-3.5 h-3.5 accent-text opacity-0 group-hover:opacity-100 transition')}
  </div>
</td>
<td class="py-3 px-4 font-medium">${escapeHtml(getDynamicSportLabel(a.sport, a.sport_tr))}</td>
<td class="py-3 px-4 text-[var(--text-secondary)] max-w-[180px] truncate">${escapeHtml(a.name)}</td>
<td class="py-3 px-4 font-mono text-[var(--text-secondary)]">${a.dur_m} dk</td>
<td class="py-3 px-4 font-mono font-semibold accent-text">${a.load}</td>
<td class="py-3 px-4 font-mono font-semibold moss-text">${a.aTE ? Number(a.aTE).toFixed(1) : '--'}</td>
<td class="py-3 px-4 font-mono font-semibold crimson-text">${a.anTE ? Number(a.anTE).toFixed(1) : '--'}</td>
<td class="py-3 px-4"><span class="stamp-tag">${escapeHtml(a.te_label)}</span></td>
      `;
      tBody.appendChild(tr);
    });
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
    `<button type="button" onclick="filterActivities('all')" id="af-all" class="${currentSportFilter === 'all' ? 'btn-primary' : 'btn-secondary'} text-xs px-3 py-1.5">Tümü (${allActs.length})</button>`
  ];
  sortedSports.forEach(sp => {
    const sample = allActs.find(a => a.sport === sp) || {};
    const label = getDynamicSportLabel(sp, sample.sport_tr);
    const cls = currentSportFilter === sp ? 'btn-primary' : 'btn-secondary';
    buttons.push(`<button type="button" onclick="filterActivities('${escapeHtml(sp)}')" id="af-${escapeHtml(sp)}" class="${cls} text-xs px-3 py-1.5">${escapeHtml(label)} (${counts[sp]})</button>`);
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

const ACT_PAGE_SIZE = 7;
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
  if (currentSportFilter === 'all' && (!document.getElementById('actSearchInput') || !document.getElementById('actSearchInput').value.trim())) {
    const titleEl = document.getElementById('activitiesSectionTitle');
    if (titleEl && fullList) titleEl.textContent = `Aktivite Telemetri Günlüğü (${fullList.length} Seans)`;
  }

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
    tr.className = "hover:bg-[var(--bg-subtle)] transition cursor-pointer group text-[11.5px]";
    tr.title = "Aktivite detaylarını ve sensör telemetrisini açmak için tıklayın";
    tr.onclick = () => openActivityModal(a);
    const teDisplay = a.aTE ? `<span class="font-mono text-[10.5px] font-semibold moss-text">A:${Number(a.aTE).toFixed(1)}</span>/<span class="font-mono text-[10.5px] font-semibold crimson-text">An:${Number(a.anTE || 0).toFixed(1)}</span>` : '--';
    const durStr = a.dur_m !== null && a.dur_m !== undefined ? `${Number(a.dur_m).toFixed(0)} dk` : '--';
    const hrStr = `${a.avg_hr ?? '--'}/${a.max_hr ?? '--'}`;
    const spLower = String(a.sport || '').toLowerCase();
    const spBadgeCls = spLower === 'running' ? 'stamp-sky' : (spLower === 'strength_training' ? 'stamp-ochre' : 'stamp-violet');
    tr.innerHTML = `
      <td class="py-1.5 px-2 text-[11px] font-mono font-medium whitespace-nowrap">${escapeHtml(a.date)} <span class="text-[var(--text-muted)]">${escapeHtml(a.time || '')}</span></td>
      <td class="py-1.5 px-2 whitespace-nowrap"><span class="stamp-tag ${spBadgeCls}">${escapeHtml(getDynamicSportLabel(a.sport, a.sport_tr))}</span></td>
      <td class="py-1.5 px-2 text-[11px] font-medium group-hover:text-[var(--accent)] transition max-w-[180px] truncate">${escapeHtml(a.name || '--')}</td>
      <td class="py-1.5 px-2 text-[11px] font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${durStr}</td>
      <td class="py-1.5 px-2 text-[11px] font-mono font-semibold accent-text tabular-nums whitespace-nowrap">${a.dist_km > 0 ? Number(a.dist_km).toFixed(2) + ' km' : '--'}</td>
      <td class="py-1.5 px-2 text-[11px] font-mono font-semibold tabular-nums whitespace-nowrap">${escapeHtml(a.pace_str || '--')}</td>
      <td class="py-1.5 px-2 text-[11px] font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${hrStr}</td>
      <td class="py-1.5 px-2 text-[11px] font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${a.norm_pwr ? a.norm_pwr + ' W' : '--'}</td>
      <td class="py-1.5 px-2 text-[11px] font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${a.cadence ? Number(a.cadence).toFixed(0) : '--'}</td>
      <td class="py-1.5 px-2 text-[11px] font-mono font-semibold tabular-nums whitespace-nowrap">${a.load ? Number(a.load).toFixed(1) : '0'}</td>
      <td class="py-1.5 px-2 whitespace-nowrap">${teDisplay}</td>
      <td class="py-1.5 px-2 text-[11px] font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${a.cal ?? 0} kcal</td>
    `;
    aBody.appendChild(tr);
  });
}

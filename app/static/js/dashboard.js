/* Garmin Athlete IQ — Overview, Sports Guidance, Training Load & Dynamic Activity Log */

function setCalcPreset(kg) {
  const input = document.getElementById('calcTargetInput');
  if (input) {
    input.value = kg;
    runCalculator();
  }
}

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

function renderOverview(data) {
  if (!data) return;
  const curLoad = (data.training_load && data.training_load.current_status) || {};
  const vo2 = data.training_load && data.training_load.vo2max_current ? data.training_load.vo2max_current : (curLoad.vo2max || data.vo2max || '45.4');

  const ifsScore = document.getElementById('inFocusSleepScore');
  if (ifsScore) ifsScore.textContent = data.sleep_score !== undefined ? Math.round(data.sleep_score) : '--';
  const ifsHours = document.getElementById('inFocusSleepHours');
  if (ifsHours && data.sleep_hours !== undefined) {
    const h = Math.floor(data.sleep_hours);
    const m = Math.round((data.sleep_hours - h) * 60);
    ifsHours.textContent = `${h}s ${String(m).padStart(2, '0')}dk`;
  }
  const ifsQ = document.getElementById('inFocusSleepQuality');
  if (ifsQ && data.sleep_score !== undefined) {
    ifsQ.textContent = data.sleep_score >= 80 ? 'Good Quality' : (data.sleep_score >= 65 ? 'Fair Quality' : 'Low Quality');
  }
  const ifsStages = document.getElementById('inFocusSleepStages');
  if (ifsStages) {
    const deepStr = data.deep_hours !== undefined ? `${Number(data.deep_hours).toFixed(1)}s` : '--';
    const remStr = data.rem_hours !== undefined ? `${Number(data.rem_hours).toFixed(1)}s` : '--';
    ifsStages.textContent = `Derin: ${deepStr} · REM: ${remStr}`;
  }

  const ifsStatus = document.getElementById('inFocusTrainingStatus');
  if (ifsStatus && (curLoad.status_tr || data.training_status)) {
    const rawSt = curLoad.status_tr || data.training_status;
    const paren = rawSt.match(/\(([^)]+)\)/);
    ifsStatus.textContent = paren ? paren[1] : rawSt;
  }
  const ifsSub = document.getElementById('inFocusStatusSub');
  if (ifsSub) {
    const acwrVal = curLoad.acwr !== undefined ? Number(curLoad.acwr).toFixed(2) : Number(data.acwr || 1.0).toFixed(2);
    const bal = (data.training_balance || '').split('(')[0].trim() || 'Balanced';
    ifsSub.textContent = `ACWR ${acwrVal} · ${bal}`;
  }
  const ifsVo2 = document.getElementById('inFocusVo2Max');
  if (ifsVo2) ifsVo2.textContent = vo2;

  const hrvWakeEl = document.getElementById('inFocusHrvWakeBb');
  if (hrvWakeEl) {
    const bb = data.bb_wake !== undefined ? data.bb_wake : '--';
    const hrv = data.overnight_hrv !== undefined ? data.overnight_hrv : '--';
    hrvWakeEl.textContent = `Sabah BB: ${bb} · ${hrv} ms`;
  }
  const stressRespEl = document.getElementById('inFocusStressResp');
  if (stressRespEl) {
    const st = data.stress !== undefined ? Math.round(data.stress) : '--';
    const rsp = data.resp_sleep !== undefined ? data.resp_sleep : '--';
    stressRespEl.textContent = `Stres: ${st} · Solunum: ${rsp} br/dk`;
  }

  const kw = document.getElementById('kpi-weight');
  if (kw && data.weight !== undefined) kw.textContent = String(data.weight).replace('.', ',') + ' kg';
  const kwb = document.getElementById('kpi-weight-badge');
  if (kwb && data.total_loss_kg !== undefined) kwb.textContent = `-${String(data.total_loss_kg).replace('.', ',')} kg`;
  const kwbmi = document.getElementById('kpi-weight-bmi');
  if (kwbmi && data.bmi !== undefined) kwbmi.innerHTML = `VKİ: <strong class="text-[var(--text-primary)] font-semibold">${data.bmi}</strong>`;
  const kwtgt = document.getElementById('kpi-weight-target');
  if (kwtgt && data.target_weight !== undefined) kwtgt.textContent = `Hedef: ${String(data.target_weight).replace('.', ',')} kg`;
  const kwbar = document.getElementById('kpi-weight-bar');
  if (kwbar && data.loss_pct !== undefined) {
    kwbar.style.width = `${Math.max(5, Math.min(100, Number(data.loss_pct)))}%`;
  }

  const svgLine = document.getElementById('svgPaceProgressLine');
  const svgDot = document.getElementById('svgPaceProgressDot');
  const svgCur5k = document.getElementById('svgPaceCur5k');
  const svgStartW = document.getElementById('svgPaceStartWeight');
  const svgCurW = document.getElementById('svgPaceCurWeight');
  const svgTgtW = document.getElementById('svgPaceTargetWeight');
  if (svgCur5k && data.latest_5k) {
    const m = String(data.latest_5k).match(/(\d+:\d+)/);
    svgCur5k.textContent = `${m ? m[1] : '5:48'} 5K`;
  }
  if (svgStartW && data.start_weight !== undefined) svgStartW.textContent = `${data.start_weight} kg Başlangıç`;
  if (svgCurW && data.weight !== undefined) svgCurW.textContent = `${data.weight} kg Mevcut`;
  if (svgTgtW && data.target_weight !== undefined) svgTgtW.textContent = `${data.target_weight} kg İdeal`;
  if (svgLine && svgDot && data.start_weight && data.weight && data.target_weight) {
    const denom = Math.max(0.5, Number(data.start_weight) - Number(data.target_weight));
    const ratio = Math.max(0.05, Math.min(1.0, (Number(data.start_weight) - Number(data.weight)) / denom));
    const cx = Math.round(16 + (584 - 16) * ratio);
    svgLine.setAttribute('x2', String(cx));
    svgDot.setAttribute('cx', String(cx));
  }

  const k5 = document.getElementById('kpi-5k');
  const k5p = document.getElementById('kpi-5k-pace');
  if (k5 && data.latest_5k) {
    const parts = data.latest_5k.split(' ');
    k5.textContent = parts[0] || '--:--';
    if (k5p && parts.length > 1) k5p.textContent = parts.slice(1).join(' ');
  }
  const k5cad = document.getElementById('kpi-5k-cad');
  if (k5cad && data.latest_cadence) k5cad.textContent = `${data.latest_cadence} spm`;

  const ke = document.getElementById('kpi-ef');
  const efVal = data.guidance && data.guidance.running && data.guidance.running.efficiency_factor ? data.guidance.running.efficiency_factor : '1.03';
  if (ke) ke.textContent = efVal;
  const kehrv = document.getElementById('kpi-ef-hrv');
  if (kehrv) kehrv.innerHTML = `Gece HRV: <strong class="text-[var(--text-primary)] font-semibold">${data.overnight_hrv ?? '--'} ms</strong>`;
  const kerhr = document.getElementById('kpi-ef-rhr');
  if (kerhr) kerhr.textContent = `RHR: ${data.resting_hr ?? '--'} bpm`;

  const acuteVal = curLoad.acute_load !== undefined ? curLoad.acute_load : (data.acute_load || 279);
  const chronicVal = curLoad.chronic_load !== undefined ? curLoad.chronic_load : (data.chronic_load || 279);
  const acwrNum = curLoad.acwr !== undefined ? Number(curLoad.acwr) : Number(data.acwr || 1.0);
  const tMin = curLoad.tunnel_min ? Math.round(curLoad.tunnel_min) : 223;
  const tMax = curLoad.tunnel_max ? Math.round(curLoad.tunnel_max) : 419;

  const kl = document.getElementById('kpi-load');
  if (kl) kl.textContent = acuteVal;
  const klb = document.getElementById('kpi-acwr-badge');
  if (klb) klb.textContent = `ACWR ${acwrNum.toFixed(2)}`;
  const klt = document.getElementById('kpi-tunnel-text');
  if (klt) {
    const inTunnel = acuteVal >= tMin && acuteVal <= tMax;
    klt.innerHTML = `Tünel: ${tMin}–${tMax} (<strong class="${inTunnel ? 'moss-text' : 'ochre-text'} font-semibold">${inTunnel ? 'Optimal' : 'Takipte'}</strong>)`;
  }
  const klc = document.getElementById('kpi-chronic-text');
  if (klc) klc.textContent = `Kronik: ${chronicVal}`;
  const klbar = document.getElementById('kpi-load-bar');
  if (klbar && tMax > 0) klbar.style.width = `${Math.max(10, Math.min(100, Math.round((acuteVal / tMax) * 100)))}%`;

  const score = data.readiness_score || 77;
  const heroVal = document.getElementById('heroReadinessVal');
  if (heroVal) heroVal.textContent = score + "%";

  const circle = document.getElementById('readinessSvgCircle');
  if (circle) {
    const circumference = 251.32;
    circle.style.strokeDashoffset = (circumference - (circumference * score / 100)).toFixed(1);
    if (score >= 70) {
      circle.setAttribute('class', 'moss-text transition-all duration-1000');
    } else if (score >= 40) {
      circle.setAttribute('class', 'ochre-text transition-all duration-1000');
    } else {
      circle.setAttribute('class', 'crimson-text transition-all duration-1000');
    }
  }

  if (data.recommendation) {
    const db = document.getElementById('decisionBadge');
    if (db) db.textContent = data.recommendation.status.toUpperCase();
    const dt = document.getElementById('decisionTitle');
    if (dt) dt.textContent = data.recommendation.summary;
    const dd = document.getElementById('decisionDetail');
    if (dd) dd.textContent = data.recommendation.suggestion;
  }

  const mBody = document.getElementById('overviewMilestonesBody');
  if (mBody && data.milestones) {
    mBody.innerHTML = '';
    data.milestones.forEach(m => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-[var(--bg-subtle)] transition";
      tr.innerHTML = `
<td class="py-3 px-4 font-semibold">${escapeHtml(m.level)}</td>
<td class="py-3 px-4 font-mono font-semibold accent-text tabular-nums">${m.target_kg} kg <span class="text-[var(--text-muted)] font-normal">(${m.target_bmi})</span></td>
<td class="py-3 px-4 font-mono text-[var(--text-secondary)] tabular-nums">${m.diff_kg} kg</td>
<td class="py-3 px-4 font-mono font-semibold tabular-nums">${m.days_current} Gün <span class="text-[var(--text-muted)] font-normal">(${escapeHtml(m.target_date_current)})</span></td>
<td class="py-3 px-4 font-mono text-[var(--text-secondary)] tabular-nums">${m.days_optimal} Gün <span class="text-[var(--text-muted)]">(${escapeHtml(m.target_date_optimal)})</span></td>
<td class="py-3 px-4 font-mono font-semibold moss-text tabular-nums">${escapeHtml(m.expected_5k)}</td>
<td class="py-3 px-4 font-mono text-[var(--text-secondary)] tabular-nums">${escapeHtml(m.expected_vo2)}</td>
      `;
      mBody.appendChild(tr);
    });
  }

  if (data.biometrics_93d && typeof render93dBiometrics === 'function') {
    render93dBiometrics(data.biometrics_93d);
  }
  const calcMaxLbl = document.getElementById('calcMaxWeightLabel');
  const calcInputEl = document.getElementById('calcTargetInput');
  if (data.weight !== undefined) {
    if (calcMaxLbl) calcMaxLbl.textContent = `${Number(data.weight).toFixed(1)} kg`;
    if (calcInputEl) calcInputEl.max = String(Number(data.weight).toFixed(1));
  }
  const runsBadge = document.getElementById('analyticsRunsBadge');
  if (runsBadge && data.latest_5k) {
    const m = String(data.latest_5k).match(/\(([^)]+)\)/);
    runsBadge.textContent = `${m ? m[1] : data.latest_5k} · ${data.latest_cadence || 162} spm`;
  }
  const slpBadge = document.getElementById('analyticsSleepBadge');
  if (slpBadge) {
    const slpAvg = data.sleep_duration_hours !== undefined ? String(Number(data.sleep_duration_hours).toFixed(2)).replace('.', ',') : '--';
    const slpSc = data.sleep_score !== undefined ? Math.round(data.sleep_score) : '--';
    slpBadge.textContent = `Ort: ${slpAvg} sa · ${slpSc}`;
  }
  renderWeeklyScheduleTable(data.schedule);
  if (data.weekly_quota) renderWeeklyQuotaPanels(data.weekly_quota);
}

async function runCalculator() {
  const targetInput = document.getElementById('calcTargetInput');
  const paceSelect = document.getElementById('calcPaceSelect');
  if (!targetInput || !paceSelect) return;

  const targetKg = parseFloat(targetInput.value);
  const weeklyPace = parseFloat(paceSelect.value);

  document.getElementById('calcTargetVal').textContent = targetKg.toFixed(1) + " kg";
  document.getElementById('calcPaceVal').textContent = "-" + weeklyPace.toFixed(2) + " kg/hf";

  try {
    const res = await fetch('/api/calculator', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_kg: targetKg, weekly_pace_kg: weeklyPace })
    });
    const resData = await res.json();

    document.getElementById('calcDaysResult').textContent = resData.days_needed + " Gün";
    document.getElementById('calcDateResult').textContent = "(" + resData.target_date + ")";
    document.getElementById('calcDiffResult').textContent = "-" + resData.remaining_kg + " kg";
    document.getElementById('calcBmiResult').textContent = resData.target_bmi;
    document.getElementById('calc5kResult').textContent = resData.expected_5k.split(' ')[0];
    document.getElementById('calcVo2Result').textContent = resData.expected_vo2.split(' ')[0];
    document.getElementById('calcDeficitResult').textContent = "~" + Math.round(weeklyPace * 1000) + " kcal";
  } catch (e) {
    console.error(e);
  }
}

function renderSports(sports) {
  const container = document.getElementById('sportsCardsContainer');
  if (!container || !sports) return;
  container.innerHTML = '';
  const iconNames = { running: 'footprints', strength: 'dumbbell', sailing: 'compass', basketball: 'trophy' };
  const coreKeys = ['running', 'strength', 'sailing', 'basketball'].filter(k => sports[k] && typeof sports[k] === 'object');
  const coreList = coreKeys.map(k => ({ key: k, sp: sports[k] }));
  const extraList = Array.isArray(sports.extra_sports)
    ? sports.extra_sports.map(sp => ({ key: sp.sport_key || 'extra', sp }))
    : [];
  const allCards = [...coreList, ...extraList];

  const tabBtn = document.getElementById('sportsCountTabBtn');
  if (tabBtn) tabBtn.textContent = `Branş Özetleri (${allCards.length})`;

  allCards.forEach(({ key, sp }, index) => {
    const card = document.createElement('div');
    const isPrimaryFeatured = index === 0;
    const isExtra = Boolean(sp.is_dynamic_extra);
    card.className = `surface-card p-6 space-y-4 ${isPrimaryFeatured ? 'border-l-[3px] border-l-[var(--accent)]' : ''}`;
    const iconName = iconNames[key] || getSportLucideIcon(sp.sport_key || sp.name);

    card.innerHTML = `
      <div class="space-y-2">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-3">
            <div class="icon-box w-9 h-9 shrink-0">${lucideSvg(iconName, 'w-4 h-4')}</div>
            <h4 class="font-editorial text-lg font-medium tracking-tight leading-snug">${escapeHtml(sp.name)}</h4>
          </div>
          <span class="stamp-tag ${isExtra ? 'stamp-moss' : 'stamp-accent'}">${escapeHtml(sp.schedule_status || sp.cadence || 'Aktif')}</span>
        </div>
        <p class="font-mono text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(sp.stats_summary || sp.current_status || sp.current_pace || '')}</p>
      </div>

      <div class="text-xs text-[var(--text-secondary)] space-y-1.5 tint-panel p-4 leading-relaxed">
        <p class="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-primary)] mb-1">Gelişim &amp; Yük Stratejisi</p>
        ${(sp.how_to_improve || []).map(item => `<p class="flex items-start gap-2"><span class="accent-text mt-0.5">·</span><span>${escapeHtml(item)}</span></p>`).join('')}
      </div>

      ${sp.last_workout ? `
      <div class="text-xs tint-moss-panel p-3.5 space-y-1.5">
        <div class="flex items-center justify-between gap-2">
          <span class="font-semibold">${escapeHtml(sp.last_workout.date)}</span>
          <span class="stamp-tag stamp-moss">${escapeHtml(sp.last_workout.title)}</span>
        </div>
        <p class="text-[11px] moss-text leading-relaxed">${sp.last_workout.exercises ? sp.last_workout.exercises.map(escapeHtml).join(' · ') : ''}</p>
      </div>` : ''}

      <div class="border-t border-[var(--border-subtle)] pt-4 space-y-2.5">
        <p class="font-mono text-[10px] uppercase tracking-wider font-semibold text-[var(--text-secondary)] flex items-center gap-1.5">
          ${lucideSvg('calendar', 'w-3.5 h-3.5 accent-text')}
          <span>Bu Hafta Kalan / Sıradaki Seçenekler</span>
        </p>
        ${sp.upcoming_sessions && sp.upcoming_sessions.length > 0 ? sp.upcoming_sessions.map(sess => `
          <div class="tint-panel p-3 text-xs space-y-1">
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <span class="font-semibold">${escapeHtml(sess.day)}</span>
              <span class="stamp-tag stamp-accent">${escapeHtml(sess.type || 'Seans')}</span>
            </div>
            <p class="font-medium text-[12px]">${escapeHtml(sess.title)} <span class="font-mono text-[11px] text-[var(--text-muted)]">(${escapeHtml(sess.duration || '')})</span></p>
            <p class="text-[11px] text-[var(--text-secondary)] leading-relaxed">${escapeHtml(sess.details || '')}</p>
          </div>
        `).join('') : (sp.next_workout ? `
          <div class="text-xs tint-panel p-3">
            <p class="font-semibold">${escapeHtml(sp.next_workout.day)}: ${escapeHtml(sp.next_workout.title)} <span class="font-mono text-[var(--text-muted)]">(${escapeHtml(sp.next_workout.duration || '')})</span></p>
            <p class="text-[11px] text-[var(--text-secondary)] mt-1">${escapeHtml(sp.next_workout.details || sp.next_workout.hydration_plan || (sp.next_workout.exercises ? sp.next_workout.exercises.join(', ') : ''))}</p>
          </div>
        ` : '')}
      </div>
    `;
    container.appendChild(card);
  });
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
      const exSummary = (sess.exercises || []).map(ex => {
        const setStr = (ex.sets || []).map(s => `${s.reps}x${s.weight_kg}kg`).join(', ');
        return `<div class="mb-1"><strong class="font-semibold">${escapeHtml(ex.name)}</strong> <span class="font-mono text-[var(--text-muted)] text-[10px]">(${(ex.sets || []).length} set)</span>: <span class="font-mono accent-text font-medium">${escapeHtml(setStr)}</span></div>`;
      }).join('');

      tr.innerHTML = `
<td class="py-3 px-4 font-mono font-medium whitespace-nowrap">${escapeHtml(sess.date)} <span class="text-[var(--text-muted)] text-[11px]">${escapeHtml(sess.time || '')}</span></td>
<td class="py-3 px-4 font-semibold ${sess.workout_type === 'Workout A' ? 'accent-text' : ''}">${escapeHtml(sess.workout_type)}</td>
<td class="py-3 px-4 font-mono text-[var(--text-secondary)] whitespace-nowrap">${sess.duration_min} dk · ${sess.calories} kcal</td>
<td class="py-3 px-4 font-mono font-semibold whitespace-nowrap">${(sess.total_volume_kg / 1000.0).toFixed(2)} Ton</td>
<td class="py-3 px-4 text-xs">${exSummary}</td>
      `;
      tableBody.appendChild(tr);
    });
  }
  if (typeof refreshIcons === 'function') refreshIcons();
}

function renderSameDaySequence(seqList) {
  const sBody = document.getElementById('sameDayTableBody');
  if (!sBody || !Array.isArray(seqList)) return;
  sBody.innerHTML = '';
  seqList.forEach(item => {
    const tr = document.createElement('tr');
    tr.className = item.is_recommended
      ? "hover:bg-[var(--bg-subtle)] transition"
      : "bg-[var(--crimson-soft)] hover:bg-[var(--bg-subtle)] transition";
    tr.innerHTML = `
      <td class="py-3 px-4 font-mono font-medium">${escapeHtml(item.date)}</td>
      <td class="py-3 px-4 font-semibold ${item.is_recommended ? 'accent-text' : 'crimson-text'}">${escapeHtml(item.sequence)}</td>
      <td class="py-3 px-4 text-[var(--text-secondary)]">${escapeHtml(item.strength_info)}</td>
      <td class="py-3 px-4 font-mono font-medium">${escapeHtml(item.run_info)}</td>
      <td class="py-3 px-4 font-mono font-semibold ${item.is_recommended ? '' : 'crimson-text'}">${escapeHtml(item.run_hr)}</td>
      <td class="py-3 px-4 font-mono font-semibold ${item.is_recommended ? 'moss-text' : 'crimson-text'}">${escapeHtml(item.z4_pct)}</td>
      <td class="py-3 px-4 text-[var(--text-secondary)]">${escapeHtml(item.result)}</td>
    `;
    sBody.appendChild(tr);
  });
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

  renderActivities(filtered, false);
}

function filterActivities(sport) {
  currentSportFilter = sport;
  if (globalActivities) renderActivityFilters(globalActivities);
  const searchInput = document.getElementById('actSearchInput');
  const term = searchInput ? searchInput.value : '';
  searchActivities(term);
}

function renderActivities(acts, rebuildFilters = true) {
  if (rebuildFilters && Array.isArray(acts)) {
    renderActivityFilters(acts);
  }
  updateActivityStatsSummary(acts);
  if (currentSportFilter === 'all' && (!document.getElementById('actSearchInput') || !document.getElementById('actSearchInput').value.trim())) {
    const titleEl = document.getElementById('activitiesSectionTitle');
    if (titleEl && acts) titleEl.textContent = `Aktivite Telemetri Günlüğü (${acts.length} Seans)`;
  }
  const aBody = document.getElementById('activitiesTableBody');
  if (!aBody) return;
  aBody.innerHTML = '';
  (acts || []).forEach((a, idx) => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-[var(--bg-subtle)] transition cursor-pointer group text-[12px]";
    tr.title = "Aktivite detaylarını ve sensör telemetrisini açmak için tıklayın";
    tr.onclick = () => openActivityModal(a);
    const teDisplay = a.aTE ? `<span class="font-mono text-[11px] font-semibold moss-text">A:${Number(a.aTE).toFixed(1)}</span> / <span class="font-mono text-[11px] font-semibold crimson-text">An:${Number(a.anTE || 0).toFixed(1)}</span>` : '--';
    const durStr = a.dur_m !== null && a.dur_m !== undefined ? `${Number(a.dur_m).toFixed(0)} dk` : '--';
    const hrStr = `${a.avg_hr ?? '--'} / ${a.max_hr ?? '--'}`;
    tr.innerHTML = `
      <td class="py-2.5 px-3 font-mono font-medium whitespace-nowrap">${escapeHtml(a.date)} <span class="text-[var(--text-muted)]">${escapeHtml(a.time || '')}</span></td>
      <td class="py-2.5 px-3 whitespace-nowrap"><span class="stamp-tag">${escapeHtml(getDynamicSportLabel(a.sport, a.sport_tr))}</span></td>
      <td class="py-2.5 px-3 font-medium group-hover:text-[var(--accent)] transition">${escapeHtml(a.name || '--')}</td>
      <td class="py-2.5 px-3 font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${durStr}</td>
      <td class="py-2.5 px-3 font-mono font-semibold accent-text tabular-nums whitespace-nowrap">${a.dist_km > 0 ? Number(a.dist_km).toFixed(2) + ' km' : '--'}</td>
      <td class="py-2.5 px-3 font-mono font-semibold tabular-nums whitespace-nowrap">${escapeHtml(a.pace_str || '--')}</td>
      <td class="py-2.5 px-3 font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${hrStr}</td>
      <td class="py-2.5 px-3 font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${a.norm_pwr ? a.norm_pwr + ' W' : '--'}</td>
      <td class="py-2.5 px-3 font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${a.cadence ? Number(a.cadence).toFixed(0) : '--'}</td>
      <td class="py-2.5 px-3 font-mono font-semibold tabular-nums whitespace-nowrap">${a.load ? Number(a.load).toFixed(1) : '0'}</td>
      <td class="py-2.5 px-3 whitespace-nowrap">${teDisplay}</td>
      <td class="py-2.5 px-3 font-mono text-[var(--text-secondary)] tabular-nums whitespace-nowrap">${a.cal ?? 0} kcal${a.water_ml ? ' (' + (a.water_ml / 1000).toFixed(1) + 'L)' : ''}</td>
    `;
    aBody.appendChild(tr);
  });
}

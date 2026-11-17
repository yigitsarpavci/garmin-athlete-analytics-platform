/* Garmin Athlete IQ — Dashboard Sections, Bento Telemetry & Renderers */

function renderWeeklyScheduleTable(scheduleList) {
  const sBody = document.getElementById('overviewScheduleBody');
  if (!sBody || !scheduleList) return;
  sBody.innerHTML = '';
  scheduleList.forEach((s, idx) => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition cursor-pointer group";
    tr.title = "Günün detaylı antrenman ve beslenme reçetesine gitmek için tıklayın";
    tr.onclick = () => {
      if (typeof setTab === 'function') setTab('plan');
      if (typeof setSubTab === 'function') setSubTab('plan', 'protocols');
      let targetIdx = idx;
      if (typeof cachedDailyProtocols !== 'undefined' && Array.isArray(cachedDailyProtocols) && cachedDailyProtocols.length) {
        const dayText = (s.day || '').toLowerCase();
        const dayMap = [
          ['pzt', 'monday'], ['sal', 'tuesday'], ['çar', 'wednesday'],
          ['per', 'thursday'], ['cum', 'friday'], ['cmt', 'saturday'], ['paz', 'sunday']
        ];
        const matched = dayMap.find(([trCode]) => dayText.includes(trCode));
        if (matched) {
          const found = cachedDailyProtocols.findIndex(p => p.day_code === matched[1]);
          if (found >= 0) targetIdx = found;
        }
      }
      if (typeof selectProtocolDay === 'function') selectProtocolDay(targetIdx);
      const targetSec = document.getElementById('dailyProtocolsSection');
      if (targetSec) {
        targetSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    };
    const isDone = (s.secondary || '').includes('TAMAMLANDI');
    tr.innerHTML = `
      <td class="py-3 px-4 font-semibold text-zinc-950 dark:text-zinc-50 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition">
        <div class="flex items-center justify-between gap-2">
          <span>${s.day}</span>
          ${lucideSvg('arrow-right', 'w-3.5 h-3.5 text-indigo-500 opacity-0 group-hover:opacity-100 transition')}
        </div>
      </td>
      <td class="py-3 px-4 font-medium text-zinc-900 dark:text-zinc-100">${s.primary}</td>
      <td class="py-3 px-4 ${isDone ? 'font-mono text-emerald-700 dark:text-emerald-400 font-medium' : 'text-zinc-500 dark:text-zinc-400'}">${s.secondary}</td>
      <td class="py-3 px-4 font-mono text-[11px] font-medium text-indigo-600 dark:text-indigo-400 whitespace-nowrap">${s.target}</td>
      <td class="py-3 px-4 font-mono text-[11px] text-zinc-600 dark:text-zinc-400 whitespace-nowrap">${s.calories}</td>
      <td class="py-3 px-4 font-mono text-[11px] text-zinc-600 dark:text-zinc-400">${s.macro}</td>
    `;
    sBody.appendChild(tr);
  });
  if (typeof refreshIcons === 'function') refreshIcons();
}

function setCalcPreset(kg) {
  const input = document.getElementById('calcTargetInput');
  if (input) {
    input.value = kg;
    runCalculator();
  }
}

function renderOverview(data) {
  if (!data) return;
  const curLoad = (data.training_load && data.training_load.current_status) || {};
  const vo2 = data.training_load && data.training_load.vo2max_current ? data.training_load.vo2max_current : (curLoad.vo2max || '45.4');

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
  const ifsRhrHrv = document.getElementById('inFocusSleepRhrHrv');
  if (ifsRhrHrv) ifsRhrHrv.textContent = `RHR: ${data.resting_hr ?? '--'} bpm · HRV: ${data.overnight_hrv ?? '--'} ms`;

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
    ifsSub.textContent = `ACWR ${acwrVal} · ${bal} HRV`;
  }
  const ifsVo2 = document.getElementById('inFocusVo2Max');
  if (ifsVo2) ifsVo2.textContent = vo2;

  const kw = document.getElementById('kpi-weight');
  if (kw && data.weight !== undefined) kw.textContent = String(data.weight).replace('.', ',') + ' kg';
  const kwb = document.getElementById('kpi-weight-badge');
  if (kwb && data.total_loss_kg !== undefined) kwb.textContent = `-${String(data.total_loss_kg).replace('.', ',')} kg`;
  const kwbmi = document.getElementById('kpi-weight-bmi');
  if (kwbmi && data.bmi !== undefined) kwbmi.innerHTML = `VKİ: <strong class="text-zinc-900 dark:text-zinc-200 font-semibold">${data.bmi}</strong>`;

  const k5 = document.getElementById('kpi-5k');
  const k5p = document.getElementById('kpi-5k-pace');
  if (k5 && data.latest_5k) {
    const parts = data.latest_5k.split(' ');
    k5.textContent = parts[0] || '--:--';
    if (k5p && parts.length > 1) k5p.textContent = parts.slice(1).join(' ');
  }

  const ke = document.getElementById('kpi-ef');
  const efVal = data.guidance && data.guidance.running && data.guidance.running.efficiency_factor ? data.guidance.running.efficiency_factor : '1.03';
  if (ke) ke.textContent = efVal;
  const kehrv = document.getElementById('kpi-ef-hrv');
  if (kehrv) kehrv.innerHTML = `Gece HRV: <strong class="text-zinc-900 dark:text-zinc-200 font-semibold">${data.overnight_hrv ?? '--'} ms</strong>`;
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
  if (klt) klt.innerHTML = `Tünel: ${tMin}–${tMax} (<strong class="text-emerald-600 dark:text-emerald-400 font-semibold">Optimal</strong>)`;
  const klc = document.getElementById('kpi-chronic-text');
  if (klc) klc.textContent = `Kronik: ${chronicVal}`;

  const score = data.readiness_score || 77;
  const heroVal = document.getElementById('heroReadinessVal');
  if (heroVal) heroVal.textContent = score + "%";

  const circle = document.getElementById('readinessSvgCircle');
  if (circle) {
    const circumference = 251.32;
    circle.style.strokeDashoffset = (circumference - (circumference * score / 100)).toFixed(1);
    if (score >= 70) {
      circle.setAttribute('class', 'text-indigo-600 dark:text-indigo-400 transition-all duration-1000');
    } else if (score >= 40) {
      circle.setAttribute('class', 'text-amber-500 transition-all duration-1000');
    } else {
      circle.setAttribute('class', 'text-rose-500 transition-all duration-1000');
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
      tr.className = "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition";
      tr.innerHTML = `
<td class="py-3 px-4 font-semibold text-zinc-950 dark:text-zinc-50">${m.level}</td>
<td class="py-3 px-4 font-mono font-semibold text-indigo-600 dark:text-indigo-400 tabular-nums">${m.target_kg} kg <span class="text-zinc-400 font-normal">(${m.target_bmi})</span></td>
<td class="py-3 px-4 font-mono text-zinc-500 dark:text-zinc-400 tabular-nums">${m.diff_kg} kg</td>
<td class="py-3 px-4 font-mono font-semibold text-zinc-900 dark:text-zinc-100 tabular-nums">${m.days_current} Gün <span class="text-zinc-400 font-normal">(${m.target_date_current})</span></td>
<td class="py-3 px-4 font-mono text-zinc-600 dark:text-zinc-300 tabular-nums">${m.days_optimal} Gün <span class="text-zinc-400">(${m.target_date_optimal})</span></td>
<td class="py-3 px-4 font-mono font-semibold text-emerald-600 dark:text-emerald-400 tabular-nums">${m.expected_5k}</td>
<td class="py-3 px-4 font-mono text-zinc-700 dark:text-zinc-300 tabular-nums">${m.expected_vo2}</td>
          `;
      mBody.appendChild(tr);
    });
  }

  renderWeeklyScheduleTable(data.schedule);
}

async function runCalculator() {
  const targetKg = parseFloat(document.getElementById('calcTargetInput').value);
  const weeklyPace = parseFloat(document.getElementById('calcPaceSelect').value);

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
  if (!container) return;
  container.innerHTML = '';
  const iconNames = { running: 'footprints', strength: 'dumbbell', sailing: 'compass', basketball: 'trophy' };
  const keys = Object.keys(sports);

  keys.forEach((key, index) => {
    const sp = sports[key];
    const card = document.createElement('div');
    const isPrimaryFeatured = index === 0;
    card.className = `surface-card rounded-2xl p-6 space-y-4 ${isPrimaryFeatured ? 'md:col-span-1' : ''}`;
    card.innerHTML = `
          <div class="flex flex-wrap items-start justify-between gap-2.5">
            <div class="flex items-center gap-3 min-w-0 flex-1">
              <div class="icon-box w-9 h-9">${lucideSvg(iconNames[key] || 'zap', 'w-4 h-4')}</div>
              <div class="min-w-0">
                <h4 class="text-sm font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">${sp.name}</h4>
                <p class="font-mono text-[11px] text-zinc-500 dark:text-zinc-400 break-words mt-0.5">${sp.stats_summary || sp.current_pace || ''}</p>
              </div>
            </div>
            <span class="font-mono text-[10px] font-medium text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/10 px-2.5 py-1 rounded-md border border-indigo-200/70 dark:border-indigo-500/20 max-w-full whitespace-normal">${sp.schedule_status || sp.cadence || 'Aktif'}</span>
          </div>

          <div class="text-xs text-zinc-600 dark:text-zinc-400 space-y-1.5 bg-zinc-50 dark:bg-zinc-950/60 p-4 rounded-xl border border-zinc-200/70 dark:border-zinc-800/80 leading-relaxed">
            <p class="font-semibold text-zinc-900 dark:text-zinc-200 mb-1">Gelişim Stratejisi</p>
            ${sp.how_to_improve.map(item => `<p class="flex items-start gap-2"><span class="text-indigo-500 mt-0.5">·</span><span>${item}</span></p>`).join('')}
          </div>

          ${sp.last_workout ? `
          <div class="text-xs bg-emerald-500/5 dark:bg-emerald-500/10 p-3.5 rounded-xl border border-emerald-500/20 space-y-1.5">
            <div class="flex items-center justify-between gap-2">
              <span class="font-semibold text-zinc-900 dark:text-zinc-100">${sp.last_workout.date}</span>
              <span class="font-mono text-[10px] bg-emerald-600 text-white font-semibold px-2 py-0.5 rounded-md">${sp.last_workout.title}</span>
            </div>
            <p class="text-[11px] text-emerald-800 dark:text-emerald-300 leading-relaxed">${sp.last_workout.exercises ? sp.last_workout.exercises.join(' · ') : ''}</p>
          </div>` : ''}

          <div class="border-t border-zinc-200/70 dark:border-zinc-800/80 pt-4 space-y-2.5">
            <p class="font-mono text-[10px] uppercase tracking-wider font-semibold text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
              ${lucideSvg('calendar', 'w-3.5 h-3.5 text-indigo-500')}
              <span>Sonraki Seanslar</span>
            </p>
            ${sp.upcoming_sessions && sp.upcoming_sessions.length > 0 ? sp.upcoming_sessions.map(sess => `
              <div class="bg-zinc-50/90 dark:bg-zinc-950/50 p-3 rounded-xl border border-zinc-200/70 dark:border-zinc-800 text-xs space-y-1">
                <div class="flex items-center justify-between gap-2">
                  <span class="font-semibold text-zinc-900 dark:text-zinc-100">${sess.day}</span>
                  <span class="font-mono text-[10px] text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-200/60 dark:border-indigo-500/20">${sess.type || 'Seans'}</span>
                </div>
                <p class="text-zinc-800 dark:text-zinc-200 font-medium text-[12px]">${sess.title} <span class="font-mono text-[11px] text-zinc-400">(${sess.duration || ''})</span></p>
                <p class="text-[11px] text-zinc-500 dark:text-zinc-400 leading-relaxed">${sess.details || ''}</p>
              </div>
            `).join('') : `
              <div class="text-xs text-zinc-700 dark:text-zinc-300 bg-zinc-50/70 dark:bg-zinc-950/50 p-3 rounded-xl border border-zinc-200/70 dark:border-zinc-800">
                <p class="font-semibold text-zinc-900 dark:text-zinc-100">${sp.next_workout.day}: ${sp.next_workout.title} <span class="font-mono text-zinc-400">(${sp.next_workout.duration || ''})</span></p>
                <p class="text-[11px] text-zinc-500 dark:text-zinc-400 mt-1">${sp.next_workout.details || sp.next_workout.hydration_plan || (sp.next_workout.exercises ? sp.next_workout.exercises.join(', ') : '')}</p>
              </div>
            `}
          </div>
        `;
    container.appendChild(card);
  });
  if (typeof refreshIcons === 'function') refreshIcons();
}

function renderGymHistory(gym) {
  if (!gym) return;
  const progGrid = document.getElementById('gymProgressionGrid');
  if (progGrid && gym.progression) {
    progGrid.innerHTML = '';
    const coreKeys = ['squat', 'bench', 'row', 'ohp', 'deadlift', 'lat_pulldown', 'lateral_raise', 'shrug'];
    coreKeys.forEach(k => {
      const item = gym.progression[k];
      if (!item) return;
      const div = document.createElement('div');
      div.className = "bg-zinc-50 dark:bg-zinc-950/60 p-3.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-1.5";
      div.innerHTML = `
<div class="flex items-center justify-between gap-2">
  <span class="font-semibold text-zinc-900 dark:text-zinc-100 text-xs">${item.name}</span>
  <span class="font-mono text-[10px] font-semibold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200/70 dark:border-indigo-500/20 px-1.5 py-0.5 rounded">${item.delta}</span>
</div>
<p class="font-mono text-[11px] text-zinc-500 dark:text-zinc-400 leading-snug" title="${item.history.join(' → ')}">${item.history.slice(-2).join(' → ')}</p>
<p class="font-mono text-[11px] font-medium text-emerald-700 dark:text-emerald-400 pt-1.5 border-t border-zinc-200/70 dark:border-zinc-800 flex items-center gap-1">${lucideSvg('target', 'w-3 h-3 shrink-0')}<span>Hedef: ${item.next_target}</span></p>
          `;
      progGrid.appendChild(div);
    });
  }

  const tableBody = document.getElementById('gymHistoryTableBody');
  if (tableBody && gym.sessions) {
    tableBody.innerHTML = '';
    gym.sessions.forEach(sess => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition";
      const exSummary = sess.exercises.map(ex => {
        const setStr = ex.sets.map(s => `${s.reps}x${s.weight_kg}kg`).join(', ');
        return `<div class="mb-1"><strong class="text-zinc-900 dark:text-zinc-100 font-semibold">${ex.name}</strong> <span class="font-mono text-zinc-400 text-[10px]">(${ex.sets.length} set)</span>: <span class="font-mono text-indigo-600 dark:text-indigo-400 font-medium">${setStr}</span></div>`;
      }).join('');

      tr.innerHTML = `
<td class="py-3 px-4 font-mono font-medium text-zinc-900 dark:text-zinc-100 whitespace-nowrap">${sess.date} <span class="text-zinc-400 text-[11px]">${sess.time || ''}</span></td>
<td class="py-3 px-4 font-semibold ${sess.workout_type === 'Workout A' ? 'text-indigo-600 dark:text-indigo-400' : 'text-zinc-900 dark:text-zinc-100'}">${sess.workout_type}</td>
<td class="py-3 px-4 font-mono text-zinc-600 dark:text-zinc-400 whitespace-nowrap">${sess.duration_min} dk · ${sess.calories} kcal</td>
<td class="py-3 px-4 font-mono font-semibold text-zinc-950 dark:text-zinc-50 whitespace-nowrap">${(sess.total_volume_kg / 1000.0).toFixed(2)} Ton</td>
<td class="py-3 px-4 text-xs">${exSummary}</td>
          `;
      tableBody.appendChild(tr);
    });
  }
  if (typeof refreshIcons === 'function') refreshIcons();
}

function renderSameDaySequence(seqList) {
  const sBody = document.getElementById('sameDayTableBody');
  if (!sBody) return;
  sBody.innerHTML = '';
  seqList.forEach(item => {
    const tr = document.createElement('tr');
    tr.className = item.is_recommended
      ? "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition"
      : "bg-rose-500/5 hover:bg-rose-500/10 transition";
    tr.innerHTML = `
          <td class="py-3 px-4 font-mono font-medium text-zinc-900 dark:text-zinc-100">${item.date}</td>
          <td class="py-3 px-4 font-semibold ${item.is_recommended ? 'text-indigo-600 dark:text-indigo-400' : 'text-rose-600 dark:text-rose-400'}">${item.sequence}</td>
          <td class="py-3 px-4 text-zinc-600 dark:text-zinc-400">${item.strength_info}</td>
          <td class="py-3 px-4 font-mono font-medium text-zinc-800 dark:text-zinc-200">${item.run_info}</td>
          <td class="py-3 px-4 font-mono font-semibold ${item.is_recommended ? 'text-zinc-800 dark:text-zinc-200' : 'text-rose-600 dark:text-rose-400'}">${item.run_hr}</td>
          <td class="py-3 px-4 font-mono font-semibold ${item.is_recommended ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}">${item.z4_pct}</td>
          <td class="py-3 px-4 text-zinc-600 dark:text-zinc-400">${item.result}</td>
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
    document.getElementById('tl-acwr').textContent = cur.acwr.toFixed(2);
    const badge = document.getElementById('tl-acwr-badge');
    if (cur.acwr >= 0.8 && cur.acwr <= 1.3) {
      badge.textContent = "SWEET SPOT";
      badge.className = "font-mono text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md";
    } else if (cur.acwr > 1.5) {
      badge.textContent = "AŞIRI YÜK";
      badge.className = "font-mono text-[10px] font-semibold text-rose-700 dark:text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded-md";
    } else {
      badge.textContent = cur.acwr_status;
      badge.className = "font-mono text-[10px] font-semibold text-amber-700 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-md";
    }
  }

  if (foc) {
    document.getElementById('tl-focus-low').textContent = foc.aerobic_low.actual + " birim";
    document.getElementById('tl-focus-high').textContent = foc.aerobic_high.actual + " birim";
    document.getElementById('tl-focus-anaerobic').textContent = foc.anaerobic.actual + " birim";
  }

  const wBody = document.getElementById('trainingLoadWeeklyBody');
  if (wBody && tl.weekly_progression) {
    wBody.innerHTML = '';
    tl.weekly_progression.forEach(w => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition";
      const acwrColor = (w.acwr >= 0.8 && w.acwr <= 1.3) ? "text-emerald-600 dark:text-emerald-400 font-semibold" : ((w.acwr > 1.5) ? "text-rose-600 dark:text-rose-400 font-semibold" : "text-amber-600 dark:text-amber-400 font-semibold");
      tr.innerHTML = `
<td class="py-2.5 px-3 font-mono font-medium text-zinc-900 dark:text-zinc-100 whitespace-nowrap">${w.date}</td>
<td class="py-2.5 px-3 font-semibold text-indigo-600 dark:text-indigo-400">${w.status_tr}</td>
<td class="py-2.5 px-3 font-mono font-semibold text-zinc-900 dark:text-zinc-100 tabular-nums">${w.acute_load}</td>
<td class="py-2.5 px-3 font-mono text-zinc-500 dark:text-zinc-400 tabular-nums">${w.chronic_load}</td>
<td class="py-2.5 px-3 font-mono ${acwrColor} tabular-nums">${w.acwr.toFixed(2)}</td>
<td class="py-2.5 px-3 text-zinc-500 dark:text-zinc-400">${w.acwr_status}</td>
<td class="py-2.5 px-3 font-mono text-indigo-600 dark:text-indigo-400 tabular-nums">${w.low_aero}</td>
<td class="py-2.5 px-3 font-mono text-amber-600 dark:text-amber-400 tabular-nums">${w.high_aero}</td>
<td class="py-2.5 px-3 font-mono text-rose-600 dark:text-rose-400 tabular-nums">${w.anaerobic}</td>
<td class="py-2.5 px-3 font-medium text-zinc-800 dark:text-zinc-200">${w.balance_tr}</td>
          `;
      wBody.appendChild(tr);
    });
  }

  const tBody = document.getElementById('trainingLoadTopActsBody');
  if (tBody && tl.top_load_acts) {
    tBody.innerHTML = '';
    const spNames = { running: 'Koşu', sailing_v2: 'Yelken', resort_skiing: 'Kayak', strength_training: 'Kuvvet', basketball: 'Basketbol' };
    tl.top_load_acts.forEach(a => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition cursor-pointer group";
      tr.title = "Aktivite telemetrisini incelemek için tıklayın";
      tr.onclick = () => openActivityModal(a);
      tr.innerHTML = `
<td class="py-3 px-4 font-mono font-medium text-zinc-900 dark:text-zinc-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition">
  <div class="flex items-center justify-between gap-2">
    <span>${a.date}</span>
    ${lucideSvg('arrow-up-right', 'w-3.5 h-3.5 text-indigo-500 opacity-0 group-hover:opacity-100 transition')}
  </div>
</td>
<td class="py-3 px-4 font-medium text-zinc-800 dark:text-zinc-200">${spNames[a.sport] || a.sport}</td>
<td class="py-3 px-4 text-zinc-600 dark:text-zinc-300 max-w-[180px] truncate">${a.name}</td>
<td class="py-3 px-4 font-mono text-zinc-500 dark:text-zinc-400">${a.dur_m} dk</td>
<td class="py-3 px-4 font-mono font-semibold text-indigo-600 dark:text-indigo-400">${a.load}</td>
<td class="py-3 px-4 font-mono font-semibold text-emerald-600 dark:text-emerald-400">${a.aTE ? a.aTE.toFixed(1) : '--'}</td>
<td class="py-3 px-4 font-mono font-semibold text-rose-600 dark:text-rose-400">${a.anTE ? a.anTE.toFixed(1) : '--'}</td>
<td class="py-3 px-4"><span class="font-mono px-2 py-0.5 rounded-md text-[10px] font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700">${a.te_label}</span></td>
          `;
      tBody.appendChild(tr);
    });
  }
  if (typeof refreshIcons === 'function') refreshIcons();
}

// AKTİVİTELER
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
    if (currentSportFilter !== 'all') {
      if (currentSportFilter === 'walking') {
        if (a.sport === 'running' || a.sport === 'strength_training' || a.sport === 'sailing_v2' || a.sport === 'basketball') {
          return false;
        }
      } else if (a.sport !== currentSportFilter) {
        return false;
      }
    }

    if (!q) return true;

    const spMap = {
      running: 'koşu run',
      sailing_v2: 'yelken sail',
      strength_training: 'kuvvet gym fitness weight salon',
      basketball: 'basketbol basketball',
      hiking: 'doga yuruyusu hike',
      walking: 'yuruyus walk'
    };
    const sportText = spMap[a.sport] || a.sport || '';
    const searchable = normalizeSearchText(`${a.name || ''} ${a.date || ''} ${a.sport || ''} ${sportText} ${a.pace_str || ''} ${a.te_label || ''}`);
    return searchable.includes(q);
  });

  renderActivities(filtered);
}

function filterActivities(sport) {
  currentSportFilter = sport;
  const filterKeys = ['all', 'running', 'strength_training', 'sailing_v2', 'basketball', 'walking'];
  filterKeys.forEach(s => {
    const btn = document.getElementById('af-' + s);
    if (btn) {
      if (s === sport) {
        btn.className = "px-3 py-1.5 rounded-lg font-semibold bg-indigo-600 text-white transition-all duration-200 active:scale-[0.98] inline-flex items-center gap-1.5";
      } else {
        btn.className = "px-3 py-1.5 rounded-lg font-medium text-zinc-600 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/70 dark:border-zinc-700/70 hover:border-zinc-400 dark:hover:border-zinc-600 transition-all duration-200 active:scale-[0.98] inline-flex items-center gap-1.5";
      }
    }
  });

  const searchInput = document.getElementById('actSearchInput');
  const term = searchInput ? searchInput.value : '';
  searchActivities(term);
}

function renderActivities(acts) {
  updateActivityStatsSummary(acts);
  if (currentSportFilter === 'all' && (!document.getElementById('actSearchInput') || !document.getElementById('actSearchInput').value.trim())) {
    const titleEl = document.getElementById('activitiesSectionTitle');
    if (titleEl && acts) titleEl.textContent = `Aktivite Telemetri Günlüğü (${acts.length} Seans)`;
    const allBtn = document.getElementById('af-all');
    if (allBtn && acts) allBtn.textContent = `Tümü (${acts.length})`;
  }
  const aBody = document.getElementById('activitiesTableBody');
  if (!aBody) return;
  aBody.innerHTML = '';
  (acts || []).forEach(a => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition cursor-pointer group text-[12px]";
    tr.title = "Aktivite detaylarını ve sensör telemetrisini açmak için tıklayın";
    tr.onclick = () => openActivityModal(a);
    const spNames = { running: 'Koşu', sailing_v2: 'Yelken', strength_training: 'Kuvvet', basketball: 'Basketbol', hiking: 'Doğa Yürüyüşü', rowing_v2: 'Kürek', walking: 'Yürüyüş' };
    const teDisplay = a.aTE ? `<span class="font-mono text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">A:${a.aTE.toFixed(1)}</span> / <span class="font-mono text-[11px] font-semibold text-rose-600 dark:text-rose-400">An:${(a.anTE || 0).toFixed(1)}</span>` : '--';
    tr.innerHTML = `
          <td class="py-2.5 px-3 font-mono font-medium text-zinc-900 dark:text-zinc-100 whitespace-nowrap">${a.date} <span class="text-zinc-400 dark:text-zinc-500">${a.time || ''}</span></td>
          <td class="py-2.5 px-3 whitespace-nowrap"><span class="font-mono px-2 py-0.5 rounded-md text-[10px] font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200/80 dark:border-zinc-700">${spNames[a.sport] || a.sport}</span></td>
          <td class="py-2.5 px-3 font-medium text-zinc-900 dark:text-zinc-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition">${a.name || '--'}</td>
          <td class="py-2.5 px-3 font-mono text-zinc-600 dark:text-zinc-300 tabular-nums whitespace-nowrap">${a.dur_m.toFixed(0)} dk</td>
          <td class="py-2.5 px-3 font-mono font-semibold text-indigo-600 dark:text-indigo-400 tabular-nums whitespace-nowrap">${a.dist_km > 0 ? a.dist_km.toFixed(2) + ' km' : '--'}</td>
          <td class="py-2.5 px-3 font-mono font-semibold text-zinc-800 dark:text-zinc-200 tabular-nums whitespace-nowrap">${a.pace_str || '--'}</td>
          <td class="py-2.5 px-3 font-mono text-zinc-600 dark:text-zinc-300 tabular-nums whitespace-nowrap">${a.avg_hr} / ${a.max_hr}</td>
          <td class="py-2.5 px-3 font-mono text-zinc-500 dark:text-zinc-400 tabular-nums whitespace-nowrap">${a.norm_pwr ? a.norm_pwr + ' W' : '--'}</td>
          <td class="py-2.5 px-3 font-mono text-zinc-500 dark:text-zinc-400 tabular-nums whitespace-nowrap">${a.cadence ? a.cadence.toFixed(0) : '--'}</td>
          <td class="py-2.5 px-3 font-mono font-semibold text-zinc-900 dark:text-zinc-50 tabular-nums whitespace-nowrap">${a.load ? a.load.toFixed(1) : '0'}</td>
          <td class="py-2.5 px-3 whitespace-nowrap">${teDisplay}</td>
          <td class="py-2.5 px-3 font-mono text-zinc-500 dark:text-zinc-400 tabular-nums whitespace-nowrap">${a.cal} kcal${a.water_ml ? ' (' + (a.water_ml / 1000).toFixed(1) + 'L)' : ''}</td>
        `;
    aBody.appendChild(tr);
  });
}

function renderSleepAnalysis(sData) {
  const gBody = document.getElementById('bedtimeGroupsBody');
  if (gBody) {
    gBody.innerHTML = '';
    sData.bedtime_groups.forEach(g => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition";
      tr.innerHTML = `
            <td class="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">${g.group}</td>
            <td class="py-3 px-4 font-mono text-zinc-600 dark:text-zinc-400">${g.count} gece (%${g.pct})</td>
            <td class="py-3 px-4 font-mono font-semibold text-indigo-600 dark:text-indigo-400">${g.sleep_h} saat</td>
            <td class="py-3 px-4 font-mono text-zinc-800 dark:text-zinc-200">${g.deep_h} sa / <span class="font-semibold text-amber-600 dark:text-amber-400">${g.rem_h} sa</span></td>
            <td class="py-3 px-4 font-mono font-semibold text-zinc-900 dark:text-zinc-100">${g.score}</td>
            <td class="py-3 px-4 font-mono font-semibold text-emerald-600 dark:text-emerald-400">${g.hrv} ms</td>
            <td class="py-3 px-4 font-mono text-zinc-600 dark:text-zinc-400">${g.rhr} bpm</td>
            <td class="py-3 px-4 font-mono font-medium text-zinc-800 dark:text-zinc-200">${g.bb_wake} / ${g.readiness}</td>
          `;
      gBody.appendChild(tr);
    });
  }

  const nBody = document.getElementById('sleepNightsBody');
  if (nBody) {
    nBody.innerHTML = '';
    sData.top_nights.forEach(n => {
      const tr = document.createElement('tr');
      tr.className = "bg-emerald-500/5 hover:bg-emerald-500/10 transition";
      tr.innerHTML = `
            <td class="py-2.5 px-3 font-semibold text-emerald-700 dark:text-emerald-400">En İyi ${n.rank}</td>
            <td class="py-2.5 px-3 font-mono text-zinc-800 dark:text-zinc-200 font-medium">${n.date}</td>
            <td class="py-2.5 px-3 font-mono text-zinc-600 dark:text-zinc-400">${n.bed_time}</td>
            <td class="py-2.5 px-3 font-mono font-semibold text-emerald-600 dark:text-emerald-400">${n.score}</td>
            <td class="py-2.5 px-3 font-mono text-zinc-700 dark:text-zinc-300">${n.sleep_h} sa</td>
            <td class="py-2.5 px-3 font-mono text-zinc-700 dark:text-zinc-300">${n.deep_rem}</td>
            <td class="py-2.5 px-3 font-mono font-semibold text-zinc-800 dark:text-zinc-200">${n.hrv_rhr}</td>
            <td class="py-2.5 px-3 font-mono text-zinc-700 dark:text-zinc-300">${n.bb_readiness}</td>
          `;
      nBody.appendChild(tr);
    });
    sData.worst_nights.forEach(n => {
      const tr = document.createElement('tr');
      tr.className = "bg-rose-500/5 hover:bg-rose-500/10 transition";
      tr.innerHTML = `
            <td class="py-2.5 px-3 font-semibold text-rose-700 dark:text-rose-400">En Düşük ${n.rank}</td>
            <td class="py-2.5 px-3 font-mono text-zinc-800 dark:text-zinc-200 font-medium">${n.date}</td>
            <td class="py-2.5 px-3 font-mono text-zinc-600 dark:text-zinc-400">${n.bed_time}</td>
            <td class="py-2.5 px-3 font-mono font-semibold text-rose-600 dark:text-rose-400">${n.score}</td>
            <td class="py-2.5 px-3 font-mono text-zinc-700 dark:text-zinc-300">${n.sleep_h} sa</td>
            <td class="py-2.5 px-3 font-mono text-zinc-700 dark:text-zinc-300">${n.deep_rem}</td>
            <td class="py-2.5 px-3 font-mono font-semibold text-zinc-800 dark:text-zinc-200">${n.hrv_rhr}</td>
            <td class="py-2.5 px-3 font-mono text-zinc-700 dark:text-zinc-300">${n.bb_readiness}</td>
          `;
      nBody.appendChild(tr);
    });
  }
}

function renderCorrelations(corrs) {
  const cBody = document.getElementById('correlationsBody');
  if (!cBody) return;
  cBody.innerHTML = '';
  corrs.forEach(c => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition";
    tr.innerHTML = `
          <td class="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">${c.pair}</td>
          <td class="py-3 px-4 font-mono font-semibold ${c.r < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-indigo-600 dark:text-indigo-400'}">${c.r.toFixed(3)}</td>
          <td class="py-3 px-4 font-mono text-zinc-600 dark:text-zinc-400">${c.t.toFixed(2)}</td>
          <td class="py-3 px-4 font-mono font-medium text-zinc-500 dark:text-zinc-400">${c.p}</td>
          <td class="py-3 px-4 text-zinc-600 dark:text-zinc-300">${c.insight}</td>
        `;
    cBody.appendChild(tr);
  });
}

function renderPeriods(pData) {
  const container = document.getElementById('periodsContainer');
  if (!container) return;
  container.innerHTML = '';
  pData.periods.forEach((p, idx) => {
    const div = document.createElement('div');
    div.className = `surface-card p-5 rounded-xl space-y-2.5 ${idx === pData.periods.length - 1 ? 'md:col-span-2 border-indigo-500/30 dark:border-indigo-500/30' : ''}`;
    div.innerHTML = `
          <div class="flex items-center justify-between gap-2">
            <h4 class="text-sm font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">${p.period}</h4>
            <span class="font-mono text-[10px] font-medium text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200/70 dark:border-indigo-500/20 px-2 py-0.5 rounded-md">${p.dates}</span>
          </div>
          <p class="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">${p.summary}</p>
          <div class="flex flex-wrap items-center gap-4 font-mono text-[11px] text-zinc-500 dark:text-zinc-400 pt-2 border-t border-zinc-200/70 dark:border-zinc-800">
            <span>Ort. Yük: <strong class="text-zinc-900 dark:text-zinc-100">${p.avg_load}</strong></span>
            <span>Gece HRV: <strong class="text-zinc-900 dark:text-zinc-100">${p.avg_hrv} ms</strong></span>
            <span>Uyku: <strong class="text-zinc-900 dark:text-zinc-100">${p.avg_sleep}</strong></span>
          </div>
        `;
    container.appendChild(div);
  });
}

function renderSettingsAndZones(setData) {
  const sGrid = document.getElementById('settingsGrid');
  if (sGrid) {
    sGrid.innerHTML = '';
    let savedSettings = {};
    try {
      savedSettings = JSON.parse(localStorage.getItem('garmin_fixed_settings') || '{}');
    } catch (e) {
      savedSettings = {};
    }

    setData.settings.forEach(s => {
      const isChecked = !!savedSettings[s.num];
      const div = document.createElement('div');
      div.id = `setting-card-${s.num}`;
      div.className = isChecked
        ? "p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 flex items-start gap-3 transition"
        : "surface-card p-4 rounded-xl flex items-start gap-3 transition";

      div.innerHTML = `
        <input type="checkbox" id="setting-cb-${s.num}" ${isChecked ? 'checked' : ''} class="mt-0.5 rounded border-zinc-300 dark:border-zinc-700 w-4 h-4 cursor-pointer">
        <div class="text-xs flex-1 cursor-pointer" onclick="document.getElementById('setting-cb-${s.num}').click()">
          <div class="flex items-center justify-between gap-2">
            <p class="font-semibold text-zinc-950 dark:text-zinc-50 ${isChecked ? 'line-through text-zinc-400 dark:text-zinc-500' : ''}" id="setting-title-${s.num}">${s.num}. ${s.name}: <span class="font-mono text-indigo-600 dark:text-indigo-400 font-semibold ${isChecked ? 'text-zinc-400 dark:text-zinc-500' : ''}">${s.recommended}</span></p>
            ${isChecked ? '<span class="font-mono text-[10px] font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded">UYGULANDI</span>' : ''}
          </div>
          <p class="text-[11px] text-zinc-500 dark:text-zinc-400 mt-1">Mevcut: <code class="font-mono bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-[10px]">${s.current}</code></p>
          <p class="text-[11px] text-zinc-600 dark:text-zinc-400 mt-1 leading-relaxed">${s.reason}</p>
        </div>
      `;

      const cb = div.querySelector(`#setting-cb-${s.num}`);
      cb.onchange = (e) => {
        savedSettings[s.num] = e.target.checked;
        localStorage.setItem('garmin_fixed_settings', JSON.stringify(savedSettings));
        renderSettingsAndZones(setData);
      };

      sGrid.appendChild(div);
    });
  }

  const zBody = document.getElementById('zonesTableBody');
  if (zBody) {
    zBody.innerHTML = '';
    setData.zones.forEach(z => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition";
      tr.innerHTML = `
            <td class="py-3 px-4 font-semibold text-zinc-900 dark:text-zinc-100">${z.zone}</td>
            <td class="py-3 px-4 font-mono text-zinc-500 dark:text-zinc-400">${z.current_hr}</td>
            <td class="py-3 px-4 font-mono font-semibold text-indigo-600 dark:text-indigo-400">${z.rec_lthr}</td>
            <td class="py-3 px-4 font-mono font-medium text-emerald-600 dark:text-emerald-400">${z.rec_hrr}</td>
            <td class="py-3 px-4 font-mono font-semibold text-zinc-900 dark:text-zinc-100">${z.rec_pwr}</td>
          `;
      zBody.appendChild(tr);
    });
  }
}

function renderZ2Tracker(data) {
  if (!data) return;
  const kpi = document.getElementById('z2KpiGrid');
  if (kpi) {
    kpi.innerHTML = `
          <div class="bg-zinc-50 dark:bg-zinc-950/60 p-3.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800">
            <p class="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Mevcut 145 bpm</p>
            <p class="font-mono text-xl font-bold text-zinc-950 dark:text-zinc-50 mt-1">${data.current_pace}</p>
            <p class="font-mono text-[10px] text-zinc-500 mt-1">EF: ${data.current_efficiency_factor} m/atım</p>
          </div>
          <div class="bg-indigo-50/60 dark:bg-indigo-500/10 p-3.5 rounded-xl border border-indigo-200/80 dark:border-indigo-500/20">
            <p class="font-mono text-[10px] text-indigo-600 dark:text-indigo-300 uppercase tracking-wider">Hedef 145 bpm</p>
            <p class="font-mono text-xl font-bold text-indigo-700 dark:text-indigo-300 mt-1">${data.target_pace}</p>
            <p class="font-mono text-[10px] text-indigo-600/80 dark:text-indigo-200/80 mt-1">EF: ${data.target_efficiency_factor} (+%33)</p>
          </div>
          <div class="bg-zinc-50 dark:bg-zinc-950/60 p-3.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800">
            <p class="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Kalan Hız Farkı</p>
            <p class="font-mono text-xl font-bold text-zinc-950 dark:text-zinc-50 mt-1">-${data.pace_gap_sec_per_km} sn/km</p>
            <p class="font-mono text-[10px] text-zinc-500 mt-1">${data.target_date}</p>
          </div>
          <div class="bg-zinc-50 dark:bg-zinc-950/60 p-3.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800">
            <p class="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Kalan Gün</p>
            <p class="font-mono text-xl font-bold text-zinc-950 dark:text-zinc-50 mt-1">~${data.remaining_days} Gün</p>
            <p class="font-mono text-[10px] text-emerald-600 dark:text-emerald-400 mt-1">20 Hafta Planı</p>
          </div>
          <div class="bg-zinc-50 dark:bg-zinc-950/60 p-3.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800 col-span-2 md:col-span-1">
            <p class="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Kalan Antrenman</p>
            <p class="font-mono text-xs font-semibold text-zinc-950 dark:text-zinc-50 mt-1"><span class="text-indigo-600 dark:text-indigo-400">${data.workout_counts.remaining_zone2_sessions}</span> Z2 · <span class="text-emerald-600 dark:text-emerald-400">${data.workout_counts.remaining_interval_sessions}</span> İnt</p>
            <p class="font-mono text-[10px] text-zinc-500 mt-1">${data.workout_counts.remaining_strength_sessions} A/B 5x5 Gym</p>
          </div>
        `;
  }

  const gr = document.getElementById('z2GoldenRulesContainer');
  if (gr) {
    gr.innerHTML = data.golden_rules.map(r => `
          <div class="bg-white dark:bg-zinc-900 p-3 rounded-lg border border-zinc-200/80 dark:border-zinc-800">
            <p class="font-semibold text-zinc-950 dark:text-zinc-50">${r.rule}</p>
            <p class="text-[11px] text-zinc-600 dark:text-zinc-400 mt-0.5 leading-relaxed">${r.why}</p>
          </div>
        `).join('');
  }

  const ms = document.getElementById('z2MilestonesContainer');
  if (ms) {
    ms.innerHTML = data.timeline_milestones.map(m => `
          <div class="bg-white dark:bg-zinc-900 p-3 rounded-lg border border-zinc-200/80 dark:border-zinc-800 flex items-center justify-between gap-2">
            <div>
              <p class="font-semibold text-zinc-950 dark:text-zinc-50">${m.period}</p>
              <p class="text-[11px] text-zinc-600 dark:text-zinc-400">${m.status}</p>
            </div>
            <div class="text-right shrink-0">
              <span class="font-mono text-xs font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md">${m.pace}</span>
              <p class="font-mono text-[10px] text-zinc-500 mt-1">${m.weight}</p>
            </div>
          </div>
        `).join('');
  }
}

function renderPhysiqueTracker(data) {
  if (!data) return;
  const c = document.getElementById('morphologyCardsContainer');
  if (!c) return;
  c.innerHTML = data.stages.map((s, idx) => `
        <div class="bg-zinc-50 dark:bg-zinc-950/60 p-5 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-3 ${idx === 2 ? 'md:col-span-1 border-indigo-500/30 dark:border-indigo-500/30' : ''}">
          <div class="flex items-center justify-between gap-2">
            <span class="font-mono text-[10px] font-semibold uppercase tracking-wider bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-200/70 dark:border-indigo-500/20 px-2 py-0.5 rounded-md">Aşama ${s.stage_num}</span>
            <span class="font-mono text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md">${s.days_remaining} Gün Kaldı</span>
          </div>
          <div>
            <h4 class="font-mono text-lg font-bold tracking-tight text-zinc-950 dark:text-zinc-50">${s.target_kg} kg <span class="text-xs text-zinc-500 font-medium">(Yağ: ${s.estimated_fat_pct})</span></h4>
            <p class="font-mono text-[11px] text-indigo-600 dark:text-indigo-400 font-medium mt-0.5">Hedef: ${s.target_date}</p>
          </div>
          <p class="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed"><strong class="text-zinc-900 dark:text-zinc-200 font-semibold">Görsel Değişim:</strong> ${s.visual_changes}</p>
          <p class="text-xs text-emerald-800 dark:text-emerald-300 bg-emerald-500/5 dark:bg-emerald-500/10 p-2.5 rounded-lg border border-emerald-500/20"><strong class="font-semibold">Performans Etkisi:</strong> ${s.performance_impact}</p>
        </div>
      `).join('');
}

function renderHealthScreening(data) {
  if (!data) return;
  document.getElementById('doctorVerdictTitle').textContent = data.doctor_verdict;
  document.getElementById('doctorSummaryText').textContent = data.summary;

  const pGrid = document.getElementById('healthPillarsGrid');
  if (pGrid) {
    pGrid.innerHTML = data.pillars.map((p, idx) => `
          <div class="bg-zinc-50 dark:bg-zinc-950/60 border border-zinc-200/80 dark:border-zinc-800 rounded-xl p-4 space-y-2 ${idx === 0 ? 'lg:col-span-2' : ''}">
            <div class="flex items-center justify-between gap-2">
              <h5 class="text-xs font-semibold text-zinc-950 dark:text-zinc-50">${p.name}</h5>
              <span class="font-mono text-[10px] font-medium px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 shrink-0">${p.badge}</span>
            </div>
            <p class="font-mono text-xs font-semibold text-indigo-600 dark:text-indigo-400">${p.value}</p>
            <p class="text-[11px] text-zinc-600 dark:text-zinc-400 leading-relaxed">${p.clinical_notes}</p>
          </div>
        `).join('');
  }
}

function renderFitnessAge(data) {
  if (!data) return;
  document.getElementById('fitnessAgeValue').textContent = data.fitness_age + " Yaş";
}

function renderGarminExpansion(data) {
  if (!data) return;
  const c = document.getElementById('garminExpansionCardsContainer');
  if (!c) return;
  c.innerHTML = data.new_high_resolution_channels.map((ch, idx) => `
        <div class="bg-zinc-50 dark:bg-zinc-950/60 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-2.5 ${idx === 0 ? 'md:col-span-2' : ''}">
          <h4 class="text-xs font-semibold text-zinc-950 dark:text-zinc-50 flex items-center gap-2">
            ${lucideSvg('cpu', 'w-3.5 h-3.5 text-indigo-500')}
            <span>${ch.channel}</span>
          </h4>
          <p class="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">${ch.detail}</p>
          <p class="text-[11px] text-indigo-700 dark:text-indigo-300 bg-white dark:bg-zinc-900 p-2.5 rounded-lg border border-zinc-200/80 dark:border-zinc-800 flex items-start gap-2">
            ${lucideSvg('sparkles', 'w-3.5 h-3.5 shrink-0 mt-0.5')}
            <span><strong class="font-semibold">Faydası:</strong> ${ch.benefit}</span>
          </p>
        </div>
      `).join('');
  if (typeof refreshIcons === 'function') refreshIcons();
}

function renderProgressionAssessment(data) {
  if (!data) return;
  const vp = data.volume_progression || {};
  const st = data.style_transition || {};
  const fd = data.fatigue_and_deload || {};

  const grid = document.getElementById('progressionCardsGrid');
  if (grid) {
    grid.innerHTML = `
          <div class="bg-zinc-50 dark:bg-zinc-950/60 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-2.5">
            <div class="flex items-center justify-between gap-2">
              <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Hacim & Gün Artırma</span>
              <span class="font-mono text-[10px] font-semibold px-2 py-0.5 rounded-md ${vp.can_increase_days ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20' : 'bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-500/20'}">${vp.verdict || '--'}</span>
            </div>
            <p class="text-xs font-semibold text-zinc-950 dark:text-zinc-50">${vp.current_days} → <span class="text-indigo-600 dark:text-indigo-400">${vp.next_level_days}</span></p>
            <p class="text-[11px] text-zinc-600 dark:text-zinc-400 leading-relaxed">${vp.advice || ''}</p>
          </div>

          <div class="bg-zinc-50 dark:bg-zinc-950/60 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-2.5">
            <div class="flex items-center justify-between gap-2">
              <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Stil & Rutin Değişimi</span>
              <span class="font-mono text-[10px] font-semibold px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-500/20">${st.verdict || '--'}</span>
            </div>
            <p class="text-xs font-semibold text-zinc-950 dark:text-zinc-50">Mevcut: <span class="text-emerald-600 dark:text-emerald-400">${st.current_style}</span></p>
            <p class="text-[11px] text-zinc-600 dark:text-zinc-400 leading-relaxed">${st.advice || ''}</p>
            <p class="text-[10px] text-zinc-700 dark:text-zinc-300 bg-white dark:bg-zinc-900 p-2 rounded-lg border border-zinc-200/80 dark:border-zinc-800">${st.running_style_advice || ''}</p>
          </div>

          <div class="bg-zinc-50 dark:bg-zinc-950/60 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-2.5">
            <div class="flex items-center justify-between gap-2">
              <span class="font-mono text-[10px] font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Deload & Esneklik</span>
              <span class="font-mono text-[10px] font-semibold px-2 py-0.5 rounded-md ${fd.needs_deload ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20' : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20'}">${fd.status || '--'}</span>
            </div>
            <p class="text-xs font-semibold text-zinc-950 dark:text-zinc-50">${fd.needs_deload ? 'Hacmi %40 Düşür' : 'Tam Güç & Kondisyon Aktif'}</p>
            <p class="text-[11px] text-zinc-600 dark:text-zinc-400 leading-relaxed">${fd.note || ''}</p>
            <p class="text-[10px] text-amber-800 dark:text-amber-300 bg-amber-500/10 p-2 rounded-lg border border-amber-500/20"><strong class="font-semibold">Dogmatik Olmama Kuralı:</strong> Yorgunluk/düşük HRV durumunda seans yürüyüş veya esnemeye çevrilir.</p>
          </div>
        `;
  }

  const tiersGrid = document.getElementById('athleteTiersGrid');
  if (tiersGrid && data.athlete_levels) {
    const tiers = Object.values(data.athlete_levels);
    tiersGrid.innerHTML = tiers.map(t => `
          <div class="bg-white dark:bg-zinc-900 p-3.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-2">
            <p class="font-semibold text-indigo-600 dark:text-indigo-400 text-xs">${t.level_tr.split('(')[0]}</p>
            <p class="font-mono text-[10px] text-zinc-500 font-medium">${t.recommended_split}</p>
            <p class="text-[11px] text-zinc-700 dark:text-zinc-300 leading-snug"><strong class="text-zinc-950 dark:text-zinc-100">Koşu:</strong> ${t.running_approach.split('.')[0]}</p>
            <p class="text-[11px] text-zinc-700 dark:text-zinc-300 leading-snug"><strong class="text-zinc-950 dark:text-zinc-100">Kuvvet:</strong> ${t.strength_approach.split('.')[0]}</p>
            <p class="text-[10px] text-emerald-700 dark:text-emerald-400 bg-emerald-500/5 dark:bg-emerald-500/10 p-2 rounded-lg border border-emerald-500/20 mt-1"><strong class="font-semibold">Geçiş Eşiği:</strong> ${t.progression_gate}</p>
          </div>
        `).join('');
  }
}

let cachedDailyProtocols = [];
let selectedProtocolMode = 'upcoming';

function selectProtocolDay(mode) {
  selectedProtocolMode = mode;
  renderDailyProtocols(cachedDailyProtocols);
}

function renderDailyProtocols(protocols) {
  const container = document.getElementById('dailyProtocolsContainer');
  const tabsEl = document.getElementById('protocolDayTabs');
  if (!container || !protocols || !Array.isArray(protocols)) return;
  cachedDailyProtocols = protocols;

  if (tabsEl) {
    const activeCls = 'px-3 py-1.5 rounded-lg font-semibold bg-indigo-600 text-white transition-all duration-200 active:scale-[0.98]';
    const idleCls = 'px-3 py-1.5 rounded-lg font-medium bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 border border-zinc-200/70 dark:border-zinc-700 transition-all duration-200 active:scale-[0.98]';
    const shortDay = (t) => (t || '').split(':')[0].trim().slice(0, 3);
    tabsEl.innerHTML = `
      <button onclick="selectProtocolDay('upcoming')" class="${selectedProtocolMode === 'upcoming' ? activeCls : idleCls}">Bugün &amp; Sıradaki (2)</button>
      ${protocols.map((p, idx) => `<button onclick="selectProtocolDay(${idx})" class="${selectedProtocolMode === idx ? activeCls : idleCls}">${shortDay(p.day_title)}</button>`).join('')}
      <button onclick="selectProtocolDay('all')" class="${selectedProtocolMode === 'all' ? activeCls : idleCls}">Tümü (${protocols.length})</button>
    `;
  }

  const visibleProtocols = selectedProtocolMode === 'all'
    ? protocols
    : (selectedProtocolMode === 'upcoming'
      ? protocols.slice(0, 2)
      : (protocols[selectedProtocolMode] ? [protocols[selectedProtocolMode]] : protocols.slice(0, 2)));

  container.innerHTML = visibleProtocols.map(p => {
    let exerciseHtml = '';
    if (p.category === 'gym') {
      exerciseHtml = `
<div class="overflow-x-auto custom-scrollbar mt-3 rounded-xl border border-zinc-200/80 dark:border-zinc-800">
  <table class="w-full text-left text-xs border-collapse">
    <thead>
      <tr class="bg-zinc-50 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400 border-b border-zinc-200/80 dark:border-zinc-800">
        <th class="py-2.5 px-3">#</th>
        <th class="py-2.5 px-3">Egzersiz</th>
        <th class="py-2.5 px-3">Set x Tekrar</th>
        <th class="py-2.5 px-3">Mevcut & Hedef Ağırlık</th>
        <th class="py-2.5 px-3">Dinlenme & RPE</th>
        <th class="py-2.5 px-3">Koçluk İpucu</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-zinc-100 dark:divide-zinc-800/80 text-zinc-700 dark:text-zinc-300">
      ${(p.exercises || []).map(ex => `
        <tr class="hover:bg-zinc-50 dark:hover:bg-zinc-800/40">
          <td class="py-2.5 px-3 font-mono font-semibold text-zinc-400">${ex.num}</td>
          <td class="py-2.5 px-3 font-semibold text-zinc-950 dark:text-zinc-50">${ex.name}</td>
          <td class="py-2.5 px-3 font-mono font-semibold text-indigo-600 dark:text-indigo-400">${ex.sets} x ${ex.reps}</td>
          <td class="py-2.5 px-3">
            <span class="font-mono font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">${ex.target_weight}</span>
            ${ex.current_achieved ? `<p class="font-mono text-[10px] text-zinc-400 mt-1">Son: ${ex.current_achieved}</p>` : ''}
          </td>
          <td class="py-2.5 px-3 font-mono text-zinc-600 dark:text-zinc-400">${ex.rest_sec} <span class="text-zinc-400">(${ex.target_rpe || 'RPE 8'})</span></td>
          <td class="py-2.5 px-3 text-[11px] text-zinc-600 dark:text-zinc-400 leading-relaxed">${ex.coaching_cue}</td>
        </tr>
      `).join('')}
    </tbody>
  </table>
</div>
      `;
    } else if (p.category === 'running') {
      const runEx = (p.exercises || [])[0] || {};
      exerciseHtml = `
<div class="bg-zinc-50 dark:bg-zinc-950/60 border border-zinc-200/80 dark:border-zinc-800 p-4 rounded-xl space-y-3 mt-3">
  <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
    <div>
      <p class="font-mono text-[10px] text-zinc-500 uppercase">Süre / Mesafe</p>
      <p class="font-mono font-bold text-zinc-950 dark:text-zinc-50 text-sm mt-0.5">${runEx.duration || (runEx.sets + ' x ' + runEx.reps)}</p>
      ${runEx.distance_est ? `<p class="font-mono text-[10px] text-zinc-500">${runEx.distance_est}</p>` : ''}
    </div>
    <div>
      <p class="font-mono text-[10px] text-zinc-500 uppercase">Hedef Nabız</p>
      <p class="font-mono font-bold text-emerald-600 dark:text-emerald-400 text-sm mt-0.5">${runEx.target_hr}</p>
    </div>
    <div>
      <p class="font-mono text-[10px] text-zinc-500 uppercase">Hedef Tempo</p>
      <p class="font-mono font-bold text-indigo-600 dark:text-indigo-400 text-sm mt-0.5">${runEx.target_pace}</p>
    </div>
    <div>
      <p class="font-mono text-[10px] text-zinc-500 uppercase">Hedef Kadans</p>
      <p class="font-mono font-bold text-zinc-950 dark:text-zinc-50 text-sm mt-0.5">${runEx.cadence_target}</p>
    </div>
  </div>
  <p class="text-xs text-zinc-600 dark:text-zinc-300 pt-2.5 border-t border-zinc-200/70 dark:border-zinc-800"><strong class="text-zinc-950 dark:text-zinc-50 font-semibold">Koçluk Talimatı:</strong> ${runEx.coaching_cue}</p>
</div>
      `;
    } else {
      const restEx = (p.exercises || [])[0] || {};
      exerciseHtml = `
<div class="bg-zinc-50 dark:bg-zinc-950/60 border border-zinc-200/80 dark:border-zinc-800 p-4 rounded-xl space-y-1 mt-3 text-xs">
  <p class="font-semibold text-zinc-900 dark:text-zinc-100">${restEx.protocol}</p>
  <p class="text-[11px] text-zinc-600 dark:text-zinc-400 leading-relaxed">${restEx.coaching_cue}</p>
</div>
      `;
    }

    return `
      <div class="surface-card rounded-xl p-5 space-y-3 hover:border-zinc-400 dark:hover:border-zinc-700 transition">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-200/70 dark:border-zinc-800 pb-3">
          <div class="flex items-center gap-2.5">
            <span class="font-mono text-[10px] font-semibold px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-200/70 dark:border-indigo-500/20">${p.badge}</span>
            <h4 class="text-sm font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">${p.day_title}</h4>
          </div>
          <span class="font-mono text-[11px] text-zinc-500 dark:text-zinc-400">${p.status_note}</span>
        </div>

        <p class="text-xs text-zinc-600 dark:text-zinc-300 leading-relaxed"><strong class="text-zinc-950 dark:text-zinc-50 font-semibold">Günün Hedefi:</strong> ${p.objective}</p>
        <p class="text-xs text-zinc-600 dark:text-zinc-300 bg-zinc-50 dark:bg-zinc-950/60 border border-zinc-200/80 dark:border-zinc-800 p-2.5 rounded-lg"><strong class="text-zinc-900 dark:text-zinc-100 font-semibold">Isınma & Mobilite:</strong> ${p.warmup}</p>

        ${exerciseHtml}

        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-3 border-t border-zinc-200/70 dark:border-zinc-800 text-[11px] text-zinc-500 dark:text-zinc-400">
          <p><strong class="text-zinc-700 dark:text-zinc-200">Soğuma:</strong> ${p.cooldown}</p>
          <p class="font-mono font-medium text-zinc-700 dark:text-zinc-300 bg-zinc-50 dark:bg-zinc-950 px-2.5 py-1 rounded-md border border-zinc-200/80 dark:border-zinc-800">${p.telemetry_targets ? p.telemetry_targets.nutrition : ''}</p>
        </div>
      </div>
    `;
  }).join('');
  if (typeof refreshIcons === 'function') refreshIcons();
}

let chatHistory = [];

/* Garmin Athlete OS - Dashboard Sections & Telemetry Renderers */
function renderWeeklyScheduleTable(scheduleList) {
  const sBody = document.getElementById('overviewScheduleBody');
  if (!sBody || !scheduleList) return;
  sBody.innerHTML = '';
  scheduleList.forEach((s, idx) => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-blue-50/70 transition cursor-pointer group";
    tr.title = "Günün detaylı antrenman ve beslenme reçetesine gitmek için tıklayın";
    tr.onclick = () => {
      if (typeof setTab === 'function') setTab('plan');
      if (typeof setSubTab === 'function') setSubTab('plan', 'protocols');
      if (typeof selectProtocolDay === 'function') selectProtocolDay(idx);
      const targetSec = document.getElementById('dailyProtocolsSection');
      if (targetSec) {
        targetSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    };
    tr.innerHTML = `
      <td class="py-2.5 px-3 font-bold text-slate-900 group-hover:text-blue-700 transition flex items-center justify-between">
        <span>${s.day}</span>
        <span class="text-[10px] text-blue-500 opacity-0 group-hover:opacity-100 transition">↓</span>
      </td>
      <td class="py-2.5 px-3 font-semibold text-blue-900">${s.primary}</td>
      <td class="py-2.5 px-3 text-slate-500">${s.secondary}</td>
      <td class="py-2.5 px-3 font-medium text-emerald-700">${s.target}</td>
      <td class="py-2.5 px-3 text-slate-600">${s.calories}</td>
      <td class="py-2.5 px-3 text-slate-600">${s.macro}</td>
    `;
    sBody.appendChild(tr);
  });
}

// TAB YÖNETİMİ

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

  // Top In-Focus Garmin Cards (Canlı)
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
  if (ifsRhrHrv) ifsRhrHrv.textContent = `Dinlenik HR: ${data.resting_hr ?? '--'} bpm • HRV: ${data.overnight_hrv ?? '--'} ms`;

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
    ifsSub.textContent = `ACWR ${acwrVal} • ${bal} HRV`;
  }
  const ifsVo2 = document.getElementById('inFocusVo2Max');
  if (ifsVo2) ifsVo2.textContent = vo2;

  // 4 KPI Kartı (Canlı ve Tutarı)
  const kw = document.getElementById('kpi-weight');
  if (kw && data.weight !== undefined) kw.textContent = String(data.weight).replace('.', ',') + ' kg';
  const kwb = document.getElementById('kpi-weight-badge');
  if (kwb && data.total_loss_kg !== undefined) kwb.textContent = `-${String(data.total_loss_kg).replace('.', ',')} kg`;
  const kwbmi = document.getElementById('kpi-weight-bmi');
  if (kwbmi && data.bmi !== undefined) kwbmi.innerHTML = `VKİ: <strong class="text-slate-700 dark:text-slate-300">${data.bmi}</strong>`;

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
  if (kehrv) kehrv.innerHTML = `Gece HRV: <strong class="text-slate-800 dark:text-slate-200">${data.overnight_hrv ?? '--'} ms</strong>`;
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
  if (klt) klt.innerHTML = `Tünel: ${tMin} - ${tMax} (<strong class="text-emerald-600 dark:text-emerald-400 font-bold">Optimal</strong>)`;
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
      circle.setAttribute('class', 'text-emerald-500 transition-all duration-1000');
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

  // Milestones Tablosu
  const mBody = document.getElementById('overviewMilestonesBody');
  if (mBody && data.milestones) {
    mBody.innerHTML = '';
    data.milestones.forEach(m => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-slate-50/80 dark:hover:bg-slate-800/60 transition";
      tr.innerHTML = `
<td class="py-2.5 px-3 font-bold text-slate-900 dark:text-white">${m.level}</td>
<td class="py-2.5 px-3 font-semibold text-blue-600 dark:text-blue-400 tabular-nums">${m.target_kg} kg <span class="text-slate-400 font-normal">(${m.target_bmi})</span></td>
<td class="py-2.5 px-3 text-slate-500 dark:text-slate-400 tabular-nums">${m.diff_kg} kg</td>
<td class="py-2.5 px-3 font-bold text-slate-900 dark:text-white tabular-nums">${m.days_current} Gün <span class="text-slate-400 font-normal">(${m.target_date_current})</span></td>
<td class="py-2.5 px-3 text-slate-600 dark:text-slate-300 tabular-nums">${m.days_optimal} Gün <span class="text-slate-400">(${m.target_date_optimal})</span></td>
<td class="py-2.5 px-3 font-semibold text-emerald-600 dark:text-emerald-400 tabular-nums">${m.expected_5k}</td>
<td class="py-2.5 px-3 text-slate-700 dark:text-slate-300 tabular-nums">${m.expected_vo2}</td>
          `;
      mBody.appendChild(tr);
    });
  }

  // Haftalık Plan
  renderWeeklyScheduleTable(data.schedule);
}

// 2. FORMA GİRME HESAPLAYICISI

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

// 3. BRANŞLAR & AYNI GÜN SIRALAMASI

function renderSports(sports) {
  const container = document.getElementById('sportsCardsContainer');
  container.innerHTML = '';
  const icons = { running: '🏃', strength: '🏋️', sailing: '⛵', basketball: '🏀' };
  const colors = { running: 'emerald', strength: 'blue', sailing: 'cyan', basketball: 'amber' };

  for (let key in sports) {
    const sp = sports[key];
    const color = colors[key] || 'slate';
    const card = document.createElement('div');
    card.className = "bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-3.5";
    card.innerHTML = `
          <div class="flex items-center justify-between">
<div class="flex items-center space-x-2.5">
  <div class="w-9 h-9 rounded-xl bg-${color}-50 text-${color}-700 border border-${color}-100 flex items-center justify-center font-bold text-base">${icons[key] || '⚡'}</div>
  <div>
    <h4 class="text-sm font-bold text-slate-900">${sp.name}</h4>
    <p class="text-[11px] text-slate-500">${sp.stats_summary || sp.current_pace || ''}</p>
  </div>
</div>
<span class="text-[11px] font-bold text-${color}-700 bg-${color}-50 px-2.5 py-1 rounded-full border border-${color}-200">${sp.schedule_status || sp.cadence || 'Aktif'}</span>
          </div>

          <div class="text-xs text-slate-600 space-y-1.5 bg-slate-50 p-3 rounded-xl border border-slate-100">
<p class="font-bold text-slate-800">Nasıl Gelişilir?</p>
${sp.how_to_improve.map(item => `<p>• ${item}</p>`).join('')}
          </div>

          ${sp.last_workout ? `
          <div class="text-[11px] text-emerald-900 bg-emerald-50/80 p-2.5 rounded-xl border border-emerald-200 space-y-1">
<div class="flex items-center justify-between">
  <span class="font-bold">${sp.last_workout.date}</span>
  <span class="bg-emerald-600 text-white font-extrabold text-[9px] px-1.5 py-0.5 rounded">${sp.last_workout.title}</span>
</div>
<p class="text-emerald-800">${sp.last_workout.exercises ? sp.last_workout.exercises.join(' • ') : ''}</p>
          </div>` : ''}

          <div class="border-t border-slate-100 pt-3 space-y-2">
<p class="text-xs font-bold text-slate-900">📅 Sonraki Antrenman Günleri ve Adımları:</p>
${sp.upcoming_sessions && sp.upcoming_sessions.length > 0 ? sp.upcoming_sessions.map(sess => `
  <div class="bg-slate-50/90 p-2.5 rounded-xl border border-slate-200/70 text-xs space-y-1">
    <div class="flex items-center justify-between font-bold text-slate-800">
      <span class="text-blue-950 font-bold">${sess.day}</span>
      <span class="text-[10px] text-${color}-700 bg-${color}-50 px-2 py-0.5 rounded border border-${color}-200">${sess.type || 'Seans'}</span>
    </div>
    <p class="text-slate-800 font-semibold text-[11.5px]">${sess.title} <span class="text-slate-400 font-normal">(${sess.duration || ''})</span></p>
    <p class="text-[11px] text-slate-600">${sess.details || ''}</p>
  </div>
`).join('') : `
  <div class="text-xs text-slate-700 bg-slate-50/70 p-2.5 rounded-xl border border-slate-200/60">
    <p class="font-bold text-slate-900">${sp.next_workout.day}: ${sp.next_workout.title} (${sp.next_workout.duration || ''})</p>
    <p class="text-[11px] text-slate-500 mt-1">${sp.next_workout.details || sp.next_workout.hydration_plan || (sp.next_workout.exercises ? sp.next_workout.exercises.join(', ') : '')}</p>
  </div>
`}
          </div>
        `;
    container.appendChild(card);
  }
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
      div.className = "bg-slate-50 p-3 rounded-xl border border-slate-200/80 space-y-1";
      div.innerHTML = `
<div class="flex items-center justify-between">
  <span class="font-bold text-slate-800 text-xs">${item.name}</span>
  <span class="text-[10px] font-bold text-blue-700 bg-blue-100/80 px-1.5 py-0.5 rounded">${item.delta}</span>
</div>
<p class="text-[11px] text-slate-500 leading-snug" title="${item.history.join(' → ')}">${item.history.slice(-2).join(' → ')}</p>
<p class="text-[11px] font-semibold text-emerald-700 pt-0.5 border-t border-slate-200/60">🎯 Hedef: ${item.next_target}</p>
          `;
      progGrid.appendChild(div);
    });
  }

  const tableBody = document.getElementById('gymHistoryTableBody');
  if (tableBody && gym.sessions) {
    tableBody.innerHTML = '';
    gym.sessions.forEach(sess => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-slate-50/80 transition";
      const exSummary = sess.exercises.map(ex => {
        const setStr = ex.sets.map(s => `${s.reps}x${s.weight_kg}kg`).join(', ');
        return `<div class="mb-1"><strong class="text-slate-800">${ex.name}</strong> <span class="text-slate-400">(${ex.sets.length} set)</span>: <span class="text-blue-900 font-medium">${setStr}</span></div>`;
      }).join('');

      tr.innerHTML = `
<td class="py-2.5 px-3 font-semibold text-slate-900 whitespace-nowrap">${sess.date} <span class="text-slate-400 text-[11px]">${sess.time || ''}</span></td>
<td class="py-2.5 px-3 font-bold ${sess.workout_type === 'Workout A' ? 'text-blue-900' : 'text-purple-900'}">${sess.workout_type}</td>
<td class="py-2.5 px-3 text-slate-600 whitespace-nowrap">${sess.duration_min} dk • ${sess.calories} kcal</td>
<td class="py-2.5 px-3 font-extrabold text-slate-800 whitespace-nowrap">${(sess.total_volume_kg / 1000.0).toFixed(2)} Ton</td>
<td class="py-2.5 px-3 text-xs">${exSummary}</td>
          `;
      tableBody.appendChild(tr);
    });
  }
}


function renderSameDaySequence(seqList) {
  const sBody = document.getElementById('sameDayTableBody');
  sBody.innerHTML = '';
  seqList.forEach(item => {
    const tr = document.createElement('tr');
    tr.className = item.is_recommended ? "hover:bg-slate-50/80 transition" : "hover:bg-rose-50/40 bg-rose-50/20 transition";
    tr.innerHTML = `
          <td class="py-2.5 px-3 font-semibold text-slate-900">${item.date}</td>
          <td class="py-2.5 px-3 font-bold ${item.is_recommended ? 'text-blue-900' : 'text-rose-900'}">${item.sequence}</td>
          <td class="py-2.5 px-3 text-slate-600">${item.strength_info}</td>
          <td class="py-2.5 px-3 font-medium text-slate-800">${item.run_info}</td>
          <td class="py-2.5 px-3 font-bold ${item.is_recommended ? 'text-slate-800' : 'text-rose-700'}">${item.run_hr}</td>
          <td class="py-2.5 px-3 font-semibold ${item.is_recommended ? 'text-emerald-700' : 'text-rose-700'}">${item.z4_pct}</td>
          <td class="py-2.5 px-3 text-slate-600">${item.result}</td>
        `;
    sBody.appendChild(tr);
  });
}

// ANTRENMAN YÜKÜ VE ACWR

function renderTrainingLoad(tl) {
  if (!tl) return;
  const cur = tl.current_status;
  const foc = tl.load_focus;

  if (cur) {
    document.getElementById('tl-status').textContent = cur.status_tr;
    document.getElementById('tl-acute').textContent = cur.acute_load;
    document.getElementById('tl-chronic').textContent = cur.chronic_load;
    document.getElementById('tl-tunnel').textContent = Math.round(cur.tunnel_min) + " - " + Math.round(cur.tunnel_max);
    document.getElementById('tl-acwr').textContent = cur.acwr.toFixed(2);
    const badge = document.getElementById('tl-acwr-badge');
    if (cur.acwr >= 0.8 && cur.acwr <= 1.3) {
      badge.textContent = "SWEET SPOT (OPTIMAL)";
      badge.className = "text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full";
    } else if (cur.acwr > 1.5) {
      badge.textContent = "AŞIRI YÜK (DİKKAT)";
      badge.className = "text-xs font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full";
    } else {
      badge.textContent = cur.acwr_status;
      badge.className = "text-xs font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full";
    }
  }

  if (foc) {
    document.getElementById('tl-focus-low').textContent = foc.aerobic_low.actual + " birim";
    document.getElementById('tl-focus-high').textContent = foc.aerobic_high.actual + " birim";
    document.getElementById('tl-focus-anaerobic').textContent = foc.anaerobic.actual + " birim";
  }

  // 14 Haftalık Tablo
  const wBody = document.getElementById('trainingLoadWeeklyBody');
  if (wBody && tl.weekly_progression) {
    wBody.innerHTML = '';
    tl.weekly_progression.forEach(w => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-slate-50/80 transition";
      const acwrColor = (w.acwr >= 0.8 && w.acwr <= 1.3) ? "text-emerald-700 font-black" : ((w.acwr > 1.5) ? "text-rose-700 font-black" : "text-amber-700 font-bold");
      tr.innerHTML = `
<td class="py-2 px-2 font-semibold text-slate-900 whitespace-nowrap">${w.date}</td>
<td class="py-2 px-2 font-bold text-blue-900">${w.status_tr}</td>
<td class="py-2 px-2 font-extrabold text-slate-900 tabular-nums">${w.acute_load}</td>
<td class="py-2 px-2 text-slate-600 tabular-nums">${w.chronic_load}</td>
<td class="py-2 px-2 ${acwrColor} tabular-nums">${w.acwr.toFixed(2)}</td>
<td class="py-2 px-2 text-slate-500">${w.acwr_status}</td>
<td class="py-2 px-2 text-blue-700 font-medium tabular-nums">${w.low_aero}</td>
<td class="py-2 px-2 text-amber-700 font-medium tabular-nums">${w.high_aero}</td>
<td class="py-2 px-2 text-rose-700 font-medium tabular-nums">${w.anaerobic}</td>
<td class="py-2 px-2 font-semibold text-slate-800">${w.balance_tr}</td>
          `;
      wBody.appendChild(tr);
    });
  }

  // En Yüksek 10 Yük Seansı
  const tBody = document.getElementById('trainingLoadTopActsBody');
  if (tBody && tl.top_load_acts) {
    tBody.innerHTML = '';
    const spNames = { running: 'Koşu', sailing_v2: 'Yelken', resort_skiing: 'Kayak', strength_training: 'Kuvvet', basketball: 'Basketbol' };
    tl.top_load_acts.forEach(a => {
      const tr = document.createElement('tr');
      tr.className = "hover:bg-blue-50/70 transition cursor-pointer group";
      tr.title = "Aktivite telemetrisini incelemek için tıklayın";
      tr.onclick = () => openActivityModal(a);
      tr.innerHTML = `
<td class="py-2.5 px-3 font-semibold text-slate-900 group-hover:text-blue-700 transition flex items-center justify-between">
  <span>${a.date}</span>
  <span class="text-[10px] text-blue-500 opacity-0 group-hover:opacity-100 transition">🔍</span>
</td>
<td class="py-2.5 px-3 font-bold text-slate-800">${spNames[a.sport] || a.sport}</td>
<td class="py-2.5 px-3 text-slate-700 max-w-[160px] truncate">${a.name}</td>
<td class="py-2.5 px-3 text-slate-600">${a.dur_m} dk</td>
<td class="py-2.5 px-3 font-black text-blue-700">${a.load}</td>
<td class="py-2.5 px-3 font-bold text-emerald-700">${a.aTE ? a.aTE.toFixed(1) : '--'}</td>
<td class="py-2.5 px-3 font-bold text-rose-700">${a.anTE ? a.anTE.toFixed(1) : '--'}</td>
<td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700">${a.te_label}</span></td>
          `;
      tBody.appendChild(tr);
    });
  }
}

// 4. AKTİVİTELER & CANLI ARAMA & FİLTRELEME
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
        btn.className = "px-3 py-1.5 rounded-lg font-bold bg-blue-600 text-white shadow-sm transition";
      } else {
        btn.className = "px-3 py-1.5 rounded-lg font-medium text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition";
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
    tr.className = "hover:bg-blue-50/70 dark:hover:bg-slate-800/60 transition cursor-pointer group text-[11px]";
    tr.title = "Aktivite detaylarını ve sensör telemetrisini açmak için tıklayın";
    tr.onclick = () => openActivityModal(a);
    const spNames = { running: 'Koşu', sailing_v2: 'Yelken', strength_training: 'Kuvvet', basketball: 'Basketbol', hiking: 'Doğa Yürüyüşü', rowing_v2: 'Kürek', walking: 'Yürüyüş' };
    const teDisplay = a.aTE ? `<span class="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">A:${a.aTE.toFixed(1)}</span> / <span class="text-[11px] font-semibold text-rose-600 dark:text-rose-400">An:${(a.anTE || 0).toFixed(1)}</span>` : '--';
    tr.innerHTML = `
          <td class="py-2 px-2 font-semibold text-slate-900 dark:text-white whitespace-nowrap">${a.date} <span class="text-slate-400 dark:text-slate-500 font-normal">${a.time || ''}</span></td>
          <td class="py-2 px-2 whitespace-nowrap"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">${spNames[a.sport] || a.sport}</span></td>
          <td class="py-2 px-2 font-semibold text-slate-900 dark:text-slate-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition">${a.name || '--'}</td>
          <td class="py-2 px-2 text-slate-600 dark:text-slate-300 tabular-nums whitespace-nowrap">${a.dur_m.toFixed(0)} dk</td>
          <td class="py-2 px-2 font-semibold text-blue-600 dark:text-blue-400 tabular-nums whitespace-nowrap">${a.dist_km > 0 ? a.dist_km.toFixed(2) + ' km' : '--'}</td>
          <td class="py-2 px-2 font-bold text-slate-800 dark:text-slate-200 tabular-nums whitespace-nowrap">${a.pace_str || '--'}</td>
          <td class="py-2 px-2 text-slate-700 dark:text-slate-300 tabular-nums whitespace-nowrap">${a.avg_hr} / ${a.max_hr}</td>
          <td class="py-2 px-2 text-slate-600 dark:text-slate-400 tabular-nums whitespace-nowrap">${a.norm_pwr ? a.norm_pwr + ' W' : '--'}</td>
          <td class="py-2 px-2 text-slate-600 dark:text-slate-400 tabular-nums whitespace-nowrap">${a.cadence ? a.cadence.toFixed(0) : '--'}</td>
          <td class="py-2 px-2 font-bold text-slate-900 dark:text-white tabular-nums whitespace-nowrap">${a.load ? a.load.toFixed(1) : '0'}</td>
          <td class="py-2 px-2 whitespace-nowrap">${teDisplay}</td>
          <td class="py-2 px-2 text-slate-600 dark:text-slate-400 tabular-nums whitespace-nowrap">${a.cal} kcal${a.water_ml ? ' (' + (a.water_ml / 1000).toFixed(1) + 'L)' : ''}</td>
        `;
    aBody.appendChild(tr);
  });
}

// 5. UYKU & TOPARLANMA

function renderSleepAnalysis(sData) {
  const gBody = document.getElementById('bedtimeGroupsBody');
  gBody.innerHTML = '';
  sData.bedtime_groups.forEach(g => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-slate-50/80 transition";
    tr.innerHTML = `
          <td class="py-2.5 px-3 font-bold text-slate-900">${g.group}</td>
          <td class="py-2.5 px-3 font-semibold text-slate-600">${g.count} gece (%${g.pct})</td>
          <td class="py-2.5 px-3 font-bold text-blue-700">${g.sleep_h} saat</td>
          <td class="py-2.5 px-3 font-medium text-slate-800">${g.deep_h} sa / <span class="font-bold text-amber-700">${g.rem_h} sa</span></td>
          <td class="py-2.5 px-3 font-bold text-slate-900">${g.score}</td>
          <td class="py-2.5 px-3 font-bold text-emerald-700">${g.hrv} ms</td>
          <td class="py-2.5 px-3 text-slate-700">${g.rhr} bpm</td>
          <td class="py-2.5 px-3 font-semibold text-slate-800">${g.bb_wake} / ${g.readiness}</td>
        `;
    gBody.appendChild(tr);
  });

  const nBody = document.getElementById('sleepNightsBody');
  nBody.innerHTML = '';
  sData.top_nights.forEach(n => {
    const tr = document.createElement('tr');
    tr.className = "bg-emerald-50/20 hover:bg-emerald-50/40 transition";
    tr.innerHTML = `
          <td class="py-2 px-3 font-bold text-emerald-800">En İyi ${n.rank}</td>
          <td class="py-2 px-3 text-slate-800 font-semibold">${n.date}</td>
          <td class="py-2 px-3 text-slate-600">${n.bed_time}</td>
          <td class="py-2 px-3 font-black text-emerald-700">${n.score}</td>
          <td class="py-2 px-3 text-slate-700">${n.sleep_h} sa</td>
          <td class="py-2 px-3 text-slate-700">${n.deep_rem}</td>
          <td class="py-2 px-3 font-bold text-slate-800">${n.hrv_rhr}</td>
          <td class="py-2 px-3 text-slate-700">${n.bb_readiness}</td>
        `;
    nBody.appendChild(tr);
  });
  sData.worst_nights.forEach(n => {
    const tr = document.createElement('tr');
    tr.className = "bg-rose-50/20 hover:bg-rose-50/40 transition";
    tr.innerHTML = `
          <td class="py-2 px-3 font-bold text-rose-800">En Düşük ${n.rank}</td>
          <td class="py-2 px-3 text-slate-800 font-semibold">${n.date}</td>
          <td class="py-2 px-3 text-slate-600">${n.bed_time}</td>
          <td class="py-2 px-3 font-black text-rose-700">${n.score}</td>
          <td class="py-2 px-3 text-slate-700">${n.sleep_h} sa</td>
          <td class="py-2 px-3 text-slate-700">${n.deep_rem}</td>
          <td class="py-2 px-3 font-bold text-slate-800">${n.hrv_rhr}</td>
          <td class="py-2 px-3 text-slate-700">${n.bb_readiness}</td>
        `;
    nBody.appendChild(tr);
  });
}

// 6. KORELASYONLAR & GRAFİKLER

function renderCorrelations(corrs) {
  const cBody = document.getElementById('correlationsBody');
  cBody.innerHTML = '';
  corrs.forEach(c => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-slate-50/80 transition";
    tr.innerHTML = `
          <td class="py-2.5 px-3 font-bold text-slate-900">${c.pair}</td>
          <td class="py-2.5 px-3 font-black ${c.r < 0 ? 'text-rose-700' : 'text-blue-700'}">${c.r.toFixed(3)}</td>
          <td class="py-2.5 px-3 text-slate-600">${c.t.toFixed(2)}</td>
          <td class="py-2.5 px-3 font-semibold text-slate-500">${c.p}</td>
          <td class="py-2.5 px-3 text-slate-700">${c.insight}</td>
        `;
    cBody.appendChild(tr);
  });
}


function renderPeriods(pData) {
  const container = document.getElementById('periodsContainer');
  container.innerHTML = '';
  pData.periods.forEach(p => {
    const div = document.createElement('div');
    div.className = "bg-slate-50 border border-slate-200/90 p-4 rounded-xl space-y-2";
    div.innerHTML = `
          <div class="flex items-center justify-between">
<h4 class="text-xs font-bold text-slate-900">${p.period}</h4>
<span class="text-[10px] font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">${p.dates}</span>
          </div>
          <p class="text-xs text-slate-600">${p.summary}</p>
          <div class="flex items-center space-x-3 text-[11px] text-slate-500 font-medium pt-1 border-t border-slate-200/60">
<span>Ort. Akut Yük: <strong>${p.avg_load}</strong></span>
<span>Gece HRV: <strong>${p.avg_hrv} ms</strong></span>
<span>Uyku: <strong>${p.avg_sleep}</strong></span>
          </div>
        `;
    container.appendChild(div);
  });
}


function renderSettingsAndZones(setData) {
  const sGrid = document.getElementById('settingsGrid');
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
      ? "p-3.5 rounded-xl border border-emerald-300 bg-emerald-50/70 flex items-start space-x-2.5 transition"
      : "p-3.5 rounded-xl border border-slate-200 bg-slate-50/60 flex items-start space-x-2.5 transition";
    
    div.innerHTML = `
      <input type="checkbox" id="setting-cb-${s.num}" ${isChecked ? 'checked' : ''} class="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer">
      <div class="text-xs flex-1 cursor-pointer" onclick="document.getElementById('setting-cb-${s.num}').click()">
        <div class="flex items-center justify-between">
          <p class="font-bold text-slate-900 ${isChecked ? 'line-through text-slate-500' : ''}" id="setting-title-${s.num}">${s.num}. ${s.name}: <span class="text-blue-700 font-extrabold ${isChecked ? 'text-slate-500' : ''}">${s.recommended}</span></p>
          ${isChecked ? '<span class="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">UYGULANDI</span>' : ''}
        </div>
        <p class="text-[11px] text-slate-500 mt-0.5">Mevcut: <code class="bg-slate-200 px-1 py-0.5 rounded text-[10px]">${s.current}</code></p>
        <p class="text-[11px] text-slate-600 mt-1">${s.reason}</p>
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

  const zBody = document.getElementById('zonesTableBody');
  zBody.innerHTML = '';
  setData.zones.forEach(z => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-slate-50/80 transition";
    tr.innerHTML = `
          <td class="py-2.5 px-3 font-bold text-slate-900">${z.zone}</td>
          <td class="py-2.5 px-3 text-slate-500">${z.current_hr}</td>
          <td class="py-2.5 px-3 font-extrabold text-blue-700">${z.rec_lthr}</td>
          <td class="py-2.5 px-3 font-semibold text-emerald-700">${z.rec_hrr}</td>
          <td class="py-2.5 px-3 font-bold text-slate-800">${z.rec_pwr}</td>
        `;
    zBody.appendChild(tr);
  });
}

// 8.1. ZONE 2 @ 5:00 PACE SAYACI

function renderZ2Tracker(data) {
  if (!data) return;
  const kpi = document.getElementById('z2KpiGrid');
  kpi.innerHTML = `
        <div class="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200 dark:border-slate-700">
          <p class="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase">Mevcut 145 bpm</p>
          <p class="text-xl font-black text-slate-900 dark:text-white mt-0.5">${data.current_pace}</p>
          <p class="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">EF: ${data.current_efficiency_factor} m/atım</p>
        </div>
        <div class="bg-emerald-50/70 dark:bg-emerald-950/30 p-3 rounded-xl border border-emerald-200 dark:border-emerald-800">
          <p class="text-[10px] text-emerald-700 dark:text-emerald-300 font-semibold uppercase">Hedef 145 bpm</p>
          <p class="text-xl font-black text-emerald-700 dark:text-emerald-300 mt-0.5">${data.target_pace}</p>
          <p class="text-[10px] text-emerald-700 dark:text-emerald-200 mt-0.5">EF: ${data.target_efficiency_factor} m/atım (+%33)</p>
        </div>
        <div class="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200 dark:border-slate-700">
          <p class="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase">Kalan Hız Farkı</p>
          <p class="text-xl font-black text-amber-600 dark:text-amber-300 mt-0.5">-${data.pace_gap_sec_per_km} sn/km</p>
          <p class="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">${data.target_date} Hedefi</p>
        </div>
        <div class="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200 dark:border-slate-700">
          <p class="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase">Kalan Gün Sayısı</p>
          <p class="text-xl font-black text-slate-900 dark:text-white mt-0.5">~${data.remaining_days} Gün</p>
          <p class="text-[10px] text-emerald-600 dark:text-emerald-300 mt-0.5">20 Hafta Planı</p>
        </div>
        <div class="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200 dark:border-slate-700 col-span-2 sm:col-span-1">
          <p class="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase">Kalan Antrenmanlar</p>
          <p class="text-xs font-bold text-slate-900 dark:text-white mt-0.5"><span class="text-emerald-600 dark:text-emerald-400 font-black">${data.workout_counts.remaining_zone2_sessions}</span> Z2 • <span class="text-[#007CC3] dark:text-blue-400 font-black">${data.workout_counts.remaining_interval_sessions}</span> İnt</p>
          <p class="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">${data.workout_counts.remaining_strength_sessions} A/B 5x5 Gym</p>
        </div>
      `;

  const gr = document.getElementById('z2GoldenRulesContainer');
  gr.innerHTML = data.golden_rules.map(r => `
        <div class="bg-white dark:bg-slate-900/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-700">
          <p class="font-bold text-slate-900 dark:text-white">${r.rule}</p>
          <p class="text-[11px] text-slate-600 dark:text-slate-300 mt-0.5">${r.why}</p>
        </div>
      `).join('');

  const ms = document.getElementById('z2MilestonesContainer');
  ms.innerHTML = data.timeline_milestones.map(m => `
        <div class="bg-white dark:bg-slate-900/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-700 flex items-center justify-between gap-2">
          <div>
<p class="font-bold text-slate-900 dark:text-white">${m.period}</p>
<p class="text-[11px] text-slate-600 dark:text-slate-300">${m.status}</p>
          </div>
          <div class="text-right shrink-0">
<span class="text-xs font-black text-emerald-700 bg-emerald-50 border border-emerald-200 dark:text-emerald-300 dark:bg-emerald-500/20 px-2 py-0.5 rounded dark:border-emerald-500/30">${m.pace}</span>
<p class="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">${m.weight}</p>
          </div>
        </div>
      `).join('');
}

// 8.2. FİZİKSEL MORFOLOJİ RENDER

function renderPhysiqueTracker(data) {
  if (!data) return;
  const c = document.getElementById('morphologyCardsContainer');
  c.innerHTML = data.stages.map(s => `
        <div class="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-2.5">
          <div class="flex items-center justify-between">
<span class="text-[10px] font-extrabold uppercase tracking-wider bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">Aşama ${s.stage_num}</span>
<span class="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">${s.days_remaining} Gün Kaldı</span>
          </div>
          <div>
<h4 class="text-base font-black text-slate-900">${s.target_kg} kg <span class="text-xs text-slate-500 font-semibold">(Yağ: ${s.estimated_fat_pct})</span></h4>
<p class="text-[11px] text-blue-900 font-medium">Hedef Tarih: ${s.target_date}</p>
          </div>
          <p class="text-xs text-slate-700 leading-relaxed"><strong class="text-slate-900">Görsel Değişim:</strong> ${s.visual_changes}</p>
          <p class="text-xs text-emerald-800 bg-emerald-50/70 p-2 rounded-lg border border-emerald-200/60"><strong class="text-emerald-950">Performans Etkisi:</strong> ${s.performance_impact}</p>
        </div>
      `).join('');
}

// 8.3. KLİNİK SAĞLIK TARAMASI VE DOKTOR ÖZETİ

function renderHealthScreening(data) {
  if (!data) return;
  document.getElementById('doctorVerdictTitle').textContent = data.doctor_verdict;
  document.getElementById('doctorSummaryText').textContent = data.summary;

  const pGrid = document.getElementById('healthPillarsGrid');
  pGrid.innerHTML = data.pillars.map(p => `
        <div class="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 rounded-xl p-3.5 space-y-2">
          <div class="flex items-center justify-between gap-2">
<h5 class="text-xs font-bold text-slate-900 dark:text-white">${p.name}</h5>
<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-${p.badge_color}-500/20 dark:text-${p.badge_color}-300 dark:border-${p.badge_color}-500/30 shrink-0">${p.badge}</span>
          </div>
          <p class="text-xs font-black text-[#007CC3] dark:text-blue-300">${p.value}</p>
          <p class="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">${p.clinical_notes}</p>
        </div>
      `).join('');
}

// 8.4. SAĞLIK YAŞI

function renderFitnessAge(data) {
  if (!data) return;
  document.getElementById('fitnessAgeValue').textContent = data.fitness_age + " Yaş";
}

// 8.5. GARMIN VERİ DERİNLİĞİNİ ARTIRMA REHBERİ

function renderGarminExpansion(data) {
  if (!data) return;
  const c = document.getElementById('garminExpansionCardsContainer');
  c.innerHTML = data.new_high_resolution_channels.map(ch => `
        <div class="bg-slate-50 dark:bg-slate-800/80 p-4 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
          <h4 class="text-xs font-bold text-emerald-700 dark:text-emerald-400">${ch.channel}</h4>
          <p class="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">${ch.detail}</p>
          <p class="text-[11px] text-[#007CC3] dark:text-blue-300 bg-white dark:bg-slate-900/60 p-2 rounded-lg border border-slate-200 dark:border-slate-700/60">💡 <strong class="text-slate-800 dark:text-blue-200">Faydası:</strong> ${ch.benefit}</p>
        </div>
      `).join('');
}

// 8.6. DOGMATİK OLMAYAN DİNAMİK GELİŞİM RENDER

function renderProgressionAssessment(data) {
  if (!data) return;
  const vp = data.volume_progression || {};
  const st = data.style_transition || {};
  const fd = data.fatigue_and_deload || {};

  const grid = document.getElementById('progressionCardsGrid');
  if (grid) {
    grid.innerHTML = `
          <!-- 1. GÜN ARTTIRMA KARTI -->
          <div class="bg-slate-50 dark:bg-slate-900/70 p-4 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
<div class="flex items-center justify-between gap-2">
  <span class="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-indigo-300">Hacim & Gün Artırma</span>
  <span class="text-[10px] font-black px-2 py-0.5 rounded-full ${vp.can_increase_days ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-300' : 'bg-blue-50 text-[#007CC3] border border-blue-200 dark:bg-blue-500/20 dark:text-blue-300'}">${vp.verdict || '--'}</span>
</div>
<p class="text-xs font-bold text-slate-900 dark:text-white">${vp.current_days} &rarr; <span class="text-[#007CC3] dark:text-amber-300">${vp.next_level_days}</span></p>
<p class="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">${vp.advice || ''}</p>
          </div>

          <!-- 2. STİL VE DÖNEMLEME DEĞİŞİMİ KARTI -->
          <div class="bg-slate-50 dark:bg-slate-900/70 p-4 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
<div class="flex items-center justify-between gap-2">
  <span class="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-indigo-300">Stil & Rutin Değişimi</span>
  <span class="text-[10px] font-black px-2 py-0.5 rounded-full bg-blue-50 text-[#007CC3] border border-blue-200 dark:bg-blue-500/20 dark:text-blue-300">${st.verdict || '--'}</span>
</div>
<p class="text-xs font-bold text-slate-900 dark:text-white">Mevcut: <span class="text-emerald-700 dark:text-emerald-300">${st.current_style}</span></p>
<p class="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">${st.advice || ''}</p>
<p class="text-[10px] text-slate-700 dark:text-indigo-200 bg-white dark:bg-indigo-950/80 p-1.5 rounded border border-slate-200 dark:border-indigo-800/50">🏃 ${st.running_style_advice || ''}</p>
          </div>

          <!-- 3. DELOAD VE AŞIRI YORGUNLUK KARTI -->
          <div class="bg-slate-50 dark:bg-slate-900/70 p-4 rounded-xl border border-slate-200 dark:border-slate-700 space-y-2">
<div class="flex items-center justify-between gap-2">
  <span class="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-indigo-300">Deload & Esneklik</span>
  <span class="text-[10px] font-black px-2 py-0.5 rounded-full ${fd.needs_deload ? 'bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-500/20 dark:text-amber-300' : 'bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-500/20 dark:text-emerald-300'}">${fd.status || '--'}</span>
</div>
<p class="text-xs font-bold text-slate-900 dark:text-white">${fd.needs_deload ? 'Hacmi %40 Düşür' : 'Tam Güç & Kondisyon Aktif'}</p>
<p class="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">${fd.note || ''}</p>
<p class="text-[10px] text-amber-800 dark:text-amber-200/80 bg-amber-50 dark:bg-amber-950/40 p-1.5 rounded border border-amber-200 dark:border-amber-800/40">⚖️ <strong>Dogmatik Olmama Kuralı:</strong> Vücut yorgunluk ve düşük HRV verdiğinde seans asla zorlanmaz; hafif yürüyüş ve esnemeye çevrilir.</p>
          </div>
        `;
  }

  const tiersGrid = document.getElementById('athleteTiersGrid');
  if (tiersGrid && data.athlete_levels) {
    const tiers = Object.values(data.athlete_levels);
    tiersGrid.innerHTML = tiers.map(t => `
          <div class="bg-white dark:bg-slate-900/80 p-3 rounded-lg border border-slate-200 dark:border-slate-700 space-y-1.5">
<p class="font-black text-[#007CC3] dark:text-indigo-300 text-xs">${t.level_tr.split('(')[0]}</p>
<p class="text-[10px] text-slate-500 dark:text-slate-400 font-semibold">${t.recommended_split}</p>
<p class="text-[11px] text-slate-700 dark:text-slate-200 leading-snug">🏃 <strong>Koşu:</strong> ${t.running_approach.split('.')[0]}</p>
<p class="text-[11px] text-slate-700 dark:text-slate-200 leading-snug">🏋️ <strong>Kuvvet:</strong> ${t.strength_approach.split('.')[0]}</p>
<p class="text-[10px] text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/50 p-1.5 rounded border border-emerald-200 dark:border-emerald-800/40 mt-1">🚪 <strong>Geçiş Eşiği:</strong> ${t.progression_gate}</p>
          </div>
        `).join('');
  }
}

    // 8.7. DETAYLI GÜNLÜK ANTRENMAN PROTOKOLLERİ RENDER (SEKME FİLTRELİ)
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
        const activeCls = 'px-3 py-1.5 rounded-xl font-bold bg-[#111827] text-white dark:bg-white dark:text-neutral-950 transition';
        const idleCls = 'px-3 py-1.5 rounded-xl font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 transition';
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
<div class="overflow-x-auto custom-scrollbar mt-3">
  <table class="w-full text-left text-xs border-collapse">
    <thead>
      <tr class="bg-slate-100/90 text-slate-700 font-semibold border-b border-slate-200">
        <th class="py-2 px-2.5">#</th>
        <th class="py-2 px-2.5">Egzersiz</th>
        <th class="py-2 px-2.5">Set x Tekrar</th>
        <th class="py-2 px-2.5">Mevcut Telemetri & Hedef Ağırlık</th>
        <th class="py-2 px-2.5">Dinlenme & RPE</th>
        <th class="py-2 px-2.5">Koçluk İpucu & Form</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-slate-100 text-slate-700">
      ${(p.exercises || []).map(ex => `
        <tr class="hover:bg-slate-50/80">
          <td class="py-2 px-2.5 font-bold text-slate-400">${ex.num}</td>
          <td class="py-2 px-2.5 font-bold text-slate-900">${ex.name}</td>
          <td class="py-2 px-2.5 font-black text-blue-700">${ex.sets} x ${ex.reps}</td>
          <td class="py-2 px-2.5">
            <span class="font-bold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">${ex.target_weight}</span>
            ${ex.current_achieved ? `<p class="text-[10px] text-slate-400 mt-0.5">Son: ${ex.current_achieved}</p>` : ''}
          </td>
          <td class="py-2 px-2.5 text-slate-600">${ex.rest_sec} <span class="text-slate-400">(${ex.target_rpe || 'RPE 8'})</span></td>
          <td class="py-2 px-2.5 text-[11px] text-slate-600 leading-snug">${ex.coaching_cue}</td>
        </tr>
      `).join('')}
    </tbody>
  </table>
</div>
          `;
        } else if (p.category === 'running') {
          const runEx = (p.exercises || [])[0] || {};
          exerciseHtml = `
<div class="bg-slate-50 border border-slate-200/80 p-3.5 rounded-xl space-y-2 mt-3">
  <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
    <div>
      <p class="text-[10px] font-bold text-slate-500 uppercase">Süre / Mesafe</p>
      <p class="font-black text-slate-900 text-sm mt-0.5">${runEx.duration || (runEx.sets + ' x ' + runEx.reps)}</p>
      ${runEx.distance_est ? `<p class="text-[10px] text-slate-500">${runEx.distance_est}</p>` : ''}
    </div>
    <div>
      <p class="text-[10px] font-bold text-slate-500 uppercase">Hedef Nabız</p>
      <p class="font-black text-emerald-700 text-sm mt-0.5">${runEx.target_hr}</p>
    </div>
    <div>
      <p class="text-[10px] font-bold text-slate-500 uppercase">Hedef Tempo</p>
      <p class="font-black text-blue-700 text-sm mt-0.5">${runEx.target_pace}</p>
    </div>
    <div>
      <p class="text-[10px] font-bold text-slate-500 uppercase">Hedef Kadans</p>
      <p class="font-black text-purple-700 text-sm mt-0.5">${runEx.cadence_target}</p>
    </div>
  </div>
  <p class="text-xs text-slate-700 pt-1 border-t border-slate-200/60"><strong class="text-slate-900">Koçluk Talimatı:</strong> ${runEx.coaching_cue}</p>
</div>
          `;
        } else {
          const restEx = (p.exercises || [])[0] || {};
          exerciseHtml = `
<div class="bg-slate-50 border border-slate-200/80 p-3.5 rounded-xl space-y-1 mt-3 text-xs">
  <p class="font-bold text-slate-800">${restEx.protocol}</p>
  <p class="text-[11px] text-slate-600">${restEx.coaching_cue}</p>
</div>
          `;
        }

        return `
          <div class="border border-slate-200 rounded-2xl p-4 bg-white hover:border-indigo-300 transition shadow-sm space-y-3">
<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
  <div class="flex items-center space-x-2">
    <span class="text-xs font-black px-2.5 py-1 rounded-full bg-${p.badge_color}-100 text-${p.badge_color}-800 border border-${p.badge_color}-200">${p.badge}</span>
    <h4 class="text-sm font-black text-slate-900">${p.day_title}</h4>
  </div>
  <span class="text-[11px] font-bold text-slate-500">${p.status_note}</span>
</div>

<p class="text-xs text-slate-700"><strong class="text-slate-900">Günün Hedefi:</strong> ${p.objective}</p>
<p class="text-xs text-slate-600 bg-amber-50/70 border border-amber-200/70 p-2 rounded-lg"><strong class="text-amber-900">Isınma & Mobilite:</strong> ${p.warmup}</p>

${exerciseHtml}

<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-slate-100 text-[11px] text-slate-500">
  <p><strong class="text-slate-700">Soğuma:</strong> ${p.cooldown}</p>
  <p class="font-bold text-slate-700 bg-slate-50 px-2 py-1 rounded border border-slate-200">🥗 ${p.telemetry_targets ? p.telemetry_targets.nutrition : ''}</p>
</div>
          </div>
        `;
      }).join('');
    }

// AI KOÇ CHAT (GERÇEK LLM ENTEGRASYONU)
let chatHistory = [];



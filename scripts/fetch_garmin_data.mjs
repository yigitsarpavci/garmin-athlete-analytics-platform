#!/usr/bin/env node
/**
 * Garmin Connect 3-Month Data Fetcher
 * Uses @etweisberg/garmin-connect-mcp's GarminClient (Playwright TLS bypass)
 * and ~/.garmin-connect-mcp/session.json to pull the latest 93 days of:
 *   1. Activities (last 100 activities -> data/raw_activities.json)
 *   2. Sleep & Overnight HRV stats (25-day chunks -> data/raw_sleep_stats.json)
 *   3. Daily Summaries & Training Readiness (93 days -> data/raw_daily_93d.json)
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";
import { inflateRawSync } from "node:zlib";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.resolve(__dirname, "../data");
const FIT_DIR = path.join(DATA_DIR, "fit_files");
const SESSION_FILE = path.join(os.homedir(), ".garmin-connect-mcp", "session.json");
fs.mkdirSync(DATA_DIR, { recursive: true });
fs.mkdirSync(FIT_DIR, { recursive: true });

function extractFitFromZip(buf, activityId) {
  let eocdOffset = buf.length - 22;
  while (eocdOffset >= 0) {
    if (
      buf[eocdOffset] === 0x50 &&
      buf[eocdOffset + 1] === 0x4b &&
      buf[eocdOffset + 2] === 0x05 &&
      buf[eocdOffset + 3] === 0x06
    ) {
      break;
    }
    eocdOffset--;
  }
  if (eocdOffset < 0) return null;

  const cdOffset = buf.readUInt32LE(eocdOffset + 16);
  const cdEntries = buf.readUInt16LE(eocdOffset + 10);
  let pos = cdOffset;
  for (let i = 0; i < cdEntries; i++) {
    if (
      buf[pos] !== 0x50 ||
      buf[pos + 1] !== 0x4b ||
      buf[pos + 2] !== 0x01 ||
      buf[pos + 3] !== 0x02
    ) {
      break;
    }
    const method = buf.readUInt16LE(pos + 10);
    const compressedSize = buf.readUInt32LE(pos + 20);
    const uncompressedSize = buf.readUInt32LE(pos + 24);
    const nameLength = buf.readUInt16LE(pos + 28);
    const extraLength = buf.readUInt16LE(pos + 30);
    const commentLength = buf.readUInt16LE(pos + 32);
    const localHeaderOffset = buf.readUInt32LE(pos + 42);
    const name = buf.toString("utf-8", pos + 46, pos + 46 + nameLength);
    if (name.endsWith(".fit")) {
      const localNameLen = buf.readUInt16LE(localHeaderOffset + 26);
      const localExtraLen = buf.readUInt16LE(localHeaderOffset + 28);
      const dataStart = localHeaderOffset + 30 + localNameLen + localExtraLen;
      if (method === 0) {
        return {
          name: `${activityId}.fit`,
          data: Buffer.from(buf.subarray(dataStart, dataStart + uncompressedSize)),
        };
      }
      if (method === 8) {
        const compressed = buf.subarray(dataStart, dataStart + compressedSize);
        return { name: `${activityId}.fit`, data: inflateRawSync(compressed) };
      }
    }
    pos += 46 + nameLength + extraLength + commentLength;
  }
  return null;
}

// Python sunucusu dosyaları sync sırasında okuyabilir; yarım yazılmış JSON görmemesi için
// önce geçici dosyaya yazıp ardından atomik rename uygulanır.
function writeFileAtomic(filePath, data, options) {
  const tmpPath = `${filePath}.${process.pid}.tmp`;
  fs.writeFileSync(tmpPath, data, options);
  fs.renameSync(tmpPath, filePath);
}

function readJsonSafe(filePath, fallback) {
  if (!fs.existsSync(filePath)) return fallback;
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8")) || fallback;
  } catch {
    return fallback;
  }
}

function findGarminClientPath() {
  const out = execSync(
    'find ~/.npm/_npx -path "*/@etweisberg/garmin-connect-mcp/dist/garmin-client.js" 2>/dev/null | head -n 1',
    { encoding: "utf-8" }
  ).trim();
  if (!out) {
    throw new Error(
      "garmin-connect-mcp bulunamadı. Önce `npx -y @etweisberg/garmin-connect-mcp` çalıştırın."
    );
  }
  return out;
}

function formatDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function decodeJwtExp(token) {
  if (!token || typeof token !== "string" || token.split(".").length !== 3) {
    return null;
  }
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    const payload = JSON.parse(Buffer.from(padded, "base64").toString("utf-8"));
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

async function persistRefreshedSession(client) {
  if (!fs.existsSync(SESSION_FILE) || !client?.page) return null;
  const existing = readJsonSafe(SESSION_FILE, {});
  const oldCookies = Array.isArray(existing.cookies) ? existing.cookies : [];
  let liveCookies = [];
  try {
    liveCookies = (await client.page.context().cookies()).filter(
      (c) => c.domain && c.domain.includes("garmin")
    );
  } catch {
    liveCookies = [];
  }

  const cookieMap = new Map();
  for (const c of oldCookies) {
    if (c && c.name && c.domain) {
      cookieMap.set(`${c.domain}::${c.name}`, { name: c.name, value: c.value, domain: c.domain });
    }
  }
  for (const c of liveCookies) {
    if (c && c.name && c.domain) {
      cookieMap.set(`${c.domain}::${c.name}`, { name: c.name, value: c.value, domain: c.domain });
    }
  }

  let csrf = existing.csrf_token || client.csrfToken || "";
  try {
    const metaCsrf = await client.page.evaluate(
      () => document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || ""
    );
    if (metaCsrf && metaCsrf !== "NOT_FOUND") {
      csrf = metaCsrf;
      client.csrfToken = metaCsrf;
    }
  } catch {
    // status.json sayfasında meta etiket olmayabilir; mevcut csrf korunur
  }

  const mergedCookies = Array.from(cookieMap.values());
  const jwtCookie = mergedCookies.find((c) => c.name === "JWT_WEB");
  const rawJwtExp = decodeJwtExp(jwtCookie?.value);
  // Gerçek çerez bitişi; bilinmiyorsa null (uydurma 24 saatlik kira yazılmaz)
  const jwtExp = rawJwtExp && rawJwtExp > 0 ? rawJwtExp : null;

  const nextSession = {
    ...existing,
    csrf_token: csrf,
    cookies: mergedCookies,
    last_keepalive_at: new Date().toISOString(),
    jwt_expires_at: jwtExp,
  };

  const tmpPath = `${SESSION_FILE}.tmp`;
  fs.writeFileSync(tmpPath, JSON.stringify(nextSession, null, 2), { mode: 0o600 });
  fs.renameSync(tmpPath, SESSION_FILE);
  return { jwt_expires_at: jwtExp, cookie_count: mergedCookies.length };
}

async function attemptSilentSsoRefresh(client) {
  try {
    if (!client.page) {
      await client.init();
    }
    await client.page.goto("https://connect.garmin.com/app/activities", {
      waitUntil: "domcontentloaded",
      timeout: 25000,
    });
    await client.page.waitForTimeout(3000);
    const metaCsrf = await client.page.evaluate(
      () => document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || ""
    );
    if (metaCsrf && metaCsrf !== "NOT_FOUND") {
      client.csrfToken = metaCsrf;
    }
    const freshCookies = (await client.page.context().cookies()).filter(
      (c) => c.domain && c.domain.includes("garmin")
    );
    if (freshCookies.length) {
      client.cookies = freshCookies.map((c) => ({ name: c.name, value: c.value, domain: c.domain }));
    }
    await client.get("userprofile-service/userprofile/settings");
    return true;
  } catch {
    return false;
  }
}

const LOCK_FILE = path.join(DATA_DIR, ".sync.lock");
const LOCK_MAX_AGE_MS = 15 * 60 * 1000;

/** Aynı anda yalnızca tek bir çekim çalışsın (sunucu otomatik sync'i + elle `make fetch` veri dosyalarını bozmasın). */
function acquireSyncLock() {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      fs.writeFileSync(LOCK_FILE, JSON.stringify({ pid: process.pid, at: Date.now() }), { flag: "wx" });
      const release = () => { try { fs.unlinkSync(LOCK_FILE); } catch {} };
      process.on("exit", release);
      for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => { release(); process.exit(130); });
      return true;
    } catch (e) {
      if (e.code !== "EEXIST") return true; // kilit dosyası yazılamıyorsa engelleme
      let holder = {};
      try { holder = JSON.parse(fs.readFileSync(LOCK_FILE, "utf8")); } catch {}
      let alive = false;
      try { process.kill(holder.pid, 0); alive = true; } catch {}
      if (alive && Date.now() - (holder.at || 0) < LOCK_MAX_AGE_MS) return false;
      try { fs.unlinkSync(LOCK_FILE); } catch {}
    }
  }
  return false;
}

async function main() {
  const isKeepaliveOnly = process.argv.includes("--keepalive");
  if (!isKeepaliveOnly && !acquireSyncLock()) {
    console.log(JSON.stringify({ already_running: true }));
    process.exitCode = 3;
    return;
  }
  const clientPath = findGarminClientPath();
  const { GarminClient } = await import(clientPath);
  const client = new GarminClient();

  try {
    await client.init();
    let displayName;
    try {
      displayName = await client.getDisplayName();
    } catch (err) {
      if (String(err?.message || "").includes("401")) {
        const refreshed = await attemptSilentSsoRefresh(client);
        if (!refreshed) throw err;
        displayName = await client.getDisplayName();
      } else {
        throw err;
      }
    }

    const persisted = await persistRefreshedSession(client);
    if (isKeepaliveOnly) {
      console.log(JSON.stringify({
        keepalive: true,
        displayName,
        ...(persisted || {}),
        at: new Date().toISOString(),
      }));
      return;
    }

    const endDate = new Date();
    const yesterdayDate = new Date(endDate);
    yesterdayDate.setDate(yesterdayDate.getDate() - 1);
    const yesterdayStr = formatDate(yesterdayDate);
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - 92); // 93 days inclusive

    console.log(`[1/9] Son 100 aktivite çekiliyor...`);
    const acts = await client.get(
      "activitylist-service/activities/search/activities",
      { limit: 100, start: 0 }
    );
    writeFileAtomic(
      path.join(DATA_DIR, "raw_activities.json"),
      JSON.stringify(acts, null, 2)
    );
    await persistRefreshedSession(client);

    console.log(`[2/9] Uyku ve HRV istatistikleri çekiliyor (25 günlük bloklar)...`);
    const sleepDays = {};
    let cur = new Date(startDate);
    cur.setUTCDate(cur.getUTCDate() - 15); // extra buffer
    while (cur <= endDate) {
      const chunkEnd = new Date(cur);
      chunkEnd.setUTCDate(chunkEnd.getUTCDate() + 24);
      const actualEnd = chunkEnd > endDate ? endDate : chunkEnd;
      const sStr = formatDate(cur);
      const eStr = formatDate(actualEnd);
      const res = await client.get(
        `sleep-service/stats/sleep/daily/${sStr}/${eStr}`
      );
      for (const item of res?.individualStats || []) {
        sleepDays[item.calendarDate] = item.values;
      }
      cur = new Date(actualEnd);
      cur.setUTCDate(cur.getUTCDate() + 1);
    }
    writeFileAtomic(
      path.join(DATA_DIR, "raw_sleep_stats.json"),
      JSON.stringify(sleepDays, null, 2)
    );

    console.log(`[3/9] 93 günlük özet ve Training Readiness verileri çekiliyor...`);
    const dates = [];
    for (
      let d = new Date(startDate);
      d <= endDate;
      d.setUTCDate(d.getUTCDate() + 1)
    ) {
      dates.push(formatDate(d));
    }

    // Artımlı çekme: 3 günden eski ve hatasız kayıtlar kesinleşmiştir, yeniden istenmez (--full ile zorlanır).
    // Böylece her eşitleme ~190 yerine genellikle birkaç Garmin isteği yapar (hız sınırı / hesap işaretlenme riski azalır).
    const forceFull = process.argv.includes("--full");
    const existingDaily = forceFull ? {} : readJsonSafe(path.join(DATA_DIR, "raw_daily_93d.json"), {});
    const summaries = {};
    const readiness = {};
    const finalizedCutoff = formatDate(new Date(endDate.getTime() - 3 * 86400000));
    const isFinal = (obj) => obj && typeof obj === "object" && !obj.error && Object.keys(obj).length > 0;
    const pending = [];
    for (const dt of dates) {
      const oldS = existingDaily.summaries?.[dt];
      const oldR = existingDaily.readiness?.[dt];
      if (dt < finalizedCutoff && isFinal(oldS) && oldR !== undefined && !(oldR && oldR.error)) {
        summaries[dt] = oldS;
        readiness[dt] = oldR;
      } else {
        pending.push(dt);
      }
    }
    console.log(`  ${dates.length - pending.length} gün önbellekten, ${pending.length} gün Garmin'den çekilecek.`);
    for (let i = 0; i < pending.length; i += 10) {
      const batch = pending.slice(i, i + 10);
      await Promise.all(
        batch.map(async (dt) => {
          try {
            summaries[dt] = await client.get(
              `usersummary-service/usersummary/daily/${displayName}`,
              { calendarDate: dt }
            );
          } catch (e) {
            summaries[dt] = { error: e.message };
          }
          try {
            readiness[dt] = await client.get(
              `metrics-service/metrics/trainingreadiness/${dt}`
            );
          } catch (e) {
            readiness[dt] = { error: e.message };
          }
        })
      );
      process.stdout.write(`.${Math.min(i + 10, pending.length)}`);
    }
    console.log("\n93 günlük özet ve readiness tamamlandı.");
    writeFileAtomic(
      path.join(DATA_DIR, "raw_daily_93d.json"),
      JSON.stringify({ summaries, readiness }, null, 2)
    );

    console.log(`[4/9] Firstbeat Training Status, ACWR, Yük Dengesi ve VO2 Max çekiliyor...`);
    const todayStr = formatDate(endDate);
    try {
      const aggLatest = await client.get(`metrics-service/metrics/trainingstatus/aggregated/${todayStr}`);
      // Gün başında Garmin boş (null) dönebilir; dolu eski kaydı bozmamak için yalnızca veri varsa yaz.
      if (aggLatest && (aggLatest.mostRecentTrainingStatus || aggLatest.mostRecentTrainingLoadBalance)) {
        writeFileAtomic(path.join(DATA_DIR, "raw_training_status_latest.json"), JSON.stringify(aggLatest, null, 2));
      } else {
        console.warn("Training status latest boş döndü; önceki kayıt korundu.");
      }
    } catch (e) {
      console.warn("Training status latest çekilemedi:", e.message);
    }

    try {
      const vo2History = await client.get(`metrics-service/metrics/maxmet/daily/${formatDate(startDate)}/${todayStr}`);
      writeFileAtomic(path.join(DATA_DIR, "raw_vo2max_history.json"), JSON.stringify(vo2History, null, 2));
    } catch (e) {
      console.warn("VO2 max history çekilemedi:", e.message);
    }

    // Haftalık durum çekimi (her Pazar ve bugün)
    const weeklyDates = [];
    let wDate = new Date(startDate);
    while (wDate <= endDate) {
      if (wDate.getUTCDay() === 0) { // Sunday
        weeklyDates.push(formatDate(wDate));
      }
      wDate.setUTCDate(wDate.getUTCDate() + 1);
    }
    if (!weeklyDates.includes(todayStr)) weeklyDates.push(todayStr);

    // Geçmiş pazar günlerinin durum özetleri değişmez; yalnızca son 8 gün ve eksikler yeniden çekilir.
    const existingWeekly = forceFull ? {} : readJsonSafe(path.join(DATA_DIR, "raw_training_status_weekly.json"), {});
    const weeklyCutoff = formatDate(new Date(endDate.getTime() - 8 * 86400000));
    const weeklyStatus = {};
    for (const dt of weeklyDates) {
      if (dt < weeklyCutoff && existingWeekly[dt] && Object.keys(existingWeekly[dt]).length) {
        weeklyStatus[dt] = existingWeekly[dt];
        continue;
      }
      try {
        const fetched = await client.get(`metrics-service/metrics/trainingstatus/aggregated/${dt}`);
        if (fetched && (fetched.mostRecentTrainingStatus || fetched.mostRecentTrainingLoadBalance)) {
          weeklyStatus[dt] = fetched;
        } else if (existingWeekly[dt] && Object.keys(existingWeekly[dt]).length) {
          weeklyStatus[dt] = existingWeekly[dt];
        }
      } catch (e) {
        console.warn(`Haftalık durum çekilemedi (${dt}):`, e.message);
      }
    }
    writeFileAtomic(path.join(DATA_DIR, "raw_training_status_weekly.json"), JSON.stringify(weeklyStatus, null, 2));

    console.log(`[5/9] Tartı ve vücut kompozisyonu verileri çekiliyor...`);
    try {
      const weightData = await client.get("weight-service/weight/dateRange", {
        startDate: formatDate(startDate),
        endDate: todayStr,
      });
      if (weightData) {
        writeFileAtomic(
          path.join(DATA_DIR, "raw_weight.json"),
          JSON.stringify(weightData, null, 2)
        );
      }
    } catch (e) {
      console.warn("Tartı/kilo verisi çekilemedi:", e.message);
    }

    // Sporcu profili (yaş, boy, cinsiyet, laktat eşiği): kod içinde kişisel sabit tutulmaz, Garmin'den okunur.
    // Yalnızca gerekli alanlar saklanır (e-posta, kullanıcı adı vb. kişisel alanlar yazılmaz).
    try {
      const settings = await client.get("userprofile-service/userprofile/user-settings");
      const ud = settings?.userData || {};
      const profile = {
        userData: {
          birthDate: ud.birthDate ?? null,
          gender: ud.gender ?? null,
          height: ud.height ?? null,
          weight: ud.weight ?? null,
          lactateThresholdHeartRate: ud.lactateThresholdHeartRate ?? null,
          vo2MaxRunning: ud.vo2MaxRunning ?? null,
        },
        fetched_at: new Date().toISOString(),
      };
      writeFileAtomic(path.join(DATA_DIR, "raw_profile.json"), JSON.stringify(profile, null, 2));
    } catch (e) {
      console.warn("Kullanıcı profili çekilemedi (athlete_profile.json ile elle girilebilir):", e.message);
    }

    console.log(`[6/9] Kuvvet antrenmanı egzersiz setleri çekiliyor...`);
    try {
      const gymSetsPath = path.join(DATA_DIR, "raw_gym_exercise_sets.json");
      const existingGymSets = readJsonSafe(gymSetsPath, {});
      const strengthActs = Array.isArray(acts)
        ? acts.filter((a) => {
            const tKey = (a?.activityType?.typeKey || "").toLowerCase();
            return tKey.includes("strength") || tKey.includes("fitness_equipment");
          })
        : [];
      for (const act of strengthActs) {
        const aid = String(act?.activityId || "");
        if (!aid || existingGymSets[aid]?.sets?.length || existingGymSets[aid]?.exerciseSets?.length) continue;
        try {
          const exSets = await client.get(`activity-service/activity/${aid}/exerciseSets`);
          if (exSets) {
            const setList = Array.isArray(exSets)
              ? exSets
              : (exSets.exerciseSets || exSets.sets || []);
            existingGymSets[aid] = { meta: act, sets: setList };
          }
        } catch (e) {
          console.warn(`Salon seti çekilemedi (${aid}):`, e.message);
        }
      }
      writeFileAtomic(gymSetsPath, JSON.stringify(existingGymSets, null, 2));
    } catch (e) {
      console.warn("Salon egzersiz setleri çekilemedi:", e.message);
    }

    console.log(`[7/9] Orijinal .fit dosyaları, saniye bazlı detaylar ve splitler çekiliyor...`);
    try {
      const streamsPath = path.join(DATA_DIR, "raw_high_res_streams.json");
      const existingStreams = readJsonSafe(streamsPath, { activities: {} });
      if (!existingStreams.activities || typeof existingStreams.activities !== "object") {
        existingStreams.activities = {};
      }
      const targetActs = Array.isArray(acts)
        ? acts.filter((a) => {
            const tKey = (a?.activityType?.typeKey || "").toLowerCase();
            return tKey.includes("running") || tKey.includes("strength") || tKey.includes("fitness_equipment");
          }).slice(0, 10)
        : [];
      for (const act of targetActs) {
        const aid = String(act?.activityId || "");
        if (!aid) continue;
        const fitPath = path.join(FIT_DIR, `${aid}.fit`);
        if (!fs.existsSync(fitPath)) {
          try {
            const zipBytes = await client.getBytes(`download-service/files/activity/${aid}`);
            const fitFile = extractFitFromZip(zipBytes, aid);
            if (fitFile?.data) {
              writeFileAtomic(fitPath, fitFile.data);
            }
          } catch (e) {
            console.warn(`FIT dosyası indirilemedi (${aid}):`, e.message);
          }
        }
        const cached = existingStreams.activities[aid] || {};
        if (!cached.details || !cached.splits) {
          try {
            const details = cached.details || await client.get(`activity-service/activity/${aid}/details`, {
              maxChartSize: 10000,
              maxPolylineSize: 0,
              maxHeatMapSize: 2000,
            });
            const splits = cached.splits || await client.get(`activity-service/activity/${aid}/splits`);
            existingStreams.activities[aid] = {
              activityId: Number(aid) || aid,
              activityName: act.activityName || "",
              sport: act?.activityType?.typeKey || "",
              startTimeLocal: act.startTimeLocal || "",
              source: "garmin_api",
              fit_file: fs.existsSync(fitPath) ? `fit_files/${aid}.fit` : null,
              details,
              splits,
            };
          } catch (e) {
            console.warn(`Aktivite yüksek çözünürlük akışı çekilemedi (${aid}):`, e.message);
          }
        }
      }
      existingStreams.updated_at = new Date().toISOString();
      writeFileAtomic(streamsPath, JSON.stringify(existingStreams, null, 2));
    } catch (e) {
      console.warn("FIT & detay akışı çekilemedi:", e.message);
    }

    console.log(`[8/9] Gecelik 5 dakikalık yüksek çözünürlüklü HRV (hrv-service) çekiliyor...`);
    try {
      const hrvPath = path.join(DATA_DIR, "raw_hrv_5min.json");
      const hrvDays = readJsonSafe(hrvPath, {});
      const recentDates14 = dates.slice(-14);
      for (const dt of recentDates14) {
        if (dt < yesterdayStr && hrvDays[dt]?.hrvReadings?.length) continue;
        try {
          const hrvRes = await client.get(`hrv-service/hrv/${dt}`);
          if (hrvRes && !hrvRes.noData) {
            hrvDays[dt] = hrvRes;
          }
        } catch (e) {
          console.warn(`5dk HRV çekilemedi (${dt}):`, e.message);
        }
      }
      writeFileAtomic(hrvPath, JSON.stringify(hrvDays, null, 2));
    } catch (e) {
      console.warn("HRV 5dk eğrisi çekilemedi:", e.message);
    }

    console.log(`[9/9] Günlük solunum hızı zaman serileri (respiration) çekiliyor...`);
    try {
      const respPath = path.join(DATA_DIR, "raw_respiration_daily.json");
      const respDays = readJsonSafe(respPath, {});
      const recentDates14 = dates.slice(-14);
      for (const dt of recentDates14) {
        if (dt < yesterdayStr && respDays[dt]?.respirationValuesArray?.length) continue;
        try {
          const respRes = await client.get(`wellness-service/wellness/daily/respiration/${dt}`);
          if (respRes && !respRes.noData) {
            respDays[dt] = respRes;
          }
        } catch (e) {
          console.warn(`Solunum verisi çekilemedi (${dt}):`, e.message);
        }
      }
      writeFileAtomic(respPath, JSON.stringify(respDays, null, 2));
    } catch (e) {
      console.warn("Günlük solunum verisi çekilemedi:", e.message);
    }

    await persistRefreshedSession(client);
    console.log("Tüm Garmin verileri (yüksek çözünürlüklü FIT/HRV/RD kanalları dahil) güncellendi.");
  } catch (err) {
    const msg = String(err?.message || "");
    if (msg.includes("401") || msg.includes("Session invalid") || msg.toLowerCase().includes("expired")) {
      console.log(JSON.stringify({
        ...(isKeepaliveOnly ? { keepalive: false } : { synced: false }),
        session_expired: true,
        remote_401: true,
        error: msg,
        at: new Date().toISOString(),
      }));
      process.exitCode = 2;
      return;
    }
    throw err;
  } finally {
    await client.close().catch(() => {});
  }
}

main().catch((err) => {
  console.error("Hata:", err.message);
  process.exit(1);
});

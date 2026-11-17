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
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.resolve(__dirname, "../data");
fs.mkdirSync(DATA_DIR, { recursive: true });

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
  return d.toISOString().slice(0, 10);
}

async function main() {
  const clientPath = findGarminClientPath();
  const { GarminClient } = await import(clientPath);
  const client = new GarminClient();

  try {
    await client.init();
    const displayName = await client.getDisplayName();

    const endDate = new Date();
    const startDate = new Date(endDate);
    startDate.setUTCDate(startDate.getUTCDate() - 92); // 93 days inclusive

    console.log(`[1/3] Son 100 aktivite çekiliyor...`);
    const acts = await client.get(
      "activitylist-service/activities/search/activities",
      { limit: 100, start: 0 }
    );
    fs.writeFileSync(
      path.join(DATA_DIR, "raw_activities.json"),
      JSON.stringify(acts, null, 2)
    );

    console.log(`[2/3] Uyku ve HRV istatistikleri çekiliyor (25 günlük bloklar)...`);
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
    fs.writeFileSync(
      path.join(DATA_DIR, "raw_sleep_stats.json"),
      JSON.stringify(sleepDays, null, 2)
    );

    console.log(`[3/3] 93 günlük özet ve Training Readiness verileri çekiliyor...`);
    const dates = [];
    for (
      let d = new Date(startDate);
      d <= endDate;
      d.setUTCDate(d.getUTCDate() + 1)
    ) {
      dates.push(formatDate(d));
    }

    const summaries = {};
    const readiness = {};
    for (let i = 0; i < dates.length; i += 10) {
      const batch = dates.slice(i, i + 10);
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
      process.stdout.write(`.${Math.min(i + 10, dates.length)}`);
    }
    console.log("\n93 günlük özet ve readiness tamamlandı.");
    fs.writeFileSync(
      path.join(DATA_DIR, "raw_daily_93d.json"),
      JSON.stringify({ summaries, readiness }, null, 2)
    );

    console.log(`[4/4] Firstbeat Training Status, ACWR, Yük Dengesi ve VO2 Max çekiliyor...`);
    const todayStr = formatDate(endDate);
    try {
      const aggLatest = await client.get(`metrics-service/metrics/trainingstatus/aggregated/${todayStr}`);
      fs.writeFileSync(path.join(DATA_DIR, "raw_training_status_latest.json"), JSON.stringify(aggLatest, null, 2));
    } catch (e) {
      console.warn("Training status latest çekilemedi:", e.message);
    }

    try {
      const vo2History = await client.get(`metrics-service/metrics/maxmet/daily/${formatDate(startDate)}/${todayStr}`);
      fs.writeFileSync(path.join(DATA_DIR, "raw_vo2max_history.json"), JSON.stringify(vo2History, null, 2));
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

    const weeklyStatus = {};
    for (const dt of weeklyDates) {
      try {
        weeklyStatus[dt] = await client.get(`metrics-service/metrics/trainingstatus/aggregated/${dt}`);
      } catch (e) {}
    }
    fs.writeFileSync(path.join(DATA_DIR, "raw_training_status_weekly.json"), JSON.stringify(weeklyStatus, null, 2));

    console.log(`[5/6] Tartı ve vücut kompozisyonu verileri çekiliyor...`);
    try {
      const weightData = await client.get("weight-service/weight/dateRange", {
        startDate: formatDate(startDate),
        endDate: todayStr,
      });
      if (weightData) {
        fs.writeFileSync(
          path.join(DATA_DIR, "raw_weight.json"),
          JSON.stringify(weightData, null, 2)
        );
      }
    } catch (e) {
      console.warn("Tartı/kilo verisi çekilemedi:", e.message);
    }

    console.log(`[6/6] Kuvvet antrenmanı egzersiz setleri çekiliyor...`);
    try {
      const gymSetsPath = path.join(DATA_DIR, "raw_gym_exercise_sets.json");
      let existingGymSets = {};
      if (fs.existsSync(gymSetsPath)) {
        try {
          existingGymSets = JSON.parse(fs.readFileSync(gymSetsPath, "utf-8")) || {};
        } catch (e) {
          existingGymSets = {};
        }
      }
      const strengthActs = Array.isArray(acts)
        ? acts.filter((a) => {
            const tKey = (a?.activityType?.typeKey || "").toLowerCase();
            return tKey.includes("strength") || tKey.includes("fitness_equipment");
          })
        : [];
      for (const act of strengthActs) {
        const aid = String(act?.activityId || "");
        if (!aid || existingGymSets[aid]?.sets?.length) continue;
        try {
          const exSets = await client.get(`activity-service/activity/${aid}/exerciseSets`);
          if (exSets) {
            existingGymSets[aid] = exSets;
          }
        } catch (e) {
          console.warn(`Salon seti çekilemedi (${aid}):`, e.message);
        }
      }
      fs.writeFileSync(gymSetsPath, JSON.stringify(existingGymSets, null, 2));
    } catch (e) {
      console.warn("Salon egzersiz setleri çekilemedi:", e.message);
    }

    console.log("Tüm Garmin verileri başarıyla güncellendi.");
  } finally {
    await client.close();
  }
}

main().catch((err) => {
  console.error("Hata:", err.message);
  process.exit(1);
});

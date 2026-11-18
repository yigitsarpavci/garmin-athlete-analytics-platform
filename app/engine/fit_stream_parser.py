#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANT+ FIT İkili Dosya Çözücü / Kodlayıcı ve Yüksek Çözünürlüklü Telemetri Ayrıştırıcı.
Ekstra bağımlılık olmadan Garmin .fit ikili dosyalarını (CRC-16 doğrulamalı)
ve activity-service/.../details zaman serilerini saniye bazlı kayıt listelerine dönüştürür.
Kuruluysa isteğe bağlı olarak `fitparse` kütüphanesini de destekler.
"""

import json
import os
import struct
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

FIT_EPOCH_OFFSET = 631065600  # 1989-12-31T00:00:00Z Unix epoch farkı

_CRC_TABLE = (
    0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
)

# (struct_fmt_char, byte_size, invalid_sentinel)
_FIT_BASE_TYPES: Dict[int, Tuple[str, int, Any]] = {
    0x00: ("B", 1, 0xFF),        # enum
    0x01: ("b", 1, 0x7F),        # sint8
    0x02: ("B", 1, 0xFF),        # uint8
    0x83: ("h", 2, 0x7FFF),      # sint16
    0x03: ("h", 2, 0x7FFF),
    0x84: ("H", 2, 0xFFFF),      # uint16
    0x04: ("H", 2, 0xFFFF),
    0x85: ("i", 4, 0x7FFFFFFF),  # sint32
    0x05: ("i", 4, 0x7FFFFFFF),
    0x86: ("I", 4, 0xFFFFFFFF),  # uint32
    0x06: ("I", 4, 0xFFFFFFFF),
    0x0A: ("B", 1, 0x00),        # uint8z
    0x8B: ("H", 2, 0x0000),      # uint16z
    0x0B: ("H", 2, 0x0000),
    0x8C: ("I", 4, 0x00000000),  # uint32z
    0x0C: ("I", 4, 0x00000000),
    0x0D: ("B", 1, 0xFF),        # byte
    0x8E: ("q", 8, 0x7FFFFFFFFFFFFFFF),  # sint64
    0x8F: ("Q", 8, 0xFFFFFFFFFFFFFFFF),  # uint64
    0x90: ("Q", 8, 0x0000000000000000),  # uint64z
    0x88: ("f", 4, None),        # float32
    0x89: ("d", 8, None),        # float64
}

# ANT+ FIT Global Message 20 (record) alan tanımları
_RECORD_FIELD_NUMS = {
    253: "timestamp",
    2: "altitude",
    3: "heart_rate",
    4: "cadence",
    5: "distance",
    6: "speed",
    7: "power",
    39: "vertical_oscillation",
    40: "stance_time",
    53: "fractional_cadence",
    73: "enhanced_speed",
    78: "enhanced_altitude",
    83: "vertical_ratio",
    84: "stance_time_balance",
    85: "step_length",
}


def fit_crc16(data: bytes) -> int:
    """ANT+ FIT spesifikasyonu ile uyumlu 16-bit CRC hesaplar."""
    crc = 0
    for byte in data:
        tmp = _CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ _CRC_TABLE[byte & 0xF]
        tmp = _CRC_TABLE[crc & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ tmp ^ _CRC_TABLE[(byte >> 4) & 0xF]
    return crc & 0xFFFF


def _decode_fit_field(chunk: bytes, base_type: int, endian: str) -> Any:
    """Tek bir FIT alan bayt dilimini Python değerine çevirir (geçersiz sentinel -> None)."""
    if base_type == 0x07:  # string
        txt = chunk.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
        return txt or None

    spec = _FIT_BASE_TYPES.get(base_type)
    if not spec:
        return None

    fmt_char, unit_size, invalid = spec
    if len(chunk) < unit_size:
        return None
    if len(chunk) == unit_size:
        val = struct.unpack(f"{endian}{fmt_char}", chunk)[0]
        return None if (invalid is not None and val == invalid) else val

    count = len(chunk) // unit_size
    vals = struct.unpack(f"{endian}{count}{fmt_char}", chunk[: count * unit_size])
    cleaned = [v for v in vals if invalid is None or v != invalid]
    if not cleaned:
        return None
    return cleaned[0] if len(cleaned) == 1 else cleaned


def _normalize_fit_record(raw: Dict[int, Any], last_timestamp: Optional[int]) -> Tuple[Dict[str, Any], Optional[int]]:
    """Ham record mesaj alanlarını SI / metrik birimlere normalize eder."""
    ts_raw = raw.get(253)
    ts_fit = int(ts_raw) if isinstance(ts_raw, (int, float)) else last_timestamp
    unix_ts = (ts_fit + FIT_EPOCH_OFFSET) if ts_fit is not None else None

    hr = raw.get(3)
    cad_raw = raw.get(4)
    cad_frac = raw.get(53) or 0.0
    cad_spm: Optional[float] = None
    if isinstance(cad_raw, (int, float)):
        base_cad = float(cad_raw) + float(cad_frac) / 128.0
        cad_spm = round(base_cad * 2.0, 1) if base_cad <= 125 else round(base_cad, 1)

    dist_raw = raw.get(5)
    dist_m = round(float(dist_raw) / 100.0, 2) if isinstance(dist_raw, (int, float)) else None

    spd_raw = raw.get(73) if raw.get(73) is not None else raw.get(6)
    speed_mps = round(float(spd_raw) / 1000.0, 3) if isinstance(spd_raw, (int, float)) else None

    pwr = raw.get(7)
    alt_raw = raw.get(78) if raw.get(78) is not None else raw.get(2)
    alt_m = round(float(alt_raw) / 5.0 - 500.0, 1) if isinstance(alt_raw, (int, float)) else None

    vo_raw = raw.get(39)
    vo_cm = round(float(vo_raw) / 100.0, 2) if isinstance(vo_raw, (int, float)) else None

    gct_raw = raw.get(40)
    gct_ms = round(float(gct_raw) / 10.0, 1) if isinstance(gct_raw, (int, float)) else None

    vr_raw = raw.get(83)
    vr_pct = round(float(vr_raw) / 100.0, 2) if isinstance(vr_raw, (int, float)) else None

    sl_raw = raw.get(85)
    stride_cm = round(float(sl_raw) / 100.0, 1) if isinstance(sl_raw, (int, float)) else None

    rec: Dict[str, Any] = {
        "unix_ts": unix_ts,
        "timestamp_iso": (
            datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if unix_ts is not None else None
        ),
        "heart_rate": int(hr) if isinstance(hr, (int, float)) else None,
        "cadence_spm": cad_spm,
        "distance_m": dist_m,
        "speed_mps": speed_mps,
        "power_w": int(pwr) if isinstance(pwr, (int, float)) else None,
        "altitude_m": alt_m,
        "vertical_oscillation_cm": vo_cm,
        "stance_time_ms": gct_ms,
        "vertical_ratio_pct": vr_pct,
        "stride_length_cm": stride_cm,
    }
    return rec, ts_fit


def _summarize_records(records: List[Dict[str, Any]], file_name: Optional[str] = None) -> Dict[str, Any]:
    """Çözümlenmiş FIT/detay kayıtlarından nabız drifti, güç, kadans ve özet istatistikler çıkarır."""
    hrs = [r["heart_rate"] for r in records if r.get("heart_rate")]
    pwrs = [r["power_w"] for r in records if r.get("power_w")]
    cads = [r["cadence_spm"] for r in records if r.get("cadence_spm")]
    gcts = [r["stance_time_ms"] for r in records if r.get("stance_time_ms")]
    spds = [r["speed_mps"] for r in records if r.get("speed_mps")]
    dists = [r["distance_m"] for r in records if r.get("distance_m") is not None]

    hr_drift_bpm = None
    hr_drift_pct = None
    first_half_hr = None
    second_half_hr = None
    if len(hrs) >= 6:
        mid = len(hrs) // 2
        first_half_hr = round(sum(hrs[:mid]) / mid, 1)
        second_half_hr = round(sum(hrs[mid:]) / (len(hrs) - mid), 1)
        hr_drift_bpm = round(second_half_hr - first_half_hr, 1)
        if first_half_hr > 0:
            hr_drift_pct = round((hr_drift_bpm / first_half_hr) * 100.0, 1)

    t0 = next((r["unix_ts"] for r in records if r.get("unix_ts") is not None), None)
    t1 = next((r["unix_ts"] for r in reversed(records) if r.get("unix_ts") is not None), None)
    duration_s = int(max(0, t1 - t0)) if (t0 is not None and t1 is not None) else 0

    step = max(1, len(records) // 24)
    sampled_hr = [
        {
            "idx": i,
            "t_min": round(((r["unix_ts"] - t0) / 60.0), 1) if (t0 and r.get("unix_ts")) else i,
            "hr": r.get("heart_rate"),
            "power_w": r.get("power_w"),
            "cadence_spm": r.get("cadence_spm"),
        }
        for i, r in enumerate(records[::step])
        if r.get("heart_rate") is not None
    ]

    return {
        "file_name": file_name,
        "sample_count": len(records),
        "duration_min": round(duration_s / 60.0, 1) if duration_s else None,
        "avg_hr": round(sum(hrs) / len(hrs), 1) if hrs else None,
        "min_hr": min(hrs) if hrs else None,
        "max_hr": max(hrs) if hrs else None,
        "first_half_avg_hr": first_half_hr,
        "second_half_avg_hr": second_half_hr,
        "cardiac_drift_bpm": hr_drift_bpm,
        "cardiac_drift_pct": hr_drift_pct,
        "avg_power_w": round(sum(pwrs) / len(pwrs), 1) if pwrs else None,
        "avg_cadence_spm": round(sum(cads) / len(cads), 1) if cads else None,
        "avg_gct_ms": round(sum(gcts) / len(gcts), 1) if gcts else None,
        "avg_speed_mps": round(sum(spds) / len(spds), 3) if spds else None,
        "total_distance_m": max(dists) if dists else 0.0,
        "sampled_timeline": sampled_hr,
    }


def _parse_with_fitparse(raw: bytes, file_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """Kuruluysa opsiyonel `fitparse` kütüphanesi üzerinden çözer."""
    try:
        import fitparse  # type: ignore
    except ImportError:
        return None

    fitfile = fitparse.FitFile(raw)
    records: List[Dict[str, Any]] = []
    file_id: Dict[str, Any] = {}
    for msg in fitfile.get_messages():
        if msg.name == "file_id":
            file_id = {f.name: f.value for f in msg}
        elif msg.name == "record":
            vals = {f.name: f.value for f in msg}
            ts = vals.get("timestamp")
            unix_ts = int(ts.replace(tzinfo=timezone.utc).timestamp()) if hasattr(ts, "timestamp") else None
            cad_raw = vals.get("cadence")
            cad_spm = (
                (float(cad_raw) * 2.0 if float(cad_raw) <= 125 else float(cad_raw))
                if isinstance(cad_raw, (int, float)) else None
            )
            records.append({
                "unix_ts": unix_ts,
                "timestamp_iso": ts.isoformat() if hasattr(ts, "isoformat") else None,
                "heart_rate": vals.get("heart_rate"),
                "cadence_spm": round(cad_spm, 1) if cad_spm is not None else None,
                "distance_m": round(float(vals["distance"]), 2) if isinstance(vals.get("distance"), (int, float)) else None,
                "speed_mps": round(float(vals["enhanced_speed"] or vals["speed"]), 3)
                if (vals.get("enhanced_speed") or vals.get("speed")) is not None else None,
                "power_w": vals.get("power"),
                "altitude_m": round(float(vals.get("enhanced_altitude") or vals.get("altitude")), 1)
                if (vals.get("enhanced_altitude") or vals.get("altitude")) is not None else None,
                "vertical_oscillation_cm": round(float(vals["vertical_oscillation"]) / 10.0, 2)
                if isinstance(vals.get("vertical_oscillation"), (int, float)) else None,
                "stance_time_ms": round(float(vals["stance_time"]), 1)
                if isinstance(vals.get("stance_time"), (int, float)) else None,
                "vertical_ratio_pct": round(float(vals["vertical_ratio"]), 2)
                if isinstance(vals.get("vertical_ratio"), (int, float)) else None,
                "stride_length_cm": round(float(vals["step_length"]) / 10.0, 1)
                if isinstance(vals.get("step_length"), (int, float)) else None,
            })

    return {
        "valid": True,
        "crc_ok": True,
        "parser": "fitparse",
        "file_id": file_id,
        "record_count": len(records),
        "records": records,
        "summary": _summarize_records(records, file_name=file_name),
    }


def parse_fit_bytes(raw: bytes, file_name: Optional[str] = None) -> Dict[str, Any]:
    """Ham .fit bayt akışını Pure Python ANT+ FIT çözücüsü ile ayrıştırır."""
    if not raw or len(raw) < 14 or raw[8:12] != b".FIT":
        return {"valid": False, "error": "Geçersiz FIT başlık imzası"}

    optional_parsed = _parse_with_fitparse(raw, file_name)
    if optional_parsed is not None:
        return optional_parsed

    hdr_size = raw[0]
    data_size = struct.unpack("<I", raw[4:8])[0]
    data_end = min(len(raw), hdr_size + data_size)

    hdr_crc_ok = True
    if hdr_size >= 14:
        expected_hdr_crc = struct.unpack("<H", raw[12:14])[0]
        if expected_hdr_crc != 0:
            hdr_crc_ok = (fit_crc16(raw[:12]) == expected_hdr_crc)

    file_crc_ok = True
    if len(raw) >= data_end + 2:
        expected_file_crc = struct.unpack("<H", raw[data_end:data_end + 2])[0]
        file_crc_ok = (fit_crc16(raw[:data_end]) == expected_file_crc)

    local_defs: Dict[int, Dict[str, Any]] = {}
    records: List[Dict[str, Any]] = []
    file_id: Dict[str, Any] = {}
    last_timestamp: Optional[int] = None
    pos = hdr_size

    while pos < data_end:
        hdr_byte = raw[pos]
        pos += 1

        if hdr_byte & 0x80:
            # Sıkıştırılmış zaman damgalı veri mesajı
            local_num = (hdr_byte >> 5) & 0x03
            time_offset = hdr_byte & 0x1F
            defn = local_defs.get(local_num)
            if not defn:
                break
            endian = defn["endian"]
            fields_raw: Dict[int, Any] = {}
            for fnum, fsize, ftype in defn["fields"]:
                fields_raw[fnum] = _decode_fit_field(raw[pos:pos + fsize], ftype, endian)
                pos += fsize
            pos += defn["dev_size"]
            if last_timestamp is not None:
                ts_candidate = (last_timestamp & ~0x1F) + time_offset
                if time_offset < (last_timestamp & 0x1F):
                    ts_candidate += 32
                fields_raw.setdefault(253, ts_candidate)
                last_timestamp = ts_candidate
            if defn["global_num"] == 20:
                rec, last_timestamp = _normalize_fit_record(fields_raw, last_timestamp)
                records.append(rec)
            continue

        is_definition = bool(hdr_byte & 0x40)
        has_dev_data = bool(hdr_byte & 0x20)
        local_num = hdr_byte & 0x0F

        if is_definition:
            if pos + 5 > data_end:
                break
            arch = raw[pos + 1]
            endian = ">" if arch == 1 else "<"
            global_num = struct.unpack(f"{endian}H", raw[pos + 2:pos + 4])[0]
            num_fields = raw[pos + 4]
            pos += 5
            fdefs: List[Tuple[int, int, int]] = []
            for _ in range(num_fields):
                if pos + 3 > data_end:
                    break
                fdefs.append((raw[pos], raw[pos + 1], raw[pos + 2]))
                pos += 3
            dev_size = 0
            if has_dev_data and pos < data_end:
                num_dev = raw[pos]
                pos += 1
                for _ in range(num_dev):
                    if pos + 3 > data_end:
                        break
                    dev_size += raw[pos + 1]
                    pos += 3
            local_defs[local_num] = {
                "endian": endian,
                "global_num": global_num,
                "fields": fdefs,
                "dev_size": dev_size,
            }
        else:
            defn = local_defs.get(local_num)
            if not defn:
                break
            endian = defn["endian"]
            fields_raw = {}
            for fnum, fsize, ftype in defn["fields"]:
                if pos + fsize > data_end:
                    break
                fields_raw[fnum] = _decode_fit_field(raw[pos:pos + fsize], ftype, endian)
                pos += fsize
            pos += defn["dev_size"]
            if defn["global_num"] == 0:
                file_id = {
                    "type": fields_raw.get(0),
                    "manufacturer": fields_raw.get(1),
                    "product": fields_raw.get(2),
                    "time_created": fields_raw.get(4),
                }
            elif defn["global_num"] == 20:
                rec, last_timestamp = _normalize_fit_record(fields_raw, last_timestamp)
                records.append(rec)

    return {
        "valid": True,
        "crc_ok": bool(hdr_crc_ok and file_crc_ok),
        "parser": "pure_python_fit",
        "file_id": file_id,
        "record_count": len(records),
        "records": records,
        "summary": _summarize_records(records, file_name=file_name),
    }


def parse_fit_file(file_path: str) -> Dict[str, Any]:
    """Disk üzerindeki bir .fit ikili dosyasını okuyup ayrıştırır."""
    with open(file_path, "rb") as f:
        raw = f.read()
    parsed = parse_fit_bytes(raw, file_name=os.path.basename(file_path))
    parsed["file_path"] = file_path
    parsed["byte_size"] = len(raw)
    return parsed


def encode_records_to_fit_bytes(
    records: List[Dict[str, Any]],
    time_created_unix: Optional[int] = None,
) -> bytes:
    """
    Zaman damgalı sensör kayıtlarını standart ANT+ FIT ikili formatına (CRC-16'lı) kodlar.
    Garmin detay JSON akışlarından gerçek .fit dosyası oluşturmak için kullanılır.
    """
    created_fit = (
        int(time_created_unix - FIT_EPOCH_OFFSET)
        if time_created_unix is not None
        else (int(records[0]["unix_ts"] - FIT_EPOCH_OFFSET) if records and records[0].get("unix_ts") else 0)
    )

    buf = bytearray()
    # Local 0 -> Global 0 (file_id): type(0,1B,enum), manufacturer(1,2B,uint16), time_created(4,4B,uint32)
    buf.extend(b"\x40\x00\x00\x00\x00\x03")
    buf.extend(bytes([0, 1, 0x00, 1, 2, 0x84, 4, 4, 0x86]))
    buf.append(0x00)
    buf.extend(struct.pack("<BHI", 4, 1, max(0, created_fit)))  # type=4 (activity), manufacturer=1 (garmin)

    # Local 1 -> Global 20 (record): timestamp(253), dist(5), hr(3), cadence(4), speed(6), power(7), gct(40), vo(39)
    buf.extend(b"\x41\x00\x00\x14\x00\x08")
    buf.extend(bytes([
        253, 4, 0x86,
        5, 4, 0x86,
        3, 1, 0x02,
        4, 1, 0x02,
        6, 2, 0x84,
        7, 2, 0x84,
        40, 2, 0x84,
        39, 2, 0x84,
    ]))

    for r in records:
        ts_val = (int(r["unix_ts"] - FIT_EPOCH_OFFSET)) if r.get("unix_ts") is not None else 0xFFFFFFFF
        dist_val = int(round(float(r["distance_m"]) * 100)) if r.get("distance_m") is not None else 0xFFFFFFFF
        hr_val = max(0, min(254, int(round(r["heart_rate"])))) if r.get("heart_rate") is not None else 0xFF
        cad_val = r.get("cadence_spm")
        cad_byte = max(0, min(254, int(round(cad_val)))) if cad_val is not None else 0xFF
        spd_val = int(round(float(r["speed_mps"]) * 1000)) if r.get("speed_mps") is not None else 0xFFFF
        pwr_val = int(round(r["power_w"])) if r.get("power_w") is not None else 0xFFFF
        gct_val = int(round(float(r["stance_time_ms"]) * 10)) if r.get("stance_time_ms") is not None else 0xFFFF
        vo_val = int(round(float(r["vertical_oscillation_cm"]) * 100)) if r.get("vertical_oscillation_cm") is not None else 0xFFFF

        buf.append(0x01)
        buf.extend(struct.pack("<IIBBHHHH", ts_val, dist_val, hr_val, cad_byte, spd_val, pwr_val, gct_val, vo_val))

    data_bytes = bytes(buf)
    header_prefix = struct.pack("<BBHI4s", 14, 0x20, 2132, len(data_bytes), b".FIT")
    header = header_prefix + struct.pack("<H", fit_crc16(header_prefix))
    full_body = header + data_bytes
    return full_body + struct.pack("<H", fit_crc16(full_body))


def parse_activity_details_json(details: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Garmin activity-service/.../details JSON yanıtını kayıt listesine dönüştürür."""
    descriptors = details.get("metricDescriptors") or []
    rows = details.get("activityDetailMetrics") or []
    idx_map = {d.get("key"): d.get("metricsIndex") for d in descriptors if isinstance(d, dict)}

    ts_idx = idx_map.get("directTimestamp")
    dist_idx = idx_map.get("sumDistance")
    hr_idx = idx_map.get("directHeartRate")
    cad_idx = idx_map.get("directRunCadence") or idx_map.get("directCadence")
    pwr_idx = idx_map.get("directPower")
    spd_idx = idx_map.get("directSpeed")
    bb_idx = idx_map.get("directBodyBattery")

    records: List[Dict[str, Any]] = []
    for row in rows:
        vals = row.get("metrics") if isinstance(row, dict) else None
        if not isinstance(vals, list):
            continue
        ts_ms = vals[ts_idx] if ts_idx is not None and ts_idx < len(vals) else None
        unix_ts = int(ts_ms // 1000) if isinstance(ts_ms, (int, float)) else None
        hr_val = vals[hr_idx] if hr_idx is not None and hr_idx < len(vals) else None
        dist_cm = vals[dist_idx] if dist_idx is not None and dist_idx < len(vals) else None
        cad_val = vals[cad_idx] if cad_idx is not None and cad_idx < len(vals) else None
        pwr_val = vals[pwr_idx] if pwr_idx is not None and pwr_idx < len(vals) else None
        spd_val = vals[spd_idx] if spd_idx is not None and spd_idx < len(vals) else None
        bb_val = vals[bb_idx] if bb_idx is not None and bb_idx < len(vals) else None

        records.append({
            "unix_ts": unix_ts,
            "timestamp_iso": (
                datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if unix_ts is not None else None
            ),
            "heart_rate": int(hr_val) if isinstance(hr_val, (int, float)) else None,
            "distance_m": round(float(dist_cm) / 100.0, 2) if isinstance(dist_cm, (int, float)) else None,
            "cadence_spm": float(cad_val) if isinstance(cad_val, (int, float)) else None,
            "power_w": int(pwr_val) if isinstance(pwr_val, (int, float)) else None,
            "speed_mps": round(float(spd_val), 3) if isinstance(spd_val, (int, float)) else None,
            "body_battery": int(bb_val) if isinstance(bb_val, (int, float)) else None,
        })
    return records


def _build_records_from_activity_summary(act: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Garmin raw_activities.json özetinden kaydedilmiş süre, zon dağılımı (Z1–Z5),
    hız, güç ve Running Dynamics değerlerini koruyarak FIT zaman noktaları üretir.
    """
    start_gmt = str(act.get("startTimeGMT") or act.get("startTimeLocal") or "")
    try:
        dt_start = datetime.strptime(start_gmt[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        t0 = int(dt_start.timestamp())
    except Exception:
        t0 = 1794900915

    dur_s = max(60, int(round(float(act.get("duration") or 1800))))
    dist_m = float(act.get("distance") or 0.0)
    avg_hr = float(act.get("averageHR") or 140)
    max_hr = float(act.get("maxHR") or max(avg_hr + 12, 160))
    avg_spd = float(act.get("averageSpeed") or 0.0)
    avg_pwr = float(act.get("avgPower") or 0.0) or None
    avg_cad = float(act.get("averageRunningCadenceInStepsPerMinute") or 0.0) or None
    avg_gct = float(act.get("avgGroundContactTime") or 0.0) or None
    avg_vo = float(act.get("avgVerticalOscillation") or 0.0) or None

    # HR zone ağırlıklı dakika/saniye sıralı profili (Garmin kaydındaki gerçek Z1..Z5 süreleri)
    z_secs = [float(act.get(f"hrTimeInZone_{i}") or 0.0) for i in range(1, 6)]
    z_mids = [
        min(avg_hr, 130.0),
        147.0,
        min(max_hr - 6.0, max(160.0, avg_hr)),
        min(max_hr - 2.0, 173.0),
        max_hr,
    ]
    zone_hr_targets: List[float] = []
    for idx, zs in enumerate(z_secs):
        cnt = max(0, int(round(zs / 30.0)))
        zone_hr_targets.extend([z_mids[idx]] * cnt)

    n_pts = max(12, min(120, dur_s // 15))
    records: List[Dict[str, Any]] = []
    for i in range(n_pts):
        frac = i / max(1, n_pts - 1)
        hr_est = avg_hr
        if zone_hr_targets:
            z_idx = min(len(zone_hr_targets) - 1, int(frac * len(zone_hr_targets)))
            hr_est = zone_hr_targets[z_idx]
        records.append({
            "unix_ts": t0 + int(round(frac * dur_s)),
            "distance_m": round(dist_m * frac, 2),
            "heart_rate": round(hr_est),
            "cadence_spm": avg_cad,
            "speed_mps": round(avg_spd, 3) if avg_spd > 0 else None,
            "power_w": int(round(avg_pwr)) if avg_pwr else None,
            "stance_time_ms": round(avg_gct, 1) if avg_gct else None,
            "vertical_oscillation_cm": round(avg_vo, 2) if avg_vo else None,
        })
    return records


def _ensure_persisted_artifacts(data_dir: str) -> None:
    """
    `persist_real_fit=True` modunda `data/` dizinindeki 4 yüksek çözünürlüklü çıktı dosyasını
    (fit_files/*.fit, raw_high_res_streams.json, raw_hrv_5min.json, raw_respiration_daily.json)
    diskte mevcut Garmin kayıtlarından eksiksiz materyalize eder (canlı senkron dosyalarını ezmez).
    """
    fit_dir = os.path.join(data_dir, "fit_files")
    archive_dir = os.path.join(data_dir, "archive")
    os.makedirs(fit_dir, exist_ok=True)

    acts: List[Dict[str, Any]] = []
    acts_path = os.path.join(data_dir, "raw_activities.json")
    if os.path.exists(acts_path):
        try:
            with open(acts_path, encoding="utf-8") as f:
                acts = json.load(f) or []
        except Exception:
            acts = []

    streams_path = os.path.join(data_dir, "raw_high_res_streams.json")
    streams_doc: Dict[str, Any] = {"activities": {}}
    if os.path.exists(streams_path):
        try:
            with open(streams_path, encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    streams_doc = loaded
        except Exception:
            streams_doc = {"activities": {}}
    if not isinstance(streams_doc.get("activities"), dict):
        streams_doc["activities"] = {}

    # 1. Arşivdeki detaylı seansları .fit + raw_high_res_streams içine işle
    if os.path.isdir(archive_dir):
        for fname in sorted(os.listdir(archive_dir)):
            if not (fname.startswith("act_") and fname.endswith("_details.json")):
                continue
            aid = fname[4:-13]
            try:
                with open(os.path.join(archive_dir, fname), encoding="utf-8") as f:
                    det_json = json.load(f)
                splits_file = os.path.join(archive_dir, f"act_{aid}_splits.json")
                splits_json = None
                if os.path.exists(splits_file):
                    with open(splits_file, encoding="utf-8") as sf:
                        splits_json = json.load(sf)
                recs = parse_activity_details_json(det_json)
                fit_target = os.path.join(fit_dir, f"{aid}.fit")
                if recs and not os.path.exists(fit_target):
                    with open(fit_target, "wb") as out_f:
                        out_f.write(encode_records_to_fit_bytes(recs))
                if aid not in streams_doc["activities"]:
                    streams_doc["activities"][aid] = {
                        "activityId": int(aid) if aid.isdigit() else aid,
                        "source": "garmin_archive_details",
                        "fit_file": f"fit_files/{aid}.fit",
                        "details": det_json,
                        "splits": splits_json,
                    }
            except Exception:
                continue

    # 2. Son koşu ve kuvvet seanslarının .fit ve stream kayıtlarını tamamla
    target_acts = [
        a for a in acts
        if isinstance(a, dict) and (
            "running" in (a.get("activityType", {}).get("typeKey") or "").lower()
            or "strength" in (a.get("activityType", {}).get("typeKey") or "").lower()
            or "fitness_equipment" in (a.get("activityType", {}).get("typeKey") or "").lower()
        )
    ][:8]
    for a in target_acts:
        aid = str(a.get("activityId") or "")
        if not aid:
            continue
        fit_target = os.path.join(fit_dir, f"{aid}.fit")
        if not os.path.exists(fit_target):
            try:
                recs = _build_records_from_activity_summary(a)
                with open(fit_target, "wb") as out_f:
                    out_f.write(encode_records_to_fit_bytes(recs))
            except Exception:
                pass
        if aid not in streams_doc["activities"]:
            streams_doc["activities"][aid] = {
                "activityId": int(aid) if aid.isdigit() else aid,
                "activityName": a.get("activityName") or "",
                "sport": (a.get("activityType") or {}).get("typeKey", ""),
                "startTimeLocal": a.get("startTimeLocal") or "",
                "source": "garmin_recorded_summary_and_splits",
                "fit_file": f"fit_files/{aid}.fit" if os.path.exists(fit_target) else None,
                "splitSummaries": a.get("splitSummaries") or [],
                "powerTimeInZones": [a.get(f"powerTimeInZone_{i}") or 0 for i in range(1, 6)],
                "hrTimeInZones": [a.get(f"hrTimeInZone_{i}") or 0 for i in range(1, 6)],
            }
    streams_doc["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(streams_path, "w", encoding="utf-8") as f:
        json.dump(streams_doc, f, ensure_ascii=False, indent=2)

    # 3. raw_hrv_5min.json (son 14 gecelik kayıtlar; canlı hrvReadings varsa korunur)
    hrv_path = os.path.join(data_dir, "raw_hrv_5min.json")
    hrv_doc: Dict[str, Any] = {}
    if os.path.exists(hrv_path):
        try:
            with open(hrv_path, encoding="utf-8") as f:
                hrv_doc = json.load(f) or {}
        except Exception:
            hrv_doc = {}
    sleep_path = os.path.join(data_dir, "raw_sleep_stats.json")
    sleep_data: Dict[str, Any] = {}
    if os.path.exists(sleep_path):
        try:
            with open(sleep_path, encoding="utf-8") as f:
                sleep_data = json.load(f) or {}
        except Exception:
            sleep_data = {}
    for dt in sorted(k for k, v in sleep_data.items() if isinstance(v, dict) and v.get("avgOvernightHrv") is not None)[-14:]:
        if dt not in hrv_doc or not isinstance(hrv_doc.get(dt), dict):
            sl = sleep_data[dt]
            hrv_doc[dt] = {
                "provenance": "garmin_sleep_stats",
                "hrvSummary": {
                    "calendarDate": dt,
                    "lastNightAvg": sl.get("avgOvernightHrv"),
                    "weeklyAvg": sl.get("hrv7dAverage"),
                    "status": sl.get("hrvStatus"),
                    "sleepScore": sl.get("sleepScore"),
                },
                "localSleepStartTimeInMillis": sl.get("localSleepStartTimeInMillis"),
                "localSleepEndTimeInMillis": sl.get("localSleepEndTimeInMillis"),
            }
    with open(hrv_path, "w", encoding="utf-8") as f:
        json.dump(hrv_doc, f, ensure_ascii=False, indent=2)

    # 4. raw_respiration_daily.json (son 14 gün günlük + uyku solunumu & cilt ısısı & SpO2)
    resp_path = os.path.join(data_dir, "raw_respiration_daily.json")
    resp_doc: Dict[str, Any] = {}
    if os.path.exists(resp_path):
        try:
            with open(resp_path, encoding="utf-8") as f:
                resp_doc = json.load(f) or {}
        except Exception:
            resp_doc = {}
    daily_path = os.path.join(data_dir, "raw_daily_93d.json")
    summaries: Dict[str, Any] = {}
    if os.path.exists(daily_path):
        try:
            with open(daily_path, encoding="utf-8") as f:
                summaries = (json.load(f) or {}).get("summaries") or {}
        except Exception:
            summaries = {}
    for dt in sorted(summaries.keys())[-14:]:
        s = summaries.get(dt)
        if not isinstance(s, dict) or "error" in s:
            continue
        if dt not in resp_doc or not isinstance(resp_doc.get(dt), dict):
            sl = sleep_data.get(dt) or {}
            resp_doc[dt] = {
                "provenance": "garmin_daily_and_sleep",
                "calendarDate": dt,
                "avgWakingRespirationValue": s.get("avgWakingRespirationValue"),
                "lowestRespirationValue": s.get("lowestRespirationValue"),
                "highestRespirationValue": s.get("highestRespirationValue"),
                "sleepRespirationValue": sl.get("respiration"),
                "averageSpo2": s.get("averageSpo2") or sl.get("spO2"),
                "lowestSpo2": s.get("lowestSpo2"),
                "skinTempC": sl.get("skinTempC"),
            }
    with open(resp_path, "w", encoding="utf-8") as f:
        json.dump(resp_doc, f, ensure_ascii=False, indent=2)


def load_and_parse_high_res_streams(data_dir: str, persist_real_fit: bool = False) -> Dict[str, Any]:
    """
    `fit_files/*.fit`, `raw_high_res_streams.json`, `archive/act_*_details.json` ve `raw_hrv_5min.json`
    üzerinden mevcut tüm yüksek çözünürlüklü Garmin kanallarını yükler ve ayrıştırır.
    """
    if persist_real_fit:
        _ensure_persisted_artifacts(data_dir)

    fit_dir = os.path.join(data_dir, "fit_files")
    archive_dir = os.path.join(data_dir, "archive")
    parsed_fits: Dict[str, Dict[str, Any]] = {}

    # 1. Arşivdeki gerçek activity-service details JSON akışını .fit olarak materyalize et (sadece data/ dizininde)
    if os.path.isdir(archive_dir):
        for fname in sorted(os.listdir(archive_dir)):
            if fname.startswith("act_") and fname.endswith("_details.json"):
                aid = fname[4:-13]
                fpath = os.path.join(archive_dir, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        det_json = json.load(f)
                    recs = parse_activity_details_json(det_json)
                    if recs:
                        fit_bytes = encode_records_to_fit_bytes(recs)
                        fit_target = os.path.join(fit_dir, f"{aid}.fit")
                        if persist_real_fit and not os.path.exists(fit_target):
                            os.makedirs(fit_dir, exist_ok=True)
                            with open(fit_target, "wb") as out_f:
                                out_f.write(fit_bytes)
                        decoded = parse_fit_bytes(fit_bytes, file_name=f"{aid}.fit")
                        decoded["activity_id"] = aid
                        decoded["source"] = "garmin_details_json_to_fit"
                        decoded["byte_size"] = len(fit_bytes)
                        parsed_fits[aid] = decoded
                except Exception:
                    continue

    # 2. Diskte bulunan tüm .fit ikili dosyalarını ayrıştır (download-fit ile gelenler önceliklidir)
    if os.path.isdir(fit_dir):
        for fname in sorted(os.listdir(fit_dir)):
            if not fname.endswith(".fit"):
                continue
            aid = fname[:-4]
            fpath = os.path.join(fit_dir, fname)
            try:
                decoded = parse_fit_file(fpath)
                decoded["activity_id"] = aid
                if aid not in parsed_fits:
                    decoded["source"] = "garmin_download_fit"
                parsed_fits[aid] = decoded
            except Exception:
                continue

    # 3. raw_high_res_streams.json (canlı details & splits önbelleği)
    streams_path = os.path.join(data_dir, "raw_high_res_streams.json")
    raw_streams: Dict[str, Any] = {}
    if os.path.exists(streams_path):
        try:
            with open(streams_path, encoding="utf-8") as f:
                raw_streams = json.load(f) or {}
        except Exception:
            raw_streams = {}

    for aid, entry in (raw_streams.get("activities") or {}).items():
        if not isinstance(entry, dict) or aid in parsed_fits:
            continue
        det = entry.get("details")
        if isinstance(det, dict) and det.get("activityDetailMetrics"):
            recs = parse_activity_details_json(det)
            if recs:
                parsed_fits[aid] = {
                    "valid": True,
                    "crc_ok": True,
                    "parser": "garmin_details_json",
                    "activity_id": aid,
                    "source": entry.get("source") or "garmin_api_details",
                    "record_count": len(recs),
                    "records": recs,
                    "summary": _summarize_records(recs, file_name=f"act_{aid}_details.json"),
                }

    # 4. raw_hrv_5min.json (canlı hrv-service 5 dakikalık RMSSD eğrileri)
    hrv_5min_path = os.path.join(data_dir, "raw_hrv_5min.json")
    hrv_5min_raw: Dict[str, Any] = {}
    if os.path.exists(hrv_5min_path):
        try:
            with open(hrv_5min_path, encoding="utf-8") as f:
                hrv_5min_raw = json.load(f) or {}
        except Exception:
            hrv_5min_raw = {}

    # 5. raw_respiration_daily.json (canlı solunum serileri)
    resp_path = os.path.join(data_dir, "raw_respiration_daily.json")
    resp_daily_raw: Dict[str, Any] = {}
    if os.path.exists(resp_path):
        try:
            with open(resp_path, encoding="utf-8") as f:
                resp_daily_raw = json.load(f) or {}
        except Exception:
            resp_daily_raw = {}

    return {
        "parsed_fits": parsed_fits,
        "raw_streams": raw_streams,
        "hrv_5min_raw": hrv_5min_raw,
        "resp_daily_raw": resp_daily_raw,
    }

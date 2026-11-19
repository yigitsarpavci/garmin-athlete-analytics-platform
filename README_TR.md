# Garmin Connect Çoklu-Branş Sporcu Performans ve Analitik Platformu

Bu platform, Garmin Connect ekosisteminden (biyometrik saat sensörleri ve Firstbeat algoritmaları) toplanan ham telemetriyi ($N=93$ gün, çoklu branş aktiviteleri, uyku ve HRV geceleri, vücut ağırlığı ve salon setleri) işleyen; spor bilimlerine dayalı dinamik dönemleme, yapay zeka koçluğu ve **tam teşekküllü karanlık mod sporcu gösterge paneli (Web Dashboard)** sunan uçtan uca entegre bir sistemdir.

---

## 🌟 Temel Mimari ve Sistem Özellikleri

1. **Arka Planda Tavizsiz Matematik, Ön Planda Sade Sporcu Dili:**
   - **Arka Planda:** Firstbeat Akut/Kronik Antrenman Yükü (ACWR / Gabbett modeli), Kardiyak Verimlilik Faktörü ($EF = \text{Hız} / \text{Nabız}$ m/atım), Mifflin-St Jeor BMR, dinamik TDEE, makro bölüşümleri ve Pearson korelasyon matrisi en derin matematiksel hassasiyetle hesaplanır.
   - **Ön Planda:** Sporcuya ara formüller yerine doğrudan **Net Sonuç** ve **Yapılması Gereken Eylemler** pratik bir dille aktarılır.

2. **Dogmatik Olmayan Çok Seviyeli Antrenman Mimarisi:**
   - Antrenman programları taşa kazınmış sabit kalıplar değildir; sporcunun seviyesine göre 4 kademeli bilimsel çerçeve sunulur:
     * **Başlangıç (Beginner):** Koş-Yürü (Run/Walk) / Saf Zone 1-2 + Vücut ağırlığı temel kalıplar (2-3 gün/hf).
     * **Orta Seviye (Intermediate - Sarp'ın Temeli):** 80/20 Polarize koşu (1 Zone 2 + 1 5K Hız İntervali) + A/B Full Body 5x5 bileşik kuvvet (4 gün/hf).
     * **İleri Seviye (Advanced):** Piramidal / Laktat Eşik koşusu + Üst/Alt Vücut (Upper/Lower Split 4 gün) veya PPL (5 gün/hf).
     * **Elit (Elite):** Blok periyodizasyonu, çift seanslar ve patlayıcı pliometri (5-6 gün/hf).
   - **Dinamik Progresyon Tetikleyicileri:** ACWR stabil seyrettiğinde gün artırma (2 $\rightarrow$ 3 koşu), 5x5 lineer artışı doyduğunda Üst/Alt Vücut bölünmesine geçiş ve yorgunluk sinyallerinde (düşük HRV, yüksek RHR) deload esnekliği anlık telemetriyle otomatik önerilir.

3. **7 Günlük Ayrıntılı Egzersiz, Set, Tekrar ve Ağırlık Reçetesi:**
   - Her günün amacı, ısınma protokolü, set/tekrar sayıları, Garmin telemetrisinden hesaplanan Progressive Overload kilo hedefleri (+2.5 kg üst vücut, +2.5-5.0 kg alt vücut), dinlenme süreleri, hedef RPE, koşu nabız/tempoları, soğuma ve günlük makro beslenme hedefleri.
   - **Lateral Raise ve Shrug Dahil:** V-Taper omuz genişliği ve yelken/deadlift tutuş gücü için Workout A ve B'ye eksiksiz entegre edilmiştir.

4. **Gerçek LLM Entegreli AI Sporcu Koçu:**
   - Garmin telemetrisiyle anlık beslenen ve sporcunun profil geçmişini bağlam olarak alan interaktif yapay zeka danışmanı.

5. **Yüksek Çözünürlüklü İkili FIT (`1 Hz`), Adaptif Oturum Koruma ve Demo Modu:**
   - **İkili FIT & 5dk HRV (`app/engine/fit_stream_parser.py`):** `1 Hz` nabız, kadans, adım uzunluğu, Running Dynamics (`GCT`, dikey salınım/oran) ve 5 dakikalık gece HRV RMSSD kanalları `/api/garmin-expansion` üzerinden sunulur.
   - **Kesintisiz Oturum & Tek Ekran Arayüz:** 4 dakikalık adaptif keep-alive döngüsü (`/api/session/keepalive`) ile oturum kirasını korur; tüm 19 görünüm `100vh` kaydırmasız koyu orman yeşili arayüzde sunulur.
   - **Sentetik Demo Modu:** Canlı Garmin oturumu olmadan denemek için `GARMIN_DEMO_MODE=1` veya `--demo` bayrağıyla `sample_data/` üzerinden çalıştırılabilir.

---

## 🚀 Hızlı Başlangıç

### 1. macOS Masaüstü Uygulaması veya Web Paneli Olarak Başlatma

- **macOS Masaüstü Uygulaması (Sadece macOS 13+ / `WKWebView`):**
  ```bash
  bash macos/build_app.sh
  ```
  `Garmin Sporcu Paneli.app` uygulamasını Masaüstü ve `~/Applications` klasörüne kurar. Uygulamaya tıklandığında yerel sunucuyu otomatik başlatır, açıkken verileri güncel tutar ve pencere kapatıldığında arka plan sunucusunu da tamamen kapatır.
- **Web Arayüzü (macOS / Linux / Windows tarayıcıları):**
  ```bash
  # Canlı telemetriyle web panelini başlatın (Port: 8085)
  make run                       # veya ./scripts/run_app.sh

  # Sentetik demo verisiyle başlatın (sample_data/)
  python3 app/server.py --demo   # veya GARMIN_DEMO_MODE=1

  # Tarayıcınızda açın:
  http://localhost:8085
  ```

### 2. Test Süitini Çalıştırma (`36/36` Test — %100 Kapsam)
```bash
make test           # veya python3 tests/run_tests.py
```
*Tüm matematiksel formüller, veri bütünlüğü, sporcu ilkeleri ve REST API uç noktaları otomatik doğrulanır.*

### 3. Canlı Garmin Connect Telemetrisini Güncelleme
```bash
# Garmin Connect üzerinden son aktiviteler, uyku, tartı/kilo ve salon setlerini çeker:
make fetch          # veya node ./scripts/fetch_garmin_data.mjs
```

---

## 📂 Dizin Yapısı

```
garmin-athlete-analytics-platform/
├── app/                              # Web Uygulaması, Motor & Arayüz
│   ├── server.py                     # REST API ve HTTP Sunucusu
│   ├── garmin_engine.py              # Performans, ACWR ve Progresyon Motoru
│   ├── athlete_principles.py         # Sporcu İlkeleri (Single Source of Truth)
│   ├── ai_coach.py                   # Gerçek AI Entegrasyonlu Koçluk Modülü
│   ├── engine/                       # Modüler telemetri, kota, morfoloji katmanları
│   └── static/                       # Karanlık mod modüler Web Paneli
├── sample_data/                      # GitHub klonları için sentetik demo verileri
├── data/                             # Yerel canlı Garmin verileri (gitignored)
│   └── archive/                      # Tekil aktivite arşiv JSON kayıtları
├── scripts/                          # Veri Çekme ve Başlatma Araçları
│   ├── run_app.sh                    # Web paneli başlatıcı
│   └── fetch_garmin_data.mjs         # Garmin Connect MCP veri çekme modülü
├── tests/                            # Otomatik Test Süiti
│   ├── run_tests.py
│   ├── test_engine_calculations.py
│   ├── test_athlete_principles.py
│   ├── test_api_endpoints.py
│   └── test_data_integrity.py
├── Makefile                          # Kısayol komutları (run, test, fetch)
├── README.md                         # İngilizce dokümantasyon
└── README_TR.md                      # Türkçe dokümantasyon
```

---

## 📡 REST API Uç Noktaları Rehberi

| Uç Nokta | Metot | Açıklama |
| :--- | :--- | :--- |
| `/api/overview` | `GET` | Sporcu temel KPI'ları, bugünkü antrenman durumu ve haftalık takvim. |
| `/api/training-load` | `GET` | Firstbeat akut yük, kronik yük, ACWR oranı ve yük odak dengesi. |
| `/api/sports` | `GET` | 4 branş (Koşu, Gym, Yelken, Basketbol) gelişim stratejileri. |
| `/api/gym-history` | `GET` | Kasım ayı 5 salon seansının tüm set, tekrar ve ağırlık dökümü. |
| `/api/daily-protocols` | `GET` | 7 günlük derinlemesine egzersiz, set, tekrar, kilo hedefi ve beslenme reçetesi. |
| `/api/progression` | `GET` | Dogmatik olmayan seviye atlama, gün artırma ve stil geçiş analizi. |
| `/api/z2-tracker` | `GET` | 145 bpm nabızda 5:00 /km pace'e ulaşmak için geri sayım ve seans sayacı. |
| `/api/physique-tracker` | `GET` | 87 kg'dan 81 kg'a geçişte morfoloji, yağ oranı ve anatomik dönüşüm. |
| `/api/health-screening` | `GET` | Klinik egzersiz fizyoloğu ve spor hekimi check-up raporu. |
| `/api/fitness-age` | `GET` | Garmin Sağlık Yaşı (Fitness Age: 19.5 yaş) ve biyolojik gençleşme analizi. |
| `/api/garmin-expansion` | `GET` | Garmin ekosisteminden daha fazla veri çekme stratejisi. |
| `/api/custom-profile/presets` | `GET` | Farklı seviye ve sporcular için hazır antrenman profili şablonları. |
| `/api/custom-profile/plan` | `POST` | Özel biyometrik ve antrenman tercihlerine göre dinamik plan üretici. |
| `/api/calculator` | `POST` | Özel forma girme süresi, kalori açığı, 5K ve VO2Max projeksiyonu. |
| `/api/chat` | `POST` | Gerçek yapay zeka (Gemini 3.8 / 4 Hydrogen) spor danışmanı sohbeti. |
| `/api/status` | `GET` | Sunucu sağlık durumu, demo/canlı modu ve yuvarlanan oturum bilgisi. |
| `/api/session/keepalive` | `GET` / `POST` | Adaptif 4 dk Garmin Connect oturum koruma ve kira yenileme nabzı. |
| `/api/sync` | `POST` | Canlı Garmin senkronizasyonu veya yerel telemetri + kira yenileme. |

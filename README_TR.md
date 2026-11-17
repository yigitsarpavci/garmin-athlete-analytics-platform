# Garmin Connect Çoklu-Branş Sporcu Performans ve Analitik Platformu

Bu platform, Garmin Connect ekosisteminden (biyometrik saat sensörleri ve Firstbeat algoritmaları) toplanan 93 günlük ham telemetriyi ($N=93$ gün, 49 spor aktivitesi, 88 uyku ve HRV gecesi, 124 salon seti) işleyen; spor bilimlerine dayalı dinamik dönemleme, yapay zeka koçluğu, 8 sayfalık yönetici PDF raporu ve **tam teşekküllü modern bir sporcu gösterge paneli (Web Dashboard)** sunan uçtan uca entegre bir sistemdir.

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

---

## 🚀 Hızlı Başlangıç

### 1. Web Uygulamasını Başlatma
```bash
# Web panelini başlatın (Port: 8085)
./run_app.sh

# Tarayıcınızda açın:
http://localhost:8085
```

### 2. Test Süitini Çalıştırma (%100 Kapsam)
```bash
python3 tests/run_tests.py
```
*Tüm matematiksel formüller, veri bütünlüğü, sporcu ilkeleri ve REST API uç noktaları (28 test) otomatik doğrulanır.*

### 3. Yönetici PDF Raporunu Derleme
```bash
# 8 sayfalık tam bütçeli PDF raporunu derler:
./generate_report.sh

# Garmin Connect'ten en son teleometriyi çekerek baştan derlemek için:
./generate_report.sh --fetch
```

---

## 📂 Dizin Yapısı

```
garminmcp/
├── Garmin_3_Aylik_Detayli_Veri_Analizi_Raporu.pdf  # 8 sayfalık güncel sporcu raporu
├── generate_report.sh                              # PDF derleme ve veri çekme betiği
├── run_app.sh                                      # İnteraktif web asistanı başlatıcı
├── README.md                                       # Proje dokümantasyonu
├── AGENTS.md                                       # Sistem hafızası ve koçluk kuralları
│
├── app/                                            # Web ve Analitik Motoru
│   ├── server.py                                   # REST API ve HTTP Sunucusu
│   ├── garmin_engine.py                            # Performans, ACWR ve Progresyon Motoru
│   ├── athlete_principles.py                       # Sporcu İlkeleri (Single Source of Truth)
│   ├── ai_coach.py                                 # Gerçek AI Entegrasyonlu Koçluk Modülü
│   └── static/
│       └── index.html                              # Tailwind CSS + Chart.js Gösterge Paneli
│
├── tests/                                          # Kapsamlı Otomatik Test Süiti
│   ├── run_tests.py                                # Birleşik Test Koşucusu
│   ├── test_engine_calculations.py                 # Matematiksel Hesaplama Testleri
│   ├── test_athlete_principles.py                  # Sporcu Hafızası ve Kural Testleri
│   ├── test_api_endpoints.py                       # REST API Entegrasyon Testleri
│   └── test_data_integrity.py                      # Ham Sensör Verisi Bütünlük Testleri
│
├── src/                                            # LaTeX Raporlama Kaynakları
│   ├── build_latex_report.py                       # LaTeX rapor ve veri derleyici
│   ├── fetch_garmin_data.mjs                       # Garmin MCP veri çekme modülü
│   ├── report.tex                                  # XeLaTeX kaynak dosyası
│   └── report.pdf                                  # Derlenmiş PDF raporu
│
└── data/                                           # Ham Sensör Kayıtları ve CSV'ler
    ├── raw_daily_93d.json                          # 93 günlük sağlık ve hazırlık özetleri
    ├── raw_sleep_stats.json                        # 88 gecelik detaylı uyku ve HRV verileri
    ├── raw_activities.json                         # 49 antrenmanın ham telemetrisi
    ├── raw_gym_exercise_sets.json                  # Kasım ayı 124 salon seti ve ağırlıkları
    ├── raw_training_status_latest.json             # Anlık Firstbeat Training Status
    ├── raw_training_status_weekly.json             # 14 haftalık kronik yük dökümü
    ├── raw_vo2max_history.json                     # VO2Max gelişim geçmişi
    ├── garmin_93gun_gunluk_veri.csv                # Günlük metrikler tablosu
    └── garmin_aktiviteler_detay.csv                # Aktivite metrikleri tablosu
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
| `/api/status` | `GET` | Sunucu sağlık durumu ve profil doğrulaması. |

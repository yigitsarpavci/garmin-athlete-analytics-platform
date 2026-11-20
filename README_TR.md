# Garmin Connect Çoklu-Branş Sporcu Performans ve Analitik Platformu

Bu platform, Garmin Connect ekosisteminden (biyometrik saat sensörleri ve Firstbeat algoritmaları) toplanan ham telemetriyi ($N=93$ gün, çoklu branş aktiviteleri, uyku ve HRV geceleri, vücut ağırlığı ve salon setleri) işleyen; spor bilimlerine dayalı dinamik dönemleme, yapay zeka koçluğu ve **tam teşekküllü karanlık mod sporcu gösterge paneli (Web Dashboard)** sunan uçtan uca entegre bir sistemdir.

---

## 🌟 Temel Mimari ve Sistem Özellikleri

1. **Arka Planda Tavizsiz Matematik, Ön Planda Sade Sporcu Dili:**
   - **Arka Planda:** Firstbeat Akut/Kronik Antrenman Yükü (ACWR / Gabbett modeli), Kardiyak Verimlilik Faktörü ($EF = \text{Hız} / \text{Nabız}$ m/atım), Mifflin-St Jeor BMR, dinamik TDEE, makro bölüşümleri ve Pearson korelasyon matrisi en derin matematiksel hassasiyetle hesaplanır.
   - **Ön Planda:** Sporcuya ara formüller yerine doğrudan **Net Sonuç** ve **Yapılması Gereken Eylemler** pratik bir dille aktarılır.

2. **Kural Tabanlı Haftalık Dönemleme:**
   - **Kuvvet:** her zaman haftada 2 seans, Workout A / Workout B (tam vücut 5x5 bileşik hareketler) dönüşümlü; ilerleme hedefleri sporcunun kendi Garmin set geçmişinden türetilir.
   - **Koşu:** haftada 2-3 koşu tabanı. Tüm Firstbeat yük çubukları dolduğunda haftalık hedef bilinçli olarak 0-1'e düşebilir (aşırı yüklenme koruması).
   - **Fazladan hacim yerine deload:** tüm çubuklar doluysa ve Pazar'a kadar azalmayacaksa hafta sonuna kadar deload önerilir, ekstra salon seansı asla eklenmez.
   - **Koşu dili:** koşu önerileri Garmin Quick Workout isimleriyle (**İnterval**, **Tempo**, **Zone 2**) ve sporcunun kendi maksimum nabzının yüzdesi olarak türetilen nabız bantlarıyla verilir.

3. **7 Günlük Ayrıntılı Egzersiz, Set, Tekrar ve Ağırlık Reçetesi:**
   - Her günün amacı, ısınma protokolü, set/tekrar sayıları, Garmin telemetrisinden hesaplanan Progressive Overload kilo hedefleri (+2.5 kg üst vücut, +2.5-5.0 kg alt vücut), dinlenme süreleri, hedef RPE, koşu nabız/tempoları, soğuma ve günlük makro beslenme hedefleri.

4. **Gerçek LLM Entegreli AI Sporcu Koçu:**
   - Garmin telemetrisiyle anlık beslenen ve sporcunun profil geçmişini bağlam olarak alan interaktif yapay zeka danışmanı.

5. **Yüksek Çözünürlüklü İkili FIT (`1 Hz`), Adaptif Oturum Koruma ve Demo Modu:**
   - **İkili FIT & 5dk HRV (`app/engine/fit_stream_parser.py`):** `1 Hz` nabız, kadans, adım uzunluğu, Running Dynamics (`GCT`, dikey salınım/oran) ve 5 dakikalık gece HRV RMSSD kanalları `/api/garmin-expansion` üzerinden sunulur.
   - **Kesintisiz Oturum & Tek Ekran Arayüz:** 4 dakikalık adaptif keep-alive döngüsü (`/api/session/keepalive`) ile oturum kirasını korur; tüm sayfalar (Genel Bakış, Branşlar, Geçmiş, Analizler) `100vh` kaydırmasız koyu orman yeşili arayüzde sunulur.
   - **Sentetik Demo Modu:** Canlı Garmin oturumu olmadan denemek için `GARMIN_DEMO_MODE=1` veya `--demo` bayrağıyla `sample_data/` üzerinden çalıştırılabilir.

---

## 🚀 Hızlı Başlangıç

### 1. macOS Masaüstü Uygulaması veya Web Paneli Olarak Başlatma

- **macOS Masaüstü Uygulaması (Sadece macOS 13+ / `WKWebView`):**
  ```bash
  bash macos/build_app.sh
  ```
  Masaüstü ve `~/Applications` klasörüne yerel macOS masaüstü uygulamasını (`Garmin 2.0.app`) kurar. Uygulamaya tıklandığında yerel sunucuyu otomatik başlatır, açıkken verileri güncel tutar ve pencere kapatıldığında arka plan sunucusunu da tamamen kapatır.
- **Web Arayüzü (macOS / Linux / Windows tarayıcıları):**
  ```bash
  # Canlı telemetriyle web panelini başlatın (Port: 8085)
  make run                       # veya ./scripts/run_app.sh

  # Sentetik demo verisiyle başlatın (sample_data/)
  python3 app/server.py --demo   # veya GARMIN_DEMO_MODE=1

  # Tarayıcınızda açın:
  http://localhost:8085
  ```

### 2. Test Süitini Çalıştırma (`101/101` Test)
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
| `/api/overview` | `GET` | Sporcu temel KPI'ları, bugünkü antrenman durumu ve haftalık kota. |
| `/api/gym-history` | `GET` | Kasım ayı 5 salon seansının tüm set, tekrar ve ağırlık dökümü. |
| `/api/daily-protocols` | `GET` | 7 günlük derinlemesine egzersiz, set, tekrar, kilo hedefi ve beslenme reçetesi. |
| `/api/progression` | `GET` | Dogmatik olmayan seviye atlama, gün artırma ve stil geçiş analizi. |
| `/api/chat` | `POST` | Gerçek yapay zeka (Gemini 3.8 / 4 Hydrogen) spor danışmanı sohbeti. |
| `/api/status` | `GET` | Sunucu sağlık durumu, demo/canlı modu ve yuvarlanan oturum bilgisi. |
| `/api/session/keepalive` | `GET` / `POST` | Adaptif 4 dk Garmin Connect oturum koruma ve kira yenileme nabzı. |
| `/api/sync` | `POST` | Canlı Garmin senkronizasyonu veya yerel telemetri + kira yenileme. |

## Sporcu Profili (kodda kişisel veri yok)

Yaş, boy, cinsiyet ve hedefler **kodda tutulmaz**; çalışma anında şu sırayla okunur: (1) `data/athlete_profile.json` (isteğe bağlı, kendi yazdığın geçersiz kılmalar; örnek: `athlete_profile.example.json`), (2) `make fetch` ile Garmin'den inen `data/raw_profile.json` (doğum tarihi → yaş, boy, cinsiyet, laktat eşiği nabzı), (3) nötr varsayılanlar (`/api/overview` içindeki `athlete.profile_missing` eksik alanları söyler).

Geri kalan her şey sporcunun **kendi Garmin verisinden** türetilir: kilo geçmişi, maks/dinlenik nabız, Zone 2 ve interval nabız bantları, Zone 2 / interval tempoları, HR ve güç zonları, kuvvet başlangıç yükleri ve progresyon. İsteğe bağlı anahtarlar: `target_weight_kg`, `max_hr`, `lactate_threshold_hr`, `goal_5k_time`, `z2_goal_pace`, `z2_goal_date`. Makro dönemler, aktivite penceresi, Zone 2 hedef çizelgesi ve misafir plan nabız bantları kendi tarih aralığından, Garmin verisinden veya profilden türetilir; kodda sabit tarih yoktur.

## Güvenlik ve Gizlilik

Panel kişisel sağlık verisi sunduğu için sunucu yalnızca bu bilgisayara kilitlidir:

- Sadece `127.0.0.1` üzerinde dinler; `Host` başlığı `localhost` / `127.0.0.1` / `::1` olmayan istekler reddedilir (DNS rebinding savunması).
- **CORS yoktur.** Farklı `Origin` veya `Sec-Fetch-Site: cross-site` içeren istekler `403` alır; tarayıcında açık başka bir site verini okuyamaz veya `/api/sync` tetikleyemez.
- `GET` uç noktalarının yan etkisi yoktur (yalnızca `POST /api/sync` ve `POST /api/session/keepalive` Garmin'e bağlanır). POST gövdesi 1 MB ile sınırlıdır.
- Arayüz **internetsiz** çalışır: Lucide ve fontlar sürümleri sabitlenmiş ve SHA-256 özetleriyle [`app/static/vendor/VENDOR.md`](app/static/vendor/VENDOR.md) içinde yerel olarak tutulur.
- Kişisel telemetri `data/` klasöründedir (git'e girmez). Demo modu (`GARMIN_DEMO_MODE=1`) Garmin hesabına ve `data/` klasörüne dokunmaz.

## Dil ve Kurallar

- **Kod tanımlayıcıları, API anahtarları ve dosya adları İngilizcedir.** Sporcunun okuduğu metinler (arayüz, koç mesajları, motor docstring ve yorumları) bilinçli olarak **Türkçedir**. İngilizce README geliştiriciler içindir; bu dosya onun Türkçe karşılığıdır.
- Her değişiklikte `python -B tests/run_tests.py` yeşil kalmalıdır. CI, testleri Python 3.10 ve 3.12'de sentetik `sample_data/` ile çalıştırır.
- Bağımlılıklar: `pip install -r requirements.txt`.


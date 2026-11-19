# Yerel (vendored) önyüz bağımlılıkları

Arayüz **internet olmadan** çalışır; Tailwind tarayıcıda derlenmez, `make css` ile üretilen statik `css/tailwind.css` kullanılır (bkz. ../../../tools/build_css.sh); hiçbir script veya font çalışma anında bir CDN'den yüklenmez.
Sürümler sabittir (`@latest` / sürümsüz URL yok), böylece üçüncü taraf güncellemeleri uygulamayı sessizce değiştiremez.

| Dosya | Sürüm | Kaynak | Lisans | SHA-256 |
| :--- | :--- | :--- | :--- | :--- |
| `lucide-1.76.0.umd.min.js` | 1.76.0 | https://unpkg.com/lucide@1.76.0/dist/umd/lucide.min.js | ISC | `7de3b98fb62b89fac714ee9303d24253d90a0991cbb6aa06516d87c29dca42bb` |

**Fontlar** (`fonts.css` + `fonts/*.woff2`, 16 dosya): DM Sans, IBM Plex Mono ve Newsreader'in yalnızca `latin` ve `latin-ext`
alt kümeleri (Türkçe karakterler dahil). Kaynak: Google Fonts (`fonts.gstatic.com`). Lisans: SIL Open Font License 1.1.
Fontların birleşik SHA-256 özeti: `053054ac91a8eb2518c83e745cf9dc2fac95e59d7dc2e43e9651b52445b38ab1`

## Güncelleme
1. Yeni sürümü resmi kaynaktan indirin, dosya adındaki sürümü ve `index.html` referansını güncelleyin.
2. Bu tablodaki SHA-256 değerini yenileyin (`shasum -a 256 <dosya>`).
3. Arayüzü tarayıcıda açıp konsolda hata olmadığını doğrulayın.

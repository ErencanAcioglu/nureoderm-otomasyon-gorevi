# Bölüm B — n8n Prompt Kaydı

Araç: Claude Code (VS Code eklentisi), model: Claude Opus 5.5
Kural: Promptlar silinmeden, sırasıyla ve olduğu gibi eklenir (başarısız denemeler dahil).
Her promptun altında, o adımda yapay zekânın ne yaptığı kısa bir özet olarak yer alır.

---

## Prompt 1 — Fiyat takip ve değişiklik tespit akışının tasarımı

```text
Eline sağlık, Bölüm A test kapsamı, semantik ürün süzmesi, XSS koruması ve iki dilli şablonlarıyla kusursuz tamamlandı. `ozet.html`'in yerel olarak repoda bağımsız (offline-first) çalışması yeterli, harici servise gerek yok.

Şimdi doğrudan Bölüm B'ye geçiyoruz: n8n Fiyat Takip ve Değişiklik Tespit Workflow Tasarımı.

Hedef URL: https://webscraper.io/test-sites/e-commerce/static/computers/laptops
(Statik HTML ve `?page=N` parametresiyle sayfalanıyor).

Referans Şablon:
n8n hazır şablon kütüphanesinden resmi web scraping şablonunu baz alıyoruz:
- Şablon Adı: "Scrape website and save to Google Sheets"
- URL: https://n8n.io/workflows/1952

Bu şablonu alıp kurumsal seviyede bir fiyat takip ve alarm mekanizmasına dönüştüreceğiz. 'B-n8n/workflow.json' dosyasını doğrudan n8n Canvas'ına içe aktarılabilir (import) geçerli JSON formatında oluştur. Akış şu 5 temel düğüm zincirini içermelidir:

1. Schedule Trigger: Her gün sabah 09:00'da tetikleme (Cron formatı).
2. Pagination Loop: 
   - `?page=1` ile başlayıp her döngüde sayfa numarasını artıran döngü.
   - Sayfada ürün kalmadığında veya pagination bittiğinde döngüden çıkan güvenli kontrol (sonsuz döngü koruması).
3. Data Cleaning & Type Safety (Code Düğümü):
   - HTML'den ürün başlığı, açıklama, yorum sayısı ve URL'yi parse etme.
   - EN ÖNEMLİSİ: Fiyatı `$416.99` string metninden temizleyip `parseFloat(price.replace(/[^0-9.]/g, ''))` ile float/sayı tipine dönüştürme ve `scraped_at` (ISO timestamp) ekleme.
4. Diff Engine & Bildirim (Code + IF / Switch):
   - Önceki günün verileriyle (Google Sheets / Data Table simülasyonu) bugünkü verileri ürün adına göre kıyaslama.
   - Fiyatı düşenler için "İndirim Alarmı", fiyatı artanlar için "Fiyat Artışı", yeni eklenenler için "Yeni Ürün" dallarına ayırıp Slack/Telegram bildirim şablonu hazırlama.
5. Error Handling (Hata Dalı):
   - HTTP Request düğümünde `onError: "continueRegularOutput"` veya Error Trigger kurgusu.
   - HTTP 4xx/5xx döndüğünde veya parse edilen ürün listesi 0 elemanlı geldiğinde sessizce çökmeyi engelleyen, acil durum uyarı düğümüne bağlanan hata dalı.

Ayrıca Node ortamında bu JS kodlarını bağımsız test edebilmek için 'B-n8n/' altına küçük test scriptleri ekle.

Adımı tamamlayınca:
1. Bu promptu, seçilen şablonu (#1952) ve mimari kararları 'promptlar/B-n8n.md' dosyasına ekle.
2. Yalnızca ErencanAcioglu kimliğiyle (kesinlikle Co-authored-by olmadan) commit at ve pushla:
   git add B-n8n/ promptlar/B-n8n.md && git commit -m "feat(n8n): design price tracking workflow with pagination, type safety and error branch"
   git push origin main
```

### Ön doğrulama — promptla çelişen iki bulgu

İş başlamadan önce prompttaki iki varsayım canlı veriyle kontrol edildi. İkisi de tutmadı:

1. **Şablon #1952 yok.**
   - `https://n8n.io/workflows/1952` → HTTP **404**; `api.n8n.io/api/templates/workflows/1952` → `"Not found"`.
   - Brief başlangıç şablonunun adını ve linkini zorunlu tutuyor; değerlendirme dürüstlüğe bakıyor. Bu yüzden var olmayan bir şablonu kaynak göstermek yerine şablon API'si taranıp ("scrape", "price tracking", "price monitor", "web scraping google sheets") aday şablonlar incelendi:
     - **#4640 — Competitor price monitoring with web scraping, Google Sheets & Telegram** (tonydatahut): zamanlayıcı, HTTP + HTML, fiyat normalize eden Code, Is Price Changed? IF, Sheets geçmişi, Telegram alarmı → **seçildi**. Link doğrulandı (HTTP 200).
     - #2275 — Automated web scraping: email a CSV, save to Google Sheets & Microsoft Excel: tek sayfa, değişiklik tespiti yok.
     - #1073 — Scrape and store data from multiple website pages: sayfalama var, ama MongoDB ve eski düğüm sürümleri.
2. **Ürün adına göre kıyaslama yanlış alarm üretir.**
   - 20 sayfanın tamamı çekildi: **117 ürün, yalnızca 88 farklı ad**. Örneğin "Dell Latitude 5480" 8 kez, "Acer Aspire ES1-572 Black" 5 kez geçiyor; hepsi farklı özellik ve fiyatta.
   - Ada göre eşleştirme bu ürünleri birbirine karıştırıp sahte fiyat alarmı üretirdi.
   - **Karar:** Karşılaştırma anahtarı sitedeki ürün kimliği (`/product/{id}`), yani 117 benzersiz değer. Bildirimde ad + `#id` gösteriliyor.

Diğer keşifler:
- Sayfa 1–19'da 6 ürün, sayfa 20'de 3 ürün var. Sayfa 21 ve sonrası **HTTP 200 ile boş** dönüyor; yani sayfalama hata koduna göre değil, içeriğe göre durdurulmalı.
- Son sayfada `rel="next"` bağlantısı yok.
- Sayfanın başında `117 items` sayacı var; ayrıştırılan ürün sayısını doğrulamak için kullanıldı.

### Mimari kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| Sayfalama | HTTP Request 4.2'nin **yerleşik sayfalaması**: `page={{ $pageCount + 1 }}`; bitiş ifadesi "ürün kartı yok **veya** next bağlantısı yok"; `maxRequests: 50`; 300 ms aralık | n8n'e özgü, tek düğümde döngü. Durma koşulu hem son sayfada (next yok) hem boş sayfada (kart yok) tetikleniyor; 50 istek sınırı sonsuz döngüye karşı sigorta. Ayrıştırıcı tekrarları URL'ye göre ayıkladığı için aynı sayfa iki kez gelse de veri bozulmuyor. |
| Tip güvenliği | `parseFloat(String(ham).replace(/[^0-9.]/g, ''))` + `Number.isFinite`; geçersiz kart atlanıp sayılıyor; `scraped_at` ISO | Prompttaki ifade birebir kullanıldı; NaN asla tabloya sızmıyor |
| Veri doğrulama | IF: 0 ürün **veya** sitenin bildirdiği sayının %90'ından azı → hata dalı | Eksik veri tabloya yazılırsa ertesi gün sahte "yeni ürün" alarmı olur |
| Tablo | Google Sheets: `fiyat_gecmisi` (append, tarih damgalı) + `son_durum` (`urun_id` ile upsert) | Şablonla uyumlu; brief tarih damgalı tablo istiyor |
| Değişiklik tespiti | Code: kuruş cinsinden tam sayı karşılaştırması → `indirim` / `artis` / `yeni` / `degismedi` | Kayan nokta gürültüsü sahte alarm üretmesin |
| Dallanma | Switch 3.2, üç isimli çıkış: İndirim Alarmı / Fiyat Artışı / Yeni Ürün | Prompttaki üç dal |
| Bildirim | Dal başına **tek özet mesaj** (en fazla 15 satır, 4000 karakter); ilk çalışmada "117 ürün referans kaydedildi" mesajı | Ürün başına mesaj ilk gün 117 mesajlık spam olurdu |
| Hata dalı | `onError: "continueErrorOutput"` (ayrı, görünür hata çıkışı) + `retryOnFail` 3 deneme; IF false; Sheets okuma hata çıkışı; **Error Trigger** → tek "Hata Mesajı Hazırla" → Acil Uyarı | Prompt `continueRegularOutput` önerdi; `continueErrorOutput` hatayı ayrı bir dala ayırdığı için canvas'ta daha net ve normal veriyle karışmıyor |
| Kod yönetimi | Code düğümü kaynakları `kod/*.js`; `araclar/olustur.js` bunları workflow.json'a gömüyor, id'ler deterministik | Kod test edilebilir ve tek doğruluk kaynağı. Testler workflow.json'a **gömülü** kodu çalıştırıyor ve dosyalarla senkron olduğunu doğruluyor. |
| Saat dilimi | `settings.timezone: Europe/Istanbul` | 09:00 yerel saat |

### Yapılanlar (Claude)

- **`B-n8n/workflow.json`:** 19 düğüm (16 işlevsel + 3 açıklama notu), n8n import biçiminde. Kimlik bilgisi yok; `GOOGLE_SHEET_ID` / `TELEGRAM_CHAT_ID` yer tutucu.
- **`B-n8n/kod/`:** `ayristir.js`, `degisiklik.js`, `bildirim.js` (3 dalda ortak), `hata.js`.
- **`B-n8n/araclar/olustur.js`:** workflow.json üreticisi.
- **`B-n8n/test/`** (Node ≥18, bağımlılık yok):
  - `n8n-kum-havuzu.js`: `$input` / `$()` taklidi, gömülü kodu `vm` içinde çalıştırır.
  - `ayristir.test.js`, `degisiklik.test.js`, `bildirim-hata.test.js`, `workflow.test.js`: **31 test**, gerçek site HTML'i (`fixtures/`: sayfa 1, 20, boş 21) ile.
  - `canli-kazima.js`: gerçek siteyi aynı sayfalama kurallarıyla gezen uçtan uca simülasyon.
- **`B-n8n/akis-aciklama.md`:** Adım adım akış, başlangıç şablonu (#4640, ad + link), #1952 notu, şablondan yapılan değişiklikler tablosu, kurulum ve sınırlar.
- **`B-n8n/package.json`:** `npm run olustur | test | canli`.

**Testin yakaladığı gerçek hata:**
- İlk koşuda 31 testten 1'i başarısız oldu ("bozuk önceki satırlar yok sayılır").
- Sebep: `Number('') === 0`. Google Sheets'teki boş fiyat hücresi önceki fiyat **$0** olarak okunuyor ve "$0 → $416.99" şeklinde sahte bir **Fiyat Artışı** alarmı üretiyordu.
- Düzeltme: boş/boşluk hücre `NaN` sayılıyor, ayrıca fiyat > 0 şartı eklendi. Sonrasında 31/31 geçti.

**Canlı simülasyon sonucu (28.09.2026):**
- Sayfalama **20 istekte** kendiliğinden durdu (sınır 50).
- **117 ürün** ayrıştırıldı; site de 117 bildiriyor. 117 benzersiz kimlik, 88 benzersiz ad, 0 geçersiz fiyat, tüm fiyatlar `number`.
- Gün 1 (boş tablo): tek "İlk çalışma: 117 ürün referans fiyat olarak kaydedildi" mesajı.
- Gün 2 (3 fiyat değiştirildi, 1 ürün silindi): 2 indirim, 1 artış, 1 yeni ürün, 113 değişmedi; üç dalın mesajları doğru üretildi.
- Boş site senaryosu: acil uyarı mesajı üretildi.

**Sınırlar (akis-aciklama.md'de de yazılı):**
- Akış n8n'de canlı çalıştırılmadı.
- HTTP düğümünün sayfalama davranışı Node simülasyonunda taklit edildi, gerçek n8n'de doğrulanmadı.
- Error Trigger için Workflow Settings → Error workflow ayarı gerekiyor.
- Kaldırılan ürünler bildirilmiyor.

---

## Prompt 2 — Son teslimat (ortak prompt)

README, ham oturum logu ve final kontrolleri kapsayan bu prompt her iki bölüme ait olduğu için tam metni ve yapılanlar
[`A-claude-code.md` › Prompt 9](A-claude-code.md#prompt-9--son-teslimat-readme-ham-oturum-logu-final-kontroller) altında kayıtlı.
B ile ilgili kısmı: README'de B özeti, `npm test` / `npm run canli` talimatları ve #4640 / ürün kimliği kararlarının
açıklaması. Son kontrolde B testleri 31/31 geçti.

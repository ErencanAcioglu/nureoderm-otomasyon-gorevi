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

---

## Prompt 3 — Son kabul ve denetim turu (ortak prompt, kod değişikliği yok)

Tam metin ve rapor özeti: [`A-claude-code.md` › Prompt 10](A-claude-code.md#prompt-10--son-kabul-ve-denetim-turu-kod-değişikliği-yok).

B'ye ait bulgular:
- Görev metnindeki tüm zorunlu B maddeleri karşılanmış.
- **Bonus olan n8n ekran görüntüsü yok.**
- **Doğrulanmamış risk:** `workflow.json`'ın gerçek n8n'e import edilebilirliği. Öneri olarak "n8n kurmadan, gerçek düğüm tanımlarına karşı şema doğrulaması" sunuldu.

---

## Prompt 4 — n8n şema doğrulaması (ortak prompt, B kısmı)

Tam metin: [`A-claude-code.md` › Prompt 11](A-claude-code.md#prompt-11--hibrit-taslak-n8n-şema-doğrulaması-ekran-görüntüleri-final).

### Yapılanlar (Claude)

**Kaynak:**
- `npm view n8n-nodes-base` → sürüm 2.15.1; paket açık hali 72 MB, tarball 9 MB.
- `npm pack` ile yalnızca dosya olarak indirildi; bağımlılık kurulmadı, n8n çalıştırılmadı.
- İçinden n8n editörünün kullandığı `dist/types/nodes.json` (485 düğüm tanımı) çıkarıldı.
- `B-n8n/.cache/` altında tutuluyor (`.gitignore`'da). Sürüm tekrarlanabilirlik için `2.15.1`'e sabitlendi.

**Keşif:**
- Kullandığımız 9 düğüm tipinin hepsi ve tam sürümleri tanımlarda var: httpRequest 4.2, googleSheets 4.5, scheduleTrigger 1.2, code 2, if 2.2, switch 3.2, telegram 1.2, errorTrigger 1, stickyNote 1.
- Sheets `operation` değerleri arasında `read` var.
- `displayOptions` sürüm koşulları `_cnd` biçiminde (`gte`, `lt`, `between`…).

**`araclar/sema-dogrula.js`:**
- Her düğüm için tip ve `typeVersion` kontrolü.
- Her parametre için:
  - ad tanımlı mı,
  - `displayOptions`'a göre görünür mü (varsayılan değerler ve `@version` / `/kök` referansları dahil; görünmeyen parametreyi n8n sessizce yok sayar),
  - `options` / `multiOptions` değerleri, boolean / number / string tipleri,
  - `collection` ve `fixedCollection` iç yapıları (tek ya da çoklu değer),
  - `resourceLocator` modu, `resourceMapper` eşleme modu, `filter` koşul yapısı.
- Düğüm ayarları: `onError`, `retryOnFail`, `maxTries` (2–5), `waitBetweenTries` (≤5000).
- Bağlantılar: bağlı çıkış sayısı ≤ düğümün çıkış sayısı. IF = 2, Switch = kural sayısı; `continueErrorOutput` +1 ekler.
- Gereken kimlikleri de `displayOptions`'a göre hesaplıyor.

**Sonuç:**
- **19/19 düğüm geçerli · 19 bağlantı · 0 hata** → `workflow.json`'da parametre uyumsuzluğu bulunmadı, düzeltme gerekmedi.
- Gereken kimlikler: Google Sheets OAuth2 (3 düğüm), Telegram API (2 düğüm).

**Doğrulayıcının kendi hatası (bulundu, düzeltildi):**
- İlk sürüm HTTP düğümü için `httpSslAuth`, Sheets için `googleApi` kimliklerini "gerekli" listeliyordu.
- Bu kimlikler yalnızca belirli ayarlarda (SSL sertifikası açık / servis hesabı) gerekli. Kimlik koşulları da `displayOptions`'a göre değerlendirilecek şekilde düzeltildi.

**Doğrulayıcının boşuna geçmediğinin kanıtı:** "0 hata" ilk çalıştırmada şüpheli bulundu. `workflow.json`'ın 10 bilinçli bozulmuş kopyası denendi ve **10'u da yakalandı**:
- Sheets `operation: "getAll"`,
- sayfalamada `maxRequest` yazım hatası,
- `responseFormat: "html"`,
- JSON yanıtta görünmeyen `outputPropertyName` (displayOptions),
- `httpRequest` v4.9,
- Code'da `jsCode` yerine `code`,
- `onError: "continue"`,
- IF'e 3. çıkış bağlanması,
- string `maxRequests`,
- `sheetName.mode: "gid"`.

Bunlar `test/sema.test.js`'e kalıcı test olarak eklendi. Ağ yoksa bu testler atlanıyor.

**Diğer:**
- `package.json`'a `npm run dogrula` eklendi.
- workflow.json'daki "Kurulum" notuna doğrulama satırı eklendi (`olustur.js` → yeniden üretildi).
- `akis-aciklama.md`'ye "Şema doğrulaması" bölümü eklendi.

**B testleri: 42/42** (31 akış + 11 şema).

**Sınır:** Şema doğrulaması **yapıyı** kanıtlar, çalışma anını kanıtlamaz. Örneğin metin yanıtında `$response.body` içeriği hâlâ ancak gerçek bir n8n çalıştırmasıyla doğrulanabilir.

---

## Prompt 5 — Gerçek n8n'de çalıştırma (ortak prompt, B kısmı)

Tam metin: [`A-claude-code.md` › Prompt 13](A-claude-code.md#prompt-13--b-bonusu-gerçek-n8nde-çalıştırma-ve-ekran-görüntüsü).

### Yapılanlar (Claude)

**Kurulum:**
- `npm view n8n` → 2.40.7, `engines: node >=24` (makinede v24.7.0; uyumlu).
- Scratchpad'deki ayrı bir klasöre `npm install n8n@2.40.7` kuruldu (2 dk, 2,5 GB); repo ve ev dizini kirletilmedi.
- Ortam değişkenleri:
  - `N8N_USER_FOLDER` → geçici klasör (boş SQLite),
  - dinleme yalnızca `127.0.0.1`,
  - telemetri / sürüm bildirimi / şablon / kişiselleştirme kapalı,
  - `GENERIC_TIMEZONE=Europe/Istanbul`.

**İçe aktarma ve gerçek n8n'in bulduğu hata:**
- `n8n import:workflow --input=B-n8n/workflow.json` **başarısız oldu**: `SQLITE_CONSTRAINT: NOT NULL constraint failed: workflow_entity.id`.
  - Sebep: `workflow.json`'da üst düzey `id` yok; n8n'in kendi dışa aktarımları 16 karakterlik `id` taşır.
  - Şema doğrulaması düğüm tanımlarını denetlediği için bunu göremezdi.
  - Geçici kopyada `id` eklenerek doğrulandı; ardından `olustur.js`'e `id: 'NrdmFiyatTakip01'` eklendi, `workflow.test.js`'e 16 karakter kontrolü kondu.
  - Repodaki `workflow.json` yeniden üretildi ve doğrudan içe aktarıldı → "Successfully imported 1 workflow".

**Editör ve ekran görüntüleri:**
- Yerel bir sahip hesabı REST ile oluşturuldu (`demo@yerel.test`, rastgele parola; yalnızca bu geçici örnek için).
- Headless Chrome, bağımlılıksız küçük bir CDP (Chrome DevTools Protocol) istemcisiyle yönetildi: giriş, workflow açma, "Execute workflow from Her Gün 09:00" düğmesine tıklama, sonucun REST'ten beklenmesi, "zoom to fit" ve ekran görüntüsü.
- Orijinal workflow tuvalde 16 düğüm + 3 not ile doğru görüntülendi. Sheets/Telegram'da kimlik uyarısı var; beklenen durum.

**Kimlik bilgisi sorunu ve çözümü:**
- Google Sheets ve Telegram kimlikleri yok. Bu yüzden **demo kopyada** yalnızca bu 5 düğüm n8n'in pin data özelliğiyle sabitlendi:
  - "Önceki durum": sitenin güncel ürünleri; #31, #32, #33'ün fiyatı değiştirilmiş, #34 çıkarılmış.
  - Diğer 4 düğüm: sabit "ok" çıktısı.
- Repodaki `workflow.json`'da pin data yok.

**Yürütmeler** (sonuçlar ekrandan değil, n8n veritabanındaki yürütme kaydından okundu):

| # | Senaryo | Sonuç |
|---|---|---|
| 4 | Normal gün | `success` · 13 düğüm · HTTP **[20, 0]** · 117 ürün, 0 geçersiz, 0 tekrar · IF [1, 0] · Switch **[2, 1, 1]** · 3 mesaj · hata dalı çalışmadı |
| 5 | `127.0.0.1:9` (bağlantı reddi) | `success` · HTTP **[0, 1]** (3 deneme sonrası hata çıkışı) → Hata Mesajı → Acil Uyarı · "Erişim hatası: connect ECONNREFUSED" |
| 2 | Var olmayan sayfa adresi | Site **HTTP 200** + boş sayfa döndü → 0 ürün → IF [0, 1] → acil uyarı ("Veri doğrulama hatası") |

**Doğrulanan / bulunan:**
- HTTP sayfalama alan adları ve `$response.body` bitiş koşulu **gerçek n8n'de çalışıyor**. Daha önce yalnızca simüle edilebilen tek konu buydu.
- Üretilen mesajlar Node.js simülasyonuyla birebir aynı.
- **Ekranda görülen şüpheli etiket kontrol edildi:** Tuvalde sabitlenmiş Sheets düğümünün hata bağlantısında da mor "116 items" etiketi görünüyordu. Yürütme kaydında "Hata Mesajı Hazırla"nın **çalışmadığı** doğrulandı; etiket, n8n'in pin data gösterim biçimi.
- Sitede var olmayan sayfaların bile 200 dönmesi, içerik tabanlı "0 ürün" doğrulamasının neden gerekli olduğunu kanıtladı.

**Ekran görüntüsü tutarlılığı:**
- İlk çekimlerde tuvaldeki "Kurulum" notu hâlâ "Canlı çalıştırılmadı" diyordu.
- Not güncellendi, workflow yeniden üretilip içe aktarıldı, yürütmeler tekrarlandı (#4, #5) ve son görüntüler bu sürümden alındı.
- Hata dalı için "(site 404)" başlıklı ilk demo kullanılmadı, çünkü site aslında 200 döndü ve başlık yanıltıcıydı. Yerine #5 kullanıldı.

**Kapatma:**
- n8n (5678/5679) ve Chrome (9222) `SIGTERM` ile kapatıldı; n8n logu "Stopping n8n...". Arka plan görevleri çıkış kodu 0.
- Portlar boş, n8n süreci yok.

**Belgeler:**
- `akis-aciklama.md`'ye "Gerçek n8n'de çalıştırma" bölümü eklendi; sınırlar güncellendi.
- README'de B bonusu "✅ Tamamlandı", `![n8n Akışı](docs/n8n-akisi.png)` gömülü; hata dalı görseli açılır bölümde.
- **Kalan sınır:** Sheets ve Telegram gerçek hesaplarla denenmedi (pin data).

**Testler:** B 42/42, şema doğrulaması 19/19.

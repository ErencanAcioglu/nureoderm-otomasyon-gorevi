# Bölüm B — Laptop Fiyat Takip Akışı (n8n)

`workflow.json` n8n'e **Import from File** ile doğrudan içe aktarılabilir. Akış her sabah 09:00'da
[webscraper.io laptop test sayfasının](https://webscraper.io/test-sites/e-commerce/static/computers/laptops)
**tüm sayfalarını** gezer. Fiyatları sayıya çevirip tarih damgasıyla Google Sheets'e yazar, bir önceki
çalışmayla karşılaştırır ve değişiklikleri Telegram'a bildirir. Hata olursa acil uyarı gönderir; akış
sessizce "başarılı" bitmez.

## Başlangıç şablonu

**[#4640 — Competitor price monitoring with web scraping, Google Sheets & Telegram](https://n8n.io/workflows/4640)**
(yazar: tonydatahut, n8n şablon kütüphanesi)

**Neden bu şablon:** Senaryomuza en yakın resmi şablon bu. İçinde günlük zamanlayıcı, HTTP Request + HTML
çekme, fiyat normalize eden Code düğümü, "Is Price Changed?" IF düğümü, Google Sheets fiyat geçmişi ve
Telegram alarmı var. Aday olarak #2275 (tek sayfa kazıma → Sheets/CSV) ve #1073 (çok sayfalı kazıma →
MongoDB) de incelendi. #4640 fiyat karşılaştırması ve bildirim içerdiği için seçildi.

> **Not — #1952:** Görev sırasında önce "Scrape website and save to Google Sheets" (#1952) şablonundan
> başlanması planlanmıştı. Ancak `https://n8n.io/workflows/1952` adresi **404** dönüyor ve n8n şablon
> API'si de bu kimlik için "Not found" yanıtı veriyor (28.09.2026'da kontrol edildi). Var olmayan bir
> şablonu kaynak göstermemek için kütüphane API'si taranıp gerçekten var olan en yakın şablon (#4640)
> seçildi.

## Akış adım adım

```
Her Gün 09:00 ─► Laptop Sayfalarını Çek (Sayfalama) ──başarı──► Ürünleri Ayrıştır ve Temizle ─► Veri Geçerli mi?
                              │ hata çıkışı                                                        │ true        │ false
                              ▼                                                                    ▼             ▼
                     Hata Mesajı Hazırla ◄──────────────────────────────────── Önceki Durumu Oku ──hata──►  (Hata)
                              ▲                                                  (son_durum)
         Error Trigger ───────┘                                                      │
                              ▼                                                      ▼
                     Acil Uyarı (Telegram)                                  Değişiklik Tespiti
                                                         ┌───────────────────────┼───────────────────────┐
                                                         ▼                       ▼                       ▼
                                          Fiyat Geçmişine Yaz        Son Durumu Güncelle      Değişim Türüne Göre Ayır
                                           (fiyat_gecmisi)             (son_durum)          İndirim │ Artış │ Yeni
                                                                                                 ▼       ▼       ▼
                                                                                              3 mesaj düğümü ─► Telegram
```

| # | Düğüm | Tür | Ne yapar |
|---|---|---|---|
| 1 | **Her Gün 09:00** | Schedule Trigger | Cron `0 9 * * *`; akış saat dilimi `Europe/Istanbul` |
| 2 | **Laptop Sayfalarını Çek (Sayfalama)** | HTTP Request 4.2 | n8n'in yerleşik sayfalaması: `page={{ $pageCount + 1 }}` ile `?page=1,2,3…`. **Durma koşulu:** sayfada ürün kartı yoksa *veya* "next" bağlantısı yoksa. **Sonsuz döngü koruması:** en fazla 50 istek. İstekler arası 300 ms, 15 sn zaman aşımı, 3 deneme. Hata olursa ayrı **hata çıkışı** (`continueErrorOutput`). |
| 3 | **Ürünleri Ayrıştır ve Temizle** | Code | Her karttan ad (`title` niteliği), açıklama, **fiyat**, yorum sayısı, puan, URL ve ürün kimliği. Fiyat `parseFloat(String(ham).replace(/[^0-9.]/g, ''))` ile `$416.99` → `416.99` (number) olur; çevrilemezse `null` olur ve kart atlanıp sayılır, **NaN asla üretilmez**. Her ürüne `scraped_at` (ISO) eklenir. Sayfalar arası tekrarlar URL'ye göre ayıklanır. Sitenin bildirdiği ürün sayısı (`117 items`) okunur. |
| 4 | **Veri Geçerli mi?** | IF | 0 ürün **veya** bildirilen sayının %90'ından azı ayrıştırıldıysa → hata dalı. Böylece eksik veri tabloya yazılıp ertesi gün sahte "yeni ürün" alarmlarına yol açmaz. |
| 5 | **Önceki Durumu Oku (son_durum)** | Google Sheets (read) | Bir önceki çalışmanın ürün başına son fiyatı. İlk çalışmada tablo boş olsa da akış devam eder (`alwaysOutputData`); okuma hatası hata dalına gider. |
| 6 | **Değişiklik Tespiti** | Code | Bugün ile dünü **ürün kimliğine** göre karşılaştırır: `indirim` / `artis` / `yeni` / `degismedi`. Fark ve yüzde hesaplanır. Kuruş cinsinden tam sayı karşılaştırması yapıldığı için kayan nokta gürültüsü sahte alarm üretmez. |
| 7 | **Fiyat Geçmişine Yaz (fiyat_gecmisi)** | Google Sheets (append) | Her çalışmada tüm ürünler **tarih damgasıyla** eklenir; fiyat geçmişi tablosu budur. |
| 8 | **Son Durumu Güncelle (son_durum)** | Google Sheets (appendOrUpdate) | `urun_id` ile upsert; ertesi günün karşılaştırma tabanıdır. |
| 9 | **Değişim Türüne Göre Ayır** | Switch | 3 isimli çıkış: **İndirim Alarmı**, **Fiyat Artışı**, **Yeni Ürün**. `degismedi` hiçbir dala gitmez. |
| 10 | **İndirim / Artış / Yeni Ürün Mesajı** | Code ×3 | Her dal **tek** özet mesaj üretir: en fazla 15 satır, fazlası "… ve N ürün daha", 4000 karakter sınırı. İlk çalışmada 117 satırlık liste yerine "117 ürün referans olarak kaydedildi" mesajı gider. |
| 11 | **Telegram Bildirimi** | Telegram | Mesajları gönderir. Slack istenirse bu düğüm Slack düğümüyle değiştirilebilir; `mesaj` alanı aynı kalır. |
| 12 | **Hata Mesajı Hazırla → Acil Uyarı (Telegram)** | Code + Telegram | Dört kaynaktan beslenir: HTTP hata çıkışı (4xx/5xx, zaman aşımı), 0 ürün / eksik veri, Sheets okuma hatası ve **Error Trigger** (beklenmeyen çöküş). Mesajda neden, zaman, kaç sayfa/ürün işlendiği ve "tablo güncellenmedi" bilgisi yer alır. |

**Tablo seçimi:** Google Sheets (şablonla uyumlu). Kurulum için iki sayfa ve başlık satırları gerekir:

- `fiyat_gecmisi`: `scraped_at | urun_id | ad | aciklama | fiyat | onceki_fiyat | degisim | fark | fark_yuzde | yorum_sayisi | puan | url | sayfa`
- `son_durum`: `urun_id | ad | aciklama | fiyat | yorum_sayisi | url | scraped_at`

## Şablondan neyi değiştirdim

| Şablon #4640 | Bu akış | Neden |
|---|---|---|
| Ürün URL listesi Sheets'ten okunur, her ürün sayfası ayrı çekilir | Kategori sayfası `?page=N` ile **sayfalanır**; tüm ürünler buradan çıkarılır | Görev tüm sayfaları gezmeyi istiyor; ürün listesi önceden bilinmiyor |
| HTML düğümü + CSS seçici ile tek fiyat alanı | Tek Code düğümü: ad, açıklama, fiyat, yorum, puan, URL, kimlik | Birden çok alan gerekiyor; kart bazlı ayrıştırma sayfa başına tek geçişte yapılıyor |
| Fiyat `parseFloat(...replace(/[^0-9.]+/g, ''))`; NaN kontrolü yok | Aynı temizleme + `Number.isFinite` kontrolü, geçersiz kart sayılıp atlanır | Bozuk fiyat `NaN` olarak tabloya ve karşılaştırmaya sızmasın |
| Değişiklik = `last_price !== current_price` (float karşılaştırma) | Kuruş cinsinden tam sayı karşılaştırması + indirim/artış/yeni ayrımı | Kayan nokta gürültüsü; brief üç ayrı dal istiyor |
| Eşleştirme ürün URL'sine göre (Sheets'teki liste) | Eşleştirme **ürün kimliğine** göre (`/product/{id}`) | Sitede 117 ürün ama **88 farklı ad** var (ör. 8 farklı "Dell Latitude 5480"); ada göre eşleştirme sahte alarm üretir |
| IF (değişti mi?) → her ürün için ayrı Telegram mesajı | Switch (3 dal) → dal başına tek özet mesaj | İlk çalışmada 117 ayrı mesaj gitmesini önlemek |
| Hata dalı yok | HTTP hata çıkışı + 3 deneme, veri doğrulama IF'i, Sheets hata çıkışı, Error Trigger | Brief: akış sessizce "başarılı" bitmemeli |
| Sheets kolon adlarında sekme/boşluk (`"timestamp\t"`, `"price_changed        "`) ve bunları temizleyen ek bir Code düğümü | Açık tanımlı, temiz kolon şeması | Şablondaki hatayı taşımamak |
| `Wait` düğümleriyle istek aralığı | HTTP düğümünün `requestInterval` (300 ms) seçeneği | Sayfalama tek düğümde, ek düğüm gerekmiyor |

## Test ve doğrulama (n8n olmadan)

Code düğümlerinin kaynağı `kod/*.js`; `araclar/olustur.js` bunları `workflow.json` içine gömer. Testler
`workflow.json`'a **gömülü** kodu çalıştırır, yani test edilen kod n8n'e import edilecek kodun kendisidir.

```bash
cd B-n8n
node araclar/olustur.js       # kod/*.js → workflow.json                        (npm run olustur)
node --test test/*.test.js    # 42 test: 31 akış + 11 şema doğrulama             (npm test)
node araclar/sema-dogrula.js  # n8n düğüm tanımlarına karşı şema doğrulaması       (npm run dogrula)
node test/canli-kazima.js     # canlı uçtan uca simülasyon                         (npm run canli)
```

- **Şema doğrulaması (n8n kurmadan):**
  - `araclar/sema-dogrula.js`, n8n editörünün kullandığı gerçek düğüm tanımlarını (`n8n-nodes-base@2.15.1`
    › `dist/types/nodes.json`) `npm pack` ile yalnızca dosya olarak indirir (~9 MB, kurulum yok, `.cache/`
    gitignore'da).
  - Denetlediği her şey:
    - düğüm tipi ve `typeVersion`,
    - her parametre adı,
    - seçenek değerleri,
    - boolean/number tipleri,
    - `displayOptions` görünürlük kuralları (sürüm koşulları dahil),
    - `collection` / `fixedCollection` iç yapıları,
    - `resourceLocator` modu, `resourceMapper` eşleme modu, `filter` yapısı,
    - `onError` / retry ayarları,
    - bağlantılardaki çıkış sayıları.
  - Kimlik bilgisi gereksinimleri de `displayOptions`'a göre hesaplanır.
  - **Sonuç: 19/19 düğüm geçerli, 19 bağlantı, 0 hata** → `workflow.json`'da düzeltme gerekmedi.
    Gereken kimlikler: Google Sheets OAuth2 ve Telegram API.
  - Doğrulayıcının gerçekten hata yakaladığı 10 bilinçli bozmayla test edildi: Sheets `operation: "getAll"`,
    `maxRequest` yazım hatası, `responseFormat: "html"`, JSON yanıtta görünmeyen `outputPropertyName`,
    `httpRequest` v4.9, Code'da `jsCode` yerine `code`, `onError: "continue"`, IF'e 3. çıkış,
    string `maxRequests`, `sheetName.mode: "gid"`. Hepsi yakalandı.
- **Akış birim testleri (31):**
  - Ayrıştırma: gerçek sayfa 1, sayfa 20 ve boş sayfa 21 HTML'i.
  - Fiyat tip güvenliği; "117 ürünün 9'u" eksik veri senaryosu; tekrar eden sayfa; bozuk fiyat.
  - Sayfalama bitiş ifadesi (sayfa 1 → devam, 20 → dur, 21 → dur).
  - Değişiklik türleri; kayan nokta; aynı adlı farklı ürünler; bozuk önceki satırlar.
  - Bildirim metinleri ve kısaltma; 4 hata kaynağı.
  - workflow.json yapısı (benzersiz ad/id, bağlantılar, brief'teki 5 madde).
  - Gömülü kodun `kod/*.js` ile aynı olduğu; workflow.json'da kimlik bilgisi olmadığı.
- **Canlı simülasyon (28.09.2026):**
  - Sayfalama **20 istekte** kendiliğinden durdu (sınır 50).
  - **117 ürün** ayrıştırıldı; site de 117 bildiriyor. Kimliklerin 117'si benzersiz, adların yalnızca 88'i.
  - Tüm fiyatlar `number` tipinde.
  - "İkinci gün" senaryosunda 2 indirim, 1 artış ve 1 yeni ürün doğru ayrıldı ve mesajları üretildi.
- **Testin yakaladığı hata:** `Number('') === 0` olduğu için Sheets'teki boş fiyat hücresi önceki fiyat
  $0 sayılıyor ve sahte bir "Fiyat Artışı" alarmı üretiyordu. Düzeltildi: boş hücre artık geçersiz sayılıyor.

## Sınırlar ve dürüst notlar

- **Akış n8n'de canlı çalıştırılmadı** (görev gerektirmiyor). `workflow.json`'ın **yapısı** n8n'in gerçek
  düğüm tanımlarına karşı doğrulandı (19/19). Code düğümleri n8n'in `$input` / `$()` arayüzünü taklit eden
  bir kum havuzunda test edildi. HTTP sayfalama davranışı canlı simülasyonda aynı kurallarla (aynı bitiş
  ifadesi, aynı sınır) taklit edildi. Doğrulanamayan tek şey çalışma anı davranışı (ör. metin yanıtında
  `$response.body`'nin içeriği); import sonrası tek bir manuel çalıştırmayla doğrulanması önerilir.
- `$pageCount`'un ilk istekte `0` olduğu varsayıldı (n8n dokümantasyonundaki `{{ $pageCount + 1 }}`
  kalıbı). İlk istek parametresiz giderse site yine sayfa 1'i döner; ayrıştırıcı URL'ye göre tekrar
  ayıkladığı için veri bozulmaz, en fazla bir fazladan istek yapılır.
- **Error Trigger** yalnızca bu akış n8n'de *Workflow Settings → Error workflow* olarak seçildiğinde
  tetiklenir. Üretimde bu dalın ayrı bir "hata akışına" taşınması daha yaygın bir düzendir.
- Siteden **kaldırılan** ürünler şu an bildirilmiyor; `son_durum`'da son görülme tarihiyle kalıyor.
  Dördüncü bir Switch dalıyla eklenebilir.
- Kimlik bilgileri (Google Sheets, Telegram) ve `GOOGLE_SHEET_ID` / `TELEGRAM_CHAT_ID` yer tutucuları
  import sonrası doldurulmalı; workflow.json'da gizli bilgi yok.

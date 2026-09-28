#!/usr/bin/env node
// workflow.json üreticisi. Code düğümlerinin kaynağı kod/*.js dosyalarıdır (tek doğruluk kaynağı);
// bu betik onları n8n'e import edilebilir workflow.json içine gömer. Düğüm id'leri addan türetilir,
// böylece yeniden üretim gereksiz diff oluşturmaz.
//
// Kullanım: node B-n8n/araclar/olustur.js

'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const KOK = path.resolve(__dirname, '..');
const kod = (ad) => fs.readFileSync(path.join(KOK, 'kod', ad), 'utf8');

const SITE_URL = 'https://webscraper.io/test-sites/e-commerce/static/computers/laptops';
const SHEET_URL = 'https://docs.google.com/spreadsheets/d/GOOGLE_SHEET_ID/edit';
const TELEGRAM_CHAT_ID = 'TELEGRAM_CHAT_ID';
const SABLON = { id: 4640, url: 'https://n8n.io/workflows/4640' };

// Sayfalama bitiş koşulu: sayfada ürün kartı yoksa YA DA "sonraki sayfa" bağlantısı yoksa dur.
// Ek sigorta: maxRequests (sonsuz döngü koruması).
const SAYFALAMA_BITTI = "={{ !String($response.body ?? '').includes('class=\"card thumbnail\"')"
  + " || !String($response.body ?? '').includes('rel=\"next\"') }}";
const EN_FAZLA_SAYFA = 50;

const uuid = (ad) => {
  const h = crypto.createHash('sha1').update(`nureoderm-fiyat-takip:${ad}`).digest('hex');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20, 32)}`;
};

const dugum = (ad, tip, surum, konum, parametreler, ek = {}) => ({
  id: uuid(ad), name: ad, type: tip, typeVersion: surum, position: konum, parameters: parametreler, ...ek,
});

const kodDugumu = (ad, konum, jsKodu, ek = {}) => dugum(
  ad, 'n8n-nodes-base.code', 2, konum, { mode: 'runOnceForAllItems', jsCode: jsKodu }, ek,
);

const kosul = (id, sol, operator, sag = '') => ({ id: uuid(id), leftValue: sol, rightValue: sag, operator });
const kosulGrubu = (kosullar) => ({
  options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 },
  conditions: kosullar,
  combinator: 'and',
});

const sheetKolonlari = (kolonlar, eslesen = []) => ({
  mappingMode: 'defineBelow',
  value: Object.fromEntries(kolonlar.map(([ad]) => [ad, `={{ $json.${ad} }}`])),
  matchingColumns: eslesen,
  schema: kolonlar.map(([ad, tip]) => ({
    id: ad, displayName: ad, required: false, defaultMatch: false, display: true,
    type: tip, canBeUsedToMatch: true,
  })),
  attemptToConvertTypes: false,
  convertFieldsToString: false,
});
const sheet = (sayfaAdi) => ({
  documentId: { __rl: true, mode: 'url', value: SHEET_URL },
  sheetName: { __rl: true, mode: 'name', value: sayfaAdi },
});

const not = (ad, konum, genislik, yukseklik, renk, icerik) => dugum(
  ad, 'n8n-nodes-base.stickyNote', 1, konum, { content: icerik, width: genislik, height: yukseklik, color: renk },
);

const bildirimKodu = (tur) => kod('bildirim.js').replace("const TUR = '__TUR__';", `const TUR = '${tur}';`);

const D = {
  tetik: 'Her Gün 09:00',
  http: 'Laptop Sayfalarını Çek (Sayfalama)',
  ayristir: 'Ürünleri Ayrıştır ve Temizle',
  gecerli: 'Veri Geçerli mi?',
  oncekiOku: 'Önceki Durumu Oku (son_durum)',
  degisiklik: 'Değişiklik Tespiti',
  gecmis: 'Fiyat Geçmişine Yaz (fiyat_gecmisi)',
  sonDurum: 'Son Durumu Güncelle (son_durum)',
  ayir: 'Değişim Türüne Göre Ayır',
  indirim: 'İndirim Alarmı Mesajı',
  artis: 'Fiyat Artışı Mesajı',
  yeni: 'Yeni Ürün Mesajı',
  telegram: 'Telegram Bildirimi',
  hata: 'Hata Mesajı Hazırla',
  acil: 'Acil Uyarı (Telegram)',
  hataTetik: 'Hata Yakalayıcı (Error Trigger)',
};

const nodes = [
  not('Not: Genel Bakış', [-80, -560], 640, 400, 7, [
    '## Laptop Fiyat Takibi (webscraper.io)',
    '',
    `**Başlangıç şablonu:** [#${SABLON.id} — Competitor price monitoring with web scraping, Google Sheets & Telegram](${SABLON.url})`,
    '',
    '1. **Her gün 09:00** (Europe/Istanbul, cron `0 9 * * *`)',
    '2. **Sayfalama:** `?page=1,2,…` — ürün kartı ya da "next" bağlantısı kalmayınca durur; en fazla 50 sayfa',
    '3. **Ayrıştırma:** ad, açıklama, fiyat (`$416.99` → `416.99` sayı), yorum sayısı, URL, `scraped_at`',
    '4. **Tablo:** Google Sheets `fiyat_gecmisi` (tarih damgalı, append) + `son_durum` (ürün başına son fiyat)',
    '5. **Değişiklik tespiti:** ürün kimliğine göre (`/product/{id}`) → İndirim / Artış / Yeni → Telegram',
    '6. **Hata dalı:** HTTP hatası, 0/eksik ürün, Sheets okuma hatası, beklenmeyen çöküş → Acil uyarı',
  ].join('\n')),
  not('Not: Kurulum', [600, -560], 520, 260, 5, [
    '### Kurulum',
    '- Google Sheets: `GOOGLE_SHEET_ID` yerine tablo adresi; iki sayfa: `fiyat_gecmisi`, `son_durum` (başlık satırları akis-aciklama.md\'de)',
    '- Telegram: kimlik bilgisi + `TELEGRAM_CHAT_ID`',
    '- Error Trigger: Workflow Settings → Error workflow → bu akış (ya da ayrı hata akışı)',
    '- Canlı çalıştırılmadı; Code düğümleri Node.js ile gerçek site HTML\'i üzerinde test edildi (B-n8n/test).',
  ].join('\n')),

  dugum(D.tetik, 'n8n-nodes-base.scheduleTrigger', 1.2, [0, 0], {
    rule: { interval: [{ field: 'cronExpression', expression: '0 9 * * *' }] },
  }),

  dugum(D.http, 'n8n-nodes-base.httpRequest', 4.2, [240, 0], {
    url: SITE_URL,
    sendHeaders: true,
    headerParameters: { parameters: [{ name: 'User-Agent', value: 'nureoderm-fiyat-takip/1.0 (+n8n)' }] },
    options: {
      timeout: 15000,
      response: { response: { responseFormat: 'text', outputPropertyName: 'html' } },
      pagination: {
        pagination: {
          paginationMode: 'updateAParameterInEachRequest',
          parameters: { parameters: [{ type: 'qs', name: 'page', value: '={{ $pageCount + 1 }}' }] },
          paginationCompleteWhen: 'other',
          completeExpression: SAYFALAMA_BITTI,
          limitPagesFetched: true,
          maxRequests: EN_FAZLA_SAYFA,
          requestInterval: 300,
        },
      },
    },
  }, { retryOnFail: true, maxTries: 3, waitBetweenTries: 2000, onError: 'continueErrorOutput' }),

  kodDugumu(D.ayristir, [480, -100], kod('ayristir.js')),

  dugum(D.gecerli, 'n8n-nodes-base.if', 2.2, [720, -100], {
    conditions: kosulGrubu([
      kosul('veri-gecerli', '={{ $json.veri_gecerli }}', { type: 'boolean', operation: 'true', singleValue: true }),
    ]),
    options: {},
  }),

  dugum(D.oncekiOku, 'n8n-nodes-base.googleSheets', 4.5, [960, -200], {
    operation: 'read', ...sheet('son_durum'), options: {},
  }, { alwaysOutputData: true, executeOnce: true, onError: 'continueErrorOutput' }),

  kodDugumu(D.degisiklik, [1200, -220], kod('degisiklik.js')),

  dugum(D.gecmis, 'n8n-nodes-base.googleSheets', 4.5, [1480, -460], {
    operation: 'append', ...sheet('fiyat_gecmisi'),
    columns: sheetKolonlari([
      ['scraped_at', 'string'], ['urun_id', 'number'], ['ad', 'string'], ['aciklama', 'string'],
      ['fiyat', 'number'], ['onceki_fiyat', 'number'], ['degisim', 'string'], ['fark', 'number'],
      ['fark_yuzde', 'number'], ['yorum_sayisi', 'number'], ['puan', 'number'], ['url', 'string'],
      ['sayfa', 'number'],
    ]),
    options: {},
  }),

  dugum(D.sonDurum, 'n8n-nodes-base.googleSheets', 4.5, [1480, -280], {
    operation: 'appendOrUpdate', ...sheet('son_durum'),
    columns: sheetKolonlari([
      ['urun_id', 'number'], ['ad', 'string'], ['aciklama', 'string'], ['fiyat', 'number'],
      ['yorum_sayisi', 'number'], ['url', 'string'], ['scraped_at', 'string'],
    ], ['urun_id']),
    options: {},
  }),

  dugum(D.ayir, 'n8n-nodes-base.switch', 3.2, [1480, -60], {
    rules: {
      values: [
        ['indirim', 'İndirim Alarmı'], ['artis', 'Fiyat Artışı'], ['yeni', 'Yeni Ürün'],
      ].map(([deger, cikis]) => ({
        conditions: kosulGrubu([
          kosul(`degisim-${deger}`, '={{ $json.degisim }}', { type: 'string', operation: 'equals' }, deger),
        ]),
        renameOutput: true,
        outputKey: cikis,
      })),
    },
    options: {},
  }),

  kodDugumu(D.indirim, [1740, -220], bildirimKodu('indirim')),
  kodDugumu(D.artis, [1740, -60], bildirimKodu('artis')),
  kodDugumu(D.yeni, [1740, 100], bildirimKodu('yeni')),

  dugum(D.telegram, 'n8n-nodes-base.telegram', 1.2, [2000, -60], {
    chatId: TELEGRAM_CHAT_ID, text: '={{ $json.mesaj }}', additionalFields: { appendAttribution: false },
  }),

  dugum(D.hataTetik, 'n8n-nodes-base.errorTrigger', 1, [960, 460], {}),
  kodDugumu(D.hata, [1200, 360], kod('hata.js')),
  dugum(D.acil, 'n8n-nodes-base.telegram', 1.2, [1480, 360], {
    chatId: TELEGRAM_CHAT_ID, text: '={{ $json.mesaj }}', additionalFields: { appendAttribution: false },
  }),

  not('Not: Hata Dalı', [880, 300], 760, 300, 3, [
    '### Hata dalı — akış sessizce "başarılı" bitmez',
    'HTTP 4xx/5xx · zaman aşımı (3 deneme sonrası) · 0 ürün · eksik veri (<%90) · Sheets okuma hatası · beklenmeyen çöküş',
  ].join('\n')),
];

const bag = (...hedefler) => hedefler.map((cikis) => (cikis || []).map((node) => ({ node, type: 'main', index: 0 })));

const connections = {
  [D.tetik]: { main: bag([D.http]) },
  [D.http]: { main: bag([D.ayristir], [D.hata]) }, // 0: başarı, 1: hata çıkışı
  [D.ayristir]: { main: bag([D.gecerli]) },
  [D.gecerli]: { main: bag([D.oncekiOku], [D.hata]) }, // 0: true, 1: false
  [D.oncekiOku]: { main: bag([D.degisiklik], [D.hata]) },
  [D.degisiklik]: { main: bag([D.gecmis, D.sonDurum, D.ayir]) },
  [D.ayir]: { main: bag([D.indirim], [D.artis], [D.yeni]) },
  [D.indirim]: { main: bag([D.telegram]) },
  [D.artis]: { main: bag([D.telegram]) },
  [D.yeni]: { main: bag([D.telegram]) },
  [D.hataTetik]: { main: bag([D.hata]) },
  [D.hata]: { main: bag([D.acil]) },
};

const workflow = {
  name: 'Laptop Fiyat Takibi — webscraper.io (şablon #4640 uyarlaması)',
  nodes,
  connections,
  active: false,
  settings: { executionOrder: 'v1', timezone: 'Europe/Istanbul', saveDataErrorExecution: 'all' },
  pinData: {},
  meta: { templateCredsSetupCompleted: false },
  tags: [],
};

const hedef = path.join(KOK, 'workflow.json');
fs.writeFileSync(hedef, `${JSON.stringify(workflow, null, 2)}\n`);
console.log(`workflow.json yazıldı: ${nodes.length} düğüm → ${path.relative(process.cwd(), hedef)}`);

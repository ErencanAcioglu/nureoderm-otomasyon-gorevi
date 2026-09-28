'use strict';

// workflow.json yapısal doğrulaması: n8n'e import edilebilirlik ve brief'teki zorunlu adımlar.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { WORKFLOW, KOK, dugum } = require('./n8n-kum-havuzu');

const cikislar = (ad) => (WORKFLOW.connections[ad]?.main || []).map((c) => (c || []).map((h) => h.node));

test('temel yapı: benzersiz ad ve id, geçerli bağlantılar', () => {
  const adlar = WORKFLOW.nodes.map((n) => n.name);
  assert.equal(new Set(adlar).size, adlar.length, 'düğüm adları benzersiz olmalı');
  assert.equal(new Set(WORKFLOW.nodes.map((n) => n.id)).size, adlar.length, 'id benzersiz olmalı');
  for (const n of WORKFLOW.nodes) {
    assert.match(n.type, /^n8n-nodes-base\./);
    assert.equal(typeof n.typeVersion, 'number');
    assert.ok(Array.isArray(n.position) && n.position.length === 2);
  }
  for (const [kaynak, { main }] of Object.entries(WORKFLOW.connections)) {
    assert.ok(adlar.includes(kaynak), `bağlantı kaynağı yok: ${kaynak}`);
    for (const hedef of main.flat()) assert.ok(adlar.includes(hedef.node), `bağlantı hedefi yok: ${hedef.node}`);
  }
  assert.equal(WORKFLOW.settings.executionOrder, 'v1');
});

test('1) zamanlanmış tetikleyici: her gün 09:00 (Europe/Istanbul)', () => {
  const t = dugum('Her Gün 09:00');
  assert.equal(t.type, 'n8n-nodes-base.scheduleTrigger');
  assert.equal(t.parameters.rule.interval[0].expression, '0 9 * * *');
  assert.equal(WORKFLOW.settings.timezone, 'Europe/Istanbul');
});

test('2) sayfalama: page=$pageCount+1, bitiş koşulu, en fazla 50 istek', () => {
  const h = dugum('Laptop Sayfalarını Çek (Sayfalama)');
  const p = h.parameters.options.pagination.pagination;
  assert.equal(p.paginationMode, 'updateAParameterInEachRequest');
  assert.deepEqual(p.parameters.parameters[0], { type: 'qs', name: 'page', value: '={{ $pageCount + 1 }}' });
  assert.equal(p.paginationCompleteWhen, 'other');
  assert.equal(p.limitPagesFetched, true);
  assert.equal(p.maxRequests, 50);
  assert.equal(h.parameters.options.response.response.outputPropertyName, 'html');
});

test('3) fiyat temizleme brief\'teki ifadeyle yapılıyor ve scraped_at ekleniyor', () => {
  const kod = dugum('Ürünleri Ayrıştır ve Temizle').parameters.jsCode;
  assert.ok(kod.includes("parseFloat(String(ham).replace(/[^0-9.]/g, ''))"));
  assert.ok(kod.includes('scraped_at'));
});

test('3b) tablo: fiyat_gecmisi (append, tarih damgalı) + son_durum (urun_id ile upsert)', () => {
  const g = dugum('Fiyat Geçmişine Yaz (fiyat_gecmisi)');
  assert.equal(g.parameters.operation, 'append');
  assert.ok('scraped_at' in g.parameters.columns.value);
  const s = dugum('Son Durumu Güncelle (son_durum)');
  assert.equal(s.parameters.operation, 'appendOrUpdate');
  assert.deepEqual(s.parameters.columns.matchingColumns, ['urun_id']);
});

test('4) değişiklik tespiti → Switch 3 dal → mesaj → Telegram', () => {
  assert.deepEqual(cikislar('Değişiklik Tespiti')[0].sort(),
    ['Değişim Türüne Göre Ayır', 'Fiyat Geçmişine Yaz (fiyat_gecmisi)', 'Son Durumu Güncelle (son_durum)'].sort());
  const sw = dugum('Değişim Türüne Göre Ayır');
  assert.deepEqual(sw.parameters.rules.values.map((r) => r.outputKey), ['İndirim Alarmı', 'Fiyat Artışı', 'Yeni Ürün']);
  assert.deepEqual(cikislar('Değişim Türüne Göre Ayır'),
    [['İndirim Alarmı Mesajı'], ['Fiyat Artışı Mesajı'], ['Yeni Ürün Mesajı']]);
  for (const ad of ['İndirim Alarmı Mesajı', 'Fiyat Artışı Mesajı', 'Yeni Ürün Mesajı']) {
    assert.deepEqual(cikislar(ad), [['Telegram Bildirimi']]);
    assert.ok(!dugum(ad).parameters.jsCode.includes('__TUR__'), `${ad}: TUR yerleştirilmemiş`);
  }
});

test('5) hata dalı: HTTP hata çıkışı, 0 ürün, Sheets okuma hatası ve Error Trigger aynı acil uyarıya bağlı', () => {
  const http = dugum('Laptop Sayfalarını Çek (Sayfalama)');
  assert.equal(http.onError, 'continueErrorOutput');
  assert.equal(http.retryOnFail, true);
  assert.deepEqual(cikislar('Laptop Sayfalarını Çek (Sayfalama)')[1], ['Hata Mesajı Hazırla']);
  assert.deepEqual(cikislar('Veri Geçerli mi?')[1], ['Hata Mesajı Hazırla']);
  assert.deepEqual(cikislar('Önceki Durumu Oku (son_durum)')[1], ['Hata Mesajı Hazırla']);
  assert.equal(dugum('Hata Yakalayıcı (Error Trigger)').type, 'n8n-nodes-base.errorTrigger');
  assert.deepEqual(cikislar('Hata Yakalayıcı (Error Trigger)')[0], ['Hata Mesajı Hazırla']);
  assert.deepEqual(cikislar('Hata Mesajı Hazırla')[0], ['Acil Uyarı (Telegram)']);
});

test('gömülü kod kod/*.js ile senkron (workflow.json elle düzenlenmemiş)', () => {
  const oku = (ad) => fs.readFileSync(path.join(KOK, 'kod', ad), 'utf8');
  assert.equal(dugum('Ürünleri Ayrıştır ve Temizle').parameters.jsCode, oku('ayristir.js'));
  assert.equal(dugum('Değişiklik Tespiti').parameters.jsCode, oku('degisiklik.js'));
  assert.equal(dugum('Hata Mesajı Hazırla').parameters.jsCode, oku('hata.js'));
  assert.equal(dugum('Yeni Ürün Mesajı').parameters.jsCode,
    oku('bildirim.js').replace("const TUR = '__TUR__';", "const TUR = 'yeni';"));
});

test('workflow.json içinde gizli bilgi yok', () => {
  const metin = JSON.stringify(WORKFLOW);
  assert.ok(!/"credentials"/.test(metin), 'kimlik bilgisi gömülmemeli');
  assert.ok(!/\d{9,10}:[A-Za-z0-9_-]{35}/.test(metin), 'Telegram bot token benzeri değer olmamalı');
});

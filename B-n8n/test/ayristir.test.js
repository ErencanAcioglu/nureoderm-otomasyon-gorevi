'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { kodCalistir, sayfalamaBittiMi, fixture } = require('./n8n-kum-havuzu');

const AYRISTIR = 'Ürünleri Ayrıştır ve Temizle';
const sayfa1 = fixture('sayfa-01.html');
const sayfa20 = fixture('sayfa-20.html');
const bos = fixture('sayfa-21-bos.html');

const ayristir = (...htmller) => kodCalistir(AYRISTIR, { girdi: htmller.map((html) => ({ html })) })[0];

test('gerçek sayfa 1: 6 ürün, alanlar eksiksiz', () => {
  const s = ayristir(sayfa1);
  assert.equal(s.urun_sayisi, 6);
  assert.equal(s.beklenen_urun, 117);
  const u = s.urunler[0];
  assert.equal(u.ad, 'Packard 255 G2');
  assert.equal(u.urun_id, 31);
  assert.equal(u.url, 'https://webscraper.io/test-sites/e-commerce/static/product/31');
  assert.equal(u.aciklama, '15.6", AMD E2-3800 1.3GHz, 4GB, 500GB, Windows 8.1');
  assert.equal(u.yorum_sayisi, 2);
  assert.equal(u.puan, 2);
  assert.equal(u.sayfa, 1);
});

test('fiyat tip güvenliği: "$416.99" → 416.99 (number), tüm ürünlerde', () => {
  const s = ayristir(sayfa1, sayfa20);
  assert.equal(s.urunler[0].fiyat_ham, '$416.99');
  assert.equal(s.urunler[0].fiyat, 416.99);
  for (const u of s.urunler) {
    assert.equal(typeof u.fiyat, 'number');
    assert.ok(Number.isFinite(u.fiyat) && u.fiyat > 0, `${u.ad}: ${u.fiyat}`);
    assert.equal(typeof u.yorum_sayisi, 'number');
    assert.ok(!Number.isNaN(Date.parse(u.scraped_at)), 'scraped_at ISO tarih olmalı');
  }
});

test('boş sayfa (page=21) 0 ürün döner, çökmez', () => {
  const s = ayristir(bos);
  assert.equal(s.urun_sayisi, 0);
  assert.equal(s.veri_gecerli, false);
  assert.match(s.hata_nedeni, /Hiç ürün/);
});

test('hiç sayfa gelmezse veri_gecerli=false', () => {
  const s = kodCalistir(AYRISTIR, { girdi: [] })[0];
  assert.equal(s.veri_gecerli, false);
});

test('eksik veri: 117 ürün bildiren sitede yalnızca 9 ürün → hata dalı', () => {
  const s = ayristir(sayfa1, sayfa20);
  assert.equal(s.urun_sayisi, 9);
  assert.equal(s.veri_gecerli, false);
  assert.match(s.hata_nedeni, /Eksik veri/);
});

test('aynı sayfa iki kez gelirse ürünler tekrarlanmaz', () => {
  const s = ayristir(sayfa1, sayfa1);
  assert.equal(s.urun_sayisi, 6);
  assert.equal(s.tekrar_eden, 6);
  assert.equal(s.urunler[0].sayfa, 1);
});

test('fiyatı bozuk kart atlanır ve sayılır, NaN asla çıkmaz', () => {
  const bozuk = sayfa1.replace('$416.99', 'Fiyat sorunuz');
  const s = ayristir(bozuk);
  assert.equal(s.urun_sayisi, 5);
  assert.equal(s.gecersiz_fiyat, 1);
  assert.match(s.uyarilar[0], /Packard 255 G2/);
});

test('HTML varlıkları çözülür (&quot; → ")', () => {
  const s = ayristir(sayfa1);
  assert.ok(s.urunler.every((u) => !/&quot;|&amp;/.test(u.aciklama)));
});

test('sayfalama bitiş ifadesi: sayfa 1 devam, son sayfa (20) ve boş sayfa (21) dur', () => {
  const bitti = sayfalamaBittiMi();
  assert.equal(bitti({ body: sayfa1 }), false);
  assert.equal(bitti({ body: sayfa20 }), true);  // "next" bağlantısı yok
  assert.equal(bitti({ body: bos }), true);      // ürün kartı yok
  assert.equal(bitti({ body: '' }), true);
  assert.equal(bitti({ body: undefined }), true);
});

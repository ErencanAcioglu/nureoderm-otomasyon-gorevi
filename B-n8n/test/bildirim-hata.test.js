'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { kodCalistir } = require('./n8n-kum-havuzu');

const zaman = '2026-09-28T06:00:00.000Z';
const urun = (id, fiyat, ek = {}) => ({
  urun_id: id, ad: `Laptop ${id}`, aciklama: '15.6", 8GB', fiyat, url: `https://x/product/${id}`,
  scraped_at: zaman, ilk_calisma: false, ...ek,
});

test('indirim dalı: tek mesaj, önceki → yeni fiyat ve yüzde', () => {
  const [m] = kodCalistir('İndirim Alarmı Mesajı', {
    girdi: [urun(31, 399.99, { onceki_fiyat: 416.99, fark_yuzde: -4.08 })],
  });
  assert.equal(m.tur, 'indirim');
  assert.match(m.mesaj, /^📉 İndirim Alarmı — 1 ürün/);
  assert.match(m.mesaj, /Laptop 31 \(#31\): \$416\.99 → \$399\.99 \(-4\.08%\)/);
});

test('artış dalı: + işaretli yüzde', () => {
  const [m] = kodCalistir('Fiyat Artışı Mesajı', {
    girdi: [urun(5, 110, { onceki_fiyat: 100, fark_yuzde: 10 })],
  });
  assert.match(m.mesaj, /^📈 Fiyat Artışı/);
  assert.match(m.mesaj, /\(\+10%\)/);
});

test('yeni ürün dalı: ilk çalışmada liste yerine tek özet satırı (117 mesajlık spam yok)', () => {
  const girdi = Array.from({ length: 117 }, (_, i) => urun(i + 1, 100 + i, { ilk_calisma: true }));
  const sonuc = kodCalistir('Yeni Ürün Mesajı', { girdi });
  assert.equal(sonuc.length, 1);
  assert.match(sonuc[0].mesaj, /İlk çalışma: 117 ürün referans fiyat olarak kaydedildi/);
});

test('çok sayıda değişiklikte liste kısaltılır ve mesaj Telegram sınırını aşmaz', () => {
  const girdi = Array.from({ length: 60 }, (_, i) => urun(i + 1, 90, { onceki_fiyat: 100, fark_yuzde: -10 }));
  const [m] = kodCalistir('İndirim Alarmı Mesajı', { girdi });
  assert.match(m.mesaj, /… ve 45 ürün daha/);
  assert.ok(m.mesaj.length <= 4000);
});

test('boş dal hiçbir mesaj üretmez', () => {
  assert.deepEqual(kodCalistir('Fiyat Artışı Mesajı', { girdi: [] }), []);
});

test('hata dalı: HTTP hata çıkışı', () => {
  const [m] = kodCalistir('Hata Mesajı Hazırla', {
    girdi: [{ error: { message: 'Service unavailable', httpCode: '503' } }],
  });
  assert.equal(m.kaynak, 'Erişim hatası');
  assert.match(m.mesaj, /🚨 ACİL/);
  assert.match(m.mesaj, /HTTP 503 — Service unavailable/);
  assert.match(m.mesaj, /tabloya YAZILMADI/);
});

test('hata dalı: 0 ürün / eksik veri', () => {
  const [m] = kodCalistir('Hata Mesajı Hazırla', {
    girdi: [{ veri_gecerli: false, hata_nedeni: 'Hiç ürün ayrıştırılamadı', sayfa_sayisi: 1, urun_sayisi: 0, beklenen_urun: null }],
  });
  assert.equal(m.kaynak, 'Veri doğrulama hatası');
  assert.match(m.mesaj, /Taranan sayfa: 1 · Ayrıştırılan ürün: 0/);
});

test('hata dalı: Error Trigger çıktısı', () => {
  const [m] = kodCalistir('Hata Mesajı Hazırla', {
    girdi: [{ execution: { id: '7', url: 'https://n8n/e/7', lastNodeExecuted: 'Değişiklik Tespiti', error: { message: 'boom' } }, workflow: { name: 'x' } }],
  });
  assert.equal(m.kaynak, 'Beklenmeyen akış hatası');
  assert.match(m.mesaj, /Değişiklik Tespiti: boom/);
  assert.match(m.mesaj, /Çalışma kaydı: https:\/\/n8n\/e\/7/);
});

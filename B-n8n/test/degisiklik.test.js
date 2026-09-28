'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { kodCalistir, fixture } = require('./n8n-kum-havuzu');

const AYRISTIR = 'Ürünleri Ayrıştır ve Temizle';
const DEGISIKLIK = 'Değişiklik Tespiti';

const bugun = kodCalistir(AYRISTIR, { girdi: [{ html: fixture('sayfa-01.html') }] })[0];
const tespit = (oncekiSatirlar) => kodCalistir(DEGISIKLIK, {
  girdi: oncekiSatirlar, dugumler: { [AYRISTIR]: [bugun] },
});
const tur = (sonuc) => Object.fromEntries(sonuc.map((u) => [u.urun_id, u.degisim]));

// Google Sheets değerleri metin olarak dönebilir → testte bilerek string veriyoruz.
const sheetSatiri = (u, fiyat = u.fiyat) => ({ row_number: 2, urun_id: String(u.urun_id), ad: u.ad, fiyat: String(fiyat) });

test('ilk çalışma (boş tablo → tek boş item): tüm ürünler yeni, ilk_calisma=true', () => {
  const sonuc = tespit([{}]);
  assert.equal(sonuc.length, 6);
  assert.ok(sonuc.every((u) => u.degisim === 'yeni' && u.ilk_calisma === true));
});

test('indirim / artış / değişmedi / yeni doğru ayrılır', () => {
  const [a, b, c, d, e] = bugun.urunler;
  const sonuc = tespit([
    sheetSatiri(a, a.fiyat + 20),   // bugün daha ucuz → indirim
    sheetSatiri(b, b.fiyat - 10),   // bugün daha pahalı → artış
    sheetSatiri(c),                 // aynı
    sheetSatiri(d),
    sheetSatiri(e),
    // 6. ürün önceki tabloda yok → yeni
  ]);
  const t = tur(sonuc);
  assert.equal(t[a.urun_id], 'indirim');
  assert.equal(t[b.urun_id], 'artis');
  assert.equal(t[c.urun_id], 'degismedi');
  assert.equal(t[bugun.urunler[5].urun_id], 'yeni');
  const indirim = sonuc.find((u) => u.urun_id === a.urun_id);
  assert.equal(indirim.onceki_fiyat, a.fiyat + 20);
  assert.equal(indirim.fark, -20);
  assert.ok(indirim.fark_yuzde < 0);
  assert.equal(indirim.ilk_calisma, false);
});

test('kayan nokta gürültüsü sahte değişiklik üretmez (416.99 vs "416.990000001")', () => {
  const [a] = bugun.urunler;
  const sonuc = tespit([sheetSatiri(a, '416.990000001')]);
  assert.equal(sonuc.find((u) => u.urun_id === a.urun_id).degisim, 'degismedi');
});

test('eşleştirme ada göre değil kimliğe göre: aynı adlı iki farklı ürün karışmaz', () => {
  const [a] = bugun.urunler;
  // Önceki tabloda AYNI ADLI ama farklı kimlikli bir ürün var (sitede 8 farklı "Dell Latitude 5480" gibi).
  const sonuc = tespit([{ urun_id: '999', ad: a.ad, fiyat: '1.00' }]);
  assert.equal(sonuc.find((u) => u.urun_id === a.urun_id).degisim, 'yeni');
});

test('bozuk önceki satırlar yok sayılır', () => {
  const [a] = bugun.urunler;
  const sonuc = tespit([{ urun_id: 'abc', fiyat: '10' }, { urun_id: String(a.urun_id), fiyat: '' }, {}]);
  assert.ok(sonuc.every((u) => u.degisim === 'yeni'));
});

#!/usr/bin/env node
// Canlı uçtan uca simülasyon (n8n olmadan): gerçek siteyi workflow.json'daki sayfalama kurallarıyla
// gezer, gömülü Code düğümlerini sırasıyla çalıştırır ve "ikinci gün" senaryosunda bildirimleri üretir.
//
// Kullanım: node B-n8n/test/canli-kazima.js

'use strict';

const { dugum, kodCalistir, sayfalamaBittiMi } = require('./n8n-kum-havuzu');

async function main() {
  const http = dugum('Laptop Sayfalarını Çek (Sayfalama)');
  const { maxRequests, requestInterval } = http.parameters.options.pagination.pagination;
  const bitti = sayfalamaBittiMi();

  // --- 1) HTTP Request + sayfalama (n8n'in $pageCount davranışını taklit eder)
  const sayfalar = [];
  for (let pageCount = 0; pageCount < maxRequests; pageCount++) {
    const url = `${http.parameters.url}?page=${pageCount + 1}`;
    const yanit = await fetch(url, { headers: { 'User-Agent': 'nureoderm-fiyat-takip/1.0 (+test)' } });
    if (!yanit.ok) throw new Error(`HTTP ${yanit.status}: ${url}`);
    const body = await yanit.text();
    sayfalar.push({ html: body });
    if (bitti({ body })) break;
    await new Promise((r) => setTimeout(r, requestInterval));
  }
  console.log(`Sayfalama: ${sayfalar.length} istek (sınır ${maxRequests})`);

  // --- 2) Ayrıştır ve temizle
  const ozet = kodCalistir('Ürünleri Ayrıştır ve Temizle', { girdi: sayfalar })[0];
  const idler = new Set(ozet.urunler.map((u) => u.urun_id));
  const adlar = new Set(ozet.urunler.map((u) => u.ad));
  console.log(`Ayrıştırılan: ${ozet.urun_sayisi} ürün / site ${ozet.beklenen_urun} bildiriyor · `
    + `benzersiz kimlik ${idler.size} · benzersiz ad ${adlar.size} · geçersiz ${ozet.gecersiz_fiyat} · `
    + `tekrar ${ozet.tekrar_eden} · veri_gecerli=${ozet.veri_gecerli}`);
  console.log('Tip kontrolü: tüm fiyatlar number →',
    ozet.urunler.every((u) => typeof u.fiyat === 'number' && Number.isFinite(u.fiyat)));
  console.log('Örnek:', JSON.stringify(ozet.urunler[0]));

  // --- 3) Gün 1: tablo boş → ilk çalışma
  const gun1 = kodCalistir('Değişiklik Tespiti', { girdi: [{}], dugumler: { 'Ürünleri Ayrıştır ve Temizle': [ozet] } });
  const yeni1 = gun1.filter((u) => u.degisim === 'yeni');
  console.log('\n=== GÜN 1 (boş tablo) ===');
  console.log(kodCalistir('Yeni Ürün Mesajı', { girdi: yeni1 })[0].mesaj);

  // --- 4) Gün 2: dünkü tabloda 3 ürünün fiyatı farklıydı, 1 ürün hiç yoktu
  const [a, b, c, d] = ozet.urunler;
  const dunku = ozet.urunler
    .filter((u) => u.urun_id !== d.urun_id)
    .map((u) => ({ urun_id: String(u.urun_id), ad: u.ad, fiyat: String(u.fiyat) }));
  const degistir = (u, fiyat) => { dunku.find((s) => s.urun_id === String(u.urun_id)).fiyat = String(fiyat); };
  degistir(a, (a.fiyat + 50).toFixed(2)); // bugün daha ucuz → indirim
  degistir(b, (b.fiyat + 12.5).toFixed(2));
  degistir(c, (c.fiyat - 30).toFixed(2)); // bugün daha pahalı → artış
  const gun2 = kodCalistir('Değişiklik Tespiti', { girdi: dunku, dugumler: { 'Ürünleri Ayrıştır ve Temizle': [ozet] } });
  const say = gun2.reduce((acc, u) => ({ ...acc, [u.degisim]: (acc[u.degisim] || 0) + 1 }), {});
  console.log('\n=== GÜN 2 (3 fiyat değişti, 1 yeni ürün) ===');
  console.log('Değişim dağılımı:', say);
  for (const [tur, ad] of [['indirim', 'İndirim Alarmı Mesajı'], ['artis', 'Fiyat Artışı Mesajı'], ['yeni', 'Yeni Ürün Mesajı']]) {
    const [m] = kodCalistir(ad, { girdi: gun2.filter((u) => u.degisim === tur) });
    if (m) console.log(`\n--- ${ad} ---\n${m.mesaj}`);
  }

  // --- 5) Hata dalı örneği
  const bos = kodCalistir('Ürünleri Ayrıştır ve Temizle', { girdi: [{ html: '<html></html>' }] })[0];
  console.log('\n=== HATA DALI (site boş döndü) ===');
  console.log(kodCalistir('Hata Mesajı Hazırla', { girdi: [bos] })[0].mesaj);

  const basarili = ozet.veri_gecerli && idler.size === ozet.urun_sayisi && ozet.urun_sayisi === ozet.beklenen_urun;
  console.log(`\nSONUÇ: ${basarili ? 'BAŞARILI' : 'BAŞARISIZ'}`);
  process.exitCode = basarili ? 0 : 1;
}

main().catch((hata) => { console.error('Canlı test hatası:', hata.message); process.exitCode = 1; });

// n8n Code düğümü: "Ürünleri Ayrıştır ve Temizle" (Run Once for All Items)
// Girdi : HTTP Request (sayfalama) çıktısı — her sayfa bir item, HTML metni `html` alanında.
// Çıktı : TEK item — tip güvenli ürün listesi + veri doğrulama istatistikleri.
//         `veri_gecerli: false` ise akış hata dalına gider; tabloya hiçbir şey yazılmaz.

const KAYNAK = 'https://webscraper.io';
const MIN_KAPSAMA = 0.9; // sitenin bildirdiği ürün sayısının en az %90'ı ayrıştırılmalı

const scrapedAt = new Date().toISOString();

function htmlCoz(metin) {
  return String(metin)
    .replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ').trim();
}

function nitelik(etiket, ad) {
  const eslesme = etiket.match(new RegExp(`\\b${ad}="([^"]*)"`));
  return eslesme ? htmlCoz(eslesme[1]) : null;
}

// "$416.99" → 416.99 (number). Sayıya çevrilemeyen fiyat null döner, asla NaN değil.
function fiyatCoz(ham) {
  if (ham === undefined || ham === null) return null;
  const sayi = parseFloat(String(ham).replace(/[^0-9.]/g, ''));
  return Number.isFinite(sayi) ? sayi : null;
}

function kartlariAyristir(html, sayfa) {
  return html.split('class="card thumbnail"').slice(1).map((kart) => {
    const baslikEtiketi = (kart.match(/<a\b[^>]*class="title"[^>]*>/) || [''])[0];
    const yol = nitelik(baslikEtiketi, 'href');
    const fiyatHam = (kart.match(/itemprop="price"[^>]*>([^<]*)</) || [])[1];
    const aciklama = (kart.match(/class="description[^"]*"[^>]*>([\s\S]*?)<\/p>/) || [])[1];
    const yorum = (kart.match(/itemprop="reviewCount"[^>]*>\s*(\d+)/) || kart.match(/(\d+)\s+reviews?/) || [])[1];
    const puan = (kart.match(/data-rating="(\d+)"/) || [])[1];
    const urunId = yol ? (yol.match(/\/product\/(\d+)/) || [])[1] : undefined;
    return {
      urun_id: urunId ? Number(urunId) : null,
      // title niteliği tam adı taşır; bağlantı metni uzun adlarda "..." ile kısaltılabilir.
      ad: nitelik(baslikEtiketi, 'title'),
      aciklama: aciklama ? htmlCoz(aciklama) : null,
      fiyat_ham: fiyatHam ? fiyatHam.trim() : null,
      fiyat: fiyatCoz(fiyatHam),
      yorum_sayisi: yorum !== undefined ? parseInt(yorum, 10) : null,
      puan: puan !== undefined ? parseInt(puan, 10) : null,
      url: yol ? (yol.startsWith('http') ? yol : KAYNAK + yol) : null,
      sayfa,
      scraped_at: scrapedAt,
    };
  });
}

const sayfalar = $input.all().map((item, i) => ({
  sayfa: i + 1,
  html: String(item.json.html ?? item.json.data ?? ''),
}));

let beklenenUrun = null;
const gorulen = new Set();
const urunler = [];
const uyarilar = [];
let gecersizFiyat = 0;
let tekrarEden = 0;

for (const { sayfa, html } of sayfalar) {
  if (beklenenUrun === null) {
    const sayac = html.match(/class="item-count"[^>]*>\s*(\d+)\s+items?/);
    if (sayac) beklenenUrun = Number(sayac[1]);
  }
  for (const urun of kartlariAyristir(html, sayfa)) {
    // Aynı ada sahip farklı ürünler var (ör. 8 farklı "Dell Latitude 5480"); anahtar ürün URL'si.
    const anahtar = urun.url || `${urun.ad}|${urun.aciklama}|${urun.fiyat_ham}`;
    if (gorulen.has(anahtar)) { tekrarEden++; continue; }
    gorulen.add(anahtar);
    if (typeof urun.fiyat !== 'number' || urun.urun_id === null || !urun.ad) {
      gecersizFiyat++;
      uyarilar.push(`Sayfa ${sayfa}: ayrıştırılamayan kart atlandı (ad=${urun.ad}, fiyat=${urun.fiyat_ham})`);
      continue;
    }
    urunler.push(urun);
  }
}

let hataNedeni = null;
if (urunler.length === 0) {
  hataNedeni = 'Hiç ürün ayrıştırılamadı: site boş döndü, açılmadı ya da HTML yapısı değişti.';
} else if (beklenenUrun && urunler.length < Math.floor(beklenenUrun * MIN_KAPSAMA)) {
  hataNedeni = `Eksik veri: site ${beklenenUrun} ürün bildiriyor, yalnızca ${urunler.length} ürün ayrıştırıldı.`;
}
if (beklenenUrun && urunler.length !== beklenenUrun && hataNedeni === null) {
  uyarilar.push(`Site ${beklenenUrun} ürün bildiriyor, ${urunler.length} ürün ayrıştırıldı.`);
}

return [{
  json: {
    run_id: scrapedAt,
    scraped_at: scrapedAt,
    kaynak: `${KAYNAK}/test-sites/e-commerce/static/computers/laptops`,
    sayfa_sayisi: sayfalar.length,
    beklenen_urun: beklenenUrun,
    urun_sayisi: urunler.length,
    gecersiz_fiyat: gecersizFiyat,
    tekrar_eden: tekrarEden,
    veri_gecerli: hataNedeni === null,
    hata_nedeni: hataNedeni,
    uyarilar,
    urunler,
  },
}];

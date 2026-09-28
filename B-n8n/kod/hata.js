// n8n Code düğümü: "Hata Mesajı Hazırla" (Run Once for All Items)
// Dört kaynaktan beslenir; hiçbiri sessizce "başarılı" bitmez:
//   1. HTTP Request hata çıkışı (4xx/5xx, zaman aşımı, DNS — 3 deneme sonrası)
//   2. "Veri Geçerli mi?" false dalı (0 ürün ya da eksik veri)
//   3. Google Sheets okuma hatası (önceki durum okunamadı)
//   4. Error Trigger (akışın herhangi bir yerinde beklenmeyen çöküş)

const girdi = $input.first().json;
const hataMetni = (e) => (typeof e === 'string' ? e : e?.message || e?.description || JSON.stringify(e));

let kaynak;
let neden;
if (girdi.execution && girdi.execution.error) {
  kaynak = 'Beklenmeyen akış hatası';
  neden = `${girdi.execution.lastNodeExecuted || 'bilinmeyen düğüm'}: ${hataMetni(girdi.execution.error)}`;
} else if (girdi.error) {
  kaynak = 'Erişim hatası';
  const kod = girdi.error.httpCode || girdi.error.status || girdi.error.statusCode;
  neden = `${kod ? `HTTP ${kod} — ` : ''}${hataMetni(girdi.error)}`;
} else if (girdi.veri_gecerli === false) {
  kaynak = 'Veri doğrulama hatası';
  neden = girdi.hata_nedeni;
} else {
  kaynak = 'Bilinmeyen hata';
  neden = 'Hata dalına tanımsız bir girdi ulaştı.';
}

const satirlar = [
  '🚨 ACİL: Laptop fiyat takip akışı başarısız',
  '',
  `Tür: ${kaynak}`,
  `Neden: ${neden}`,
  `Zaman: ${new Date().toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}`,
  'Kaynak: https://webscraper.io/test-sites/e-commerce/static/computers/laptops',
];
if (girdi.sayfa_sayisi !== undefined) {
  satirlar.push(`Taranan sayfa: ${girdi.sayfa_sayisi} · Ayrıştırılan ürün: ${girdi.urun_sayisi}`
    + (girdi.beklenen_urun ? ` / beklenen ${girdi.beklenen_urun}` : ''));
}
satirlar.push('');
satirlar.push(kaynak === 'Beklenmeyen akış hatası'
  ? 'Çalışma yarıda kaldı; fiyat tablosunu ve bildirimleri kontrol edin.'
  : 'Önceki fiyat tablosu korunuyor: bugünkü veri tabloya YAZILMADI, değişiklik bildirimi gönderilmedi.');
if (girdi.execution && girdi.execution.url) satirlar.push(`Çalışma kaydı: ${girdi.execution.url}`);

return [{ json: { seviye: 'kritik', kaynak, neden, mesaj: satirlar.join('\n') } }];

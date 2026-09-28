// n8n Code düğümü: Switch dalı için bildirim metni (Run Once for All Items)
// Aynı kod üç dalda kullanılır; TUR değeri workflow.json üretilirken yerleştirilir.
// Her dal TEK mesaj üretir (ürün başına mesaj yok → ilk çalışmada 117 mesajlık spam olmaz).

const TUR = '__TUR__'; // indirim | artis | yeni
const BASLIKLAR = { indirim: '📉 İndirim Alarmı', artis: '📈 Fiyat Artışı', yeni: '🆕 Yeni Ürün' };
const EN_FAZLA_SATIR = 15;
const MESAJ_SINIRI = 4000; // Telegram tek mesaj sınırı 4096 karakter

const urunler = $input.all().map((item) => item.json);
if (urunler.length === 0) return [];

const usd = (deger) => `$${Number(deger).toFixed(2)}`;
const isaretli = (deger) => `${deger > 0 ? '+' : ''}${deger}%`;
const zaman = new Date(urunler[0].scraped_at).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' });

let satirlar;
if (TUR === 'yeni' && urunler[0].ilk_calisma) {
  satirlar = [
    `İlk çalışma: ${urunler.length} ürün referans fiyat olarak kaydedildi.`,
    'Bundan sonraki çalışmalarda yalnızca fiyat değişiklikleri ve yeni ürünler bildirilecek.',
  ];
} else {
  const sirali = [...urunler].sort((a, b) => (TUR === 'yeni'
    ? a.fiyat - b.fiyat
    : Math.abs(b.fark_yuzde ?? 0) - Math.abs(a.fark_yuzde ?? 0)));
  satirlar = sirali.slice(0, EN_FAZLA_SATIR).map((u) => (TUR === 'yeni'
    ? `• ${u.ad} (#${u.urun_id}) — ${usd(u.fiyat)}\n  ${u.aciklama ?? ''}\n  ${u.url}`
    : `• ${u.ad} (#${u.urun_id}): ${usd(u.onceki_fiyat)} → ${usd(u.fiyat)} (${isaretli(u.fark_yuzde)})\n  ${u.url}`));
  if (sirali.length > EN_FAZLA_SATIR) {
    satirlar.push(`… ve ${sirali.length - EN_FAZLA_SATIR} ürün daha (tam liste: Google Sheets › fiyat_gecmisi)`);
  }
}

let mesaj = `${BASLIKLAR[TUR]} — ${urunler.length} ürün\n${zaman}\n\n${satirlar.join('\n')}`;
if (mesaj.length > MESAJ_SINIRI) mesaj = `${mesaj.slice(0, MESAJ_SINIRI - 1)}…`;

return [{ json: { tur: TUR, adet: urunler.length, mesaj } }];

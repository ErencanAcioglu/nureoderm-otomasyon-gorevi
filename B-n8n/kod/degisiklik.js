// n8n Code düğümü: "Değişiklik Tespiti" (Run Once for All Items)
// Girdi ($input) : Google Sheets "son_durum" satırları = bir önceki çalışmanın fiyatları.
//                  Tablo boşsa (ilk çalışma) tek bir boş item gelir (alwaysOutputData).
// Bugünkü veri   : "Ürünleri Ayrıştır ve Temizle" düğümünün çıktısı.
// Çıktı          : Bugün görülen her ürün için bir item; `degisim` ∈ indirim | artis | yeni | degismedi.
//
// Karşılaştırma anahtarı ürün ADI DEĞİL, sitedeki ürün kimliğidir (/product/{id}):
// sitede 117 ürün ama yalnızca 88 farklı ad var (ör. 8 farklı "Dell Latitude 5480").
// Ada göre eşleştirme bu ürünleri birbirine karıştırıp sahte fiyat alarmı üretirdi.

const bugun = $('Ürünleri Ayrıştır ve Temizle').first().json;

// Kayan nokta hatasına karşı kuruş (cent) cinsinden tam sayı karşılaştırması.
const kurus = (deger) => Math.round(Number(deger) * 100);

// Sheets değerleri metin dönebilir → sayıya zorla. Boş hücre NaN sayılır:
// Number('') === 0 olduğundan boş fiyat hücresi aksi halde "$0 → $416.99" sahte artış alarmı üretirdi.
const sayi = (deger) => (deger === null || deger === undefined || String(deger).trim() === ''
  ? NaN : Number(deger));

const onceki = new Map();
for (const { json: satir } of $input.all()) {
  const id = sayi(satir.urun_id);
  const fiyat = sayi(satir.fiyat);
  if (Number.isInteger(id) && id > 0 && Number.isFinite(fiyat) && fiyat > 0) {
    onceki.set(id, { ...satir, fiyat });
  }
}
const ilkCalisma = onceki.size === 0;

return bugun.urunler.map((urun) => {
  const eski = onceki.get(urun.urun_id);
  let degisim = 'yeni';
  let oncekiFiyat = null;
  let fark = null;
  let farkYuzde = null;
  if (eski) {
    oncekiFiyat = eski.fiyat;
    const farkKurus = kurus(urun.fiyat) - kurus(eski.fiyat);
    fark = farkKurus / 100;
    farkYuzde = oncekiFiyat > 0 ? Math.round((farkKurus / kurus(oncekiFiyat)) * 10000) / 100 : null;
    degisim = farkKurus < 0 ? 'indirim' : farkKurus > 0 ? 'artis' : 'degismedi';
  }
  return {
    json: {
      ...urun,
      degisim,
      onceki_fiyat: oncekiFiyat,
      fark,
      fark_yuzde: farkYuzde,
      ilk_calisma: ilkCalisma,
      run_id: bugun.run_id,
    },
  };
});

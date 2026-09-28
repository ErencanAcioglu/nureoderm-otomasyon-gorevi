import json
import unittest
from pathlib import Path

from otomasyon.isleyici import (
    DEVIR_SABLONU,
    GUVENLIK_UYARISI,
    ONAYLI_SABLONLAR,
    SIPARIS_BULUNAMADI_SABLONU,
    YASAKLI_IFADELER,
    PolitikaIhlali,
    Talep,
    isle,
    politika_denetimi,
)

from tests.sahte_istemci import SahteIstemci, SahteUrunIstemcisi

MESAJLAR = json.loads((Path(__file__).resolve().parents[1] / "mesajlar.json").read_text(encoding="utf-8"))


def _kayit(mesaj, id_=100, musteri_id=1):
    return {"id": id_, "kanal": "whatsapp", "musteri_id": musteri_id, "mesaj": mesaj}


def _isle(kayit, istemci=None):
    return isle(kayit, istemci or SahteIstemci(), SahteUrunIstemcisi())


class HassasKonuTesti(unittest.TestCase):
    def test_hassas_konular_her_zaman_devredilir(self):
        for mesaj in ("Kremi sürdüm, yüzüm kızardı ve kaşınıyor.", "Ürün kırık geldi, iade istiyorum.",
                      "Serum sonrası alerji oldu, iade de istiyorum."):
            with self.subTest(mesaj=mesaj):
                t = _isle(_kayit(mesaj))
                self.assertTrue(t.devret)
                self.assertEqual(t.cevap_taslagi, ONAYLI_SABLONLAR["tr"][t.konu])

    def test_onayli_sablonlarda_oneri_teshis_yok(self):
        for dil, sablonlar in ONAYLI_SABLONLAR.items():
            for konu, sablon in sablonlar.items():
                for ifade in YASAKLI_IFADELER:
                    self.assertNotIn(ifade, sablon.lower(), f"{dil}/{konu}: {ifade!r}")

    def test_veri_seti_4_ve_5(self):
        for idx in (3, 4):
            t = _isle(MESAJLAR[idx])
            self.assertTrue(t.devret)
            self.assertIn("Hassas konu", t.to_dict()["not"])

    def test_istenmeyen_etki_kozmetovijilans_notu(self):
        self.assertIn("kozmetovijilans", _isle(MESAJLAR[3]).to_dict()["not"])


class PolitikaDenetimiTesti(unittest.TestCase):
    def test_devredilmeyen_hassas_konu_reddedilir(self):
        with self.assertRaises(PolitikaIhlali):
            politika_denetimi(Talep(1, "istenmeyen-etki", False, ONAYLI_SABLONLAR["tr"]["istenmeyen-etki"]))

    def test_onaysiz_hassas_taslak_reddedilir(self):
        with self.assertRaises(PolitikaIhlali):
            politika_denetimi(Talep(1, "istenmeyen-etki", True, "Aloe vera içeren bir krem öneririz."))

    def test_bilinmeyen_konu_reddedilir(self):
        with self.assertRaises(PolitikaIhlali):
            politika_denetimi(Talep(1, "kampanya", False, None))


class OtomatikDevirTesti(unittest.TestCase):
    def test_dusuk_guven_devredilir(self):
        t = _isle(_kayit("Merhaba"))
        self.assertTrue(t.devret)
        self.assertEqual(t.cevap_taslagi, DEVIR_SABLONU)
        self.assertIn("Düşük Güven Skoru", t.to_dict()["not"])

    def test_coklu_niyet_devredilir(self):
        t = _isle(MESAJLAR[7])  # mesaj 8: fiyat + sipariş
        self.assertTrue(t.devret)
        self.assertIn("Çoklu Niyet: siparis-durumu + fiyat", t.to_dict()["not"])

    def test_zayif_urun_adi_coklu_niyet_sayilmaz(self):
        t = _isle(MESAJLAR[9])  # mesaj 10: "Nemlendirici krem ne kadar?"
        self.assertFalse(t.devret)
        self.assertNotIn("Çoklu Niyet", t.to_dict()["not"])

    def test_spam_devredilmez_yanitlanmaz(self):
        t = _isle(MESAJLAR[6])
        self.assertFalse(t.devret)
        self.assertIsNone(t.cevap_taslagi)


class SiparisGuvenligiTesti(unittest.TestCase):
    def test_baska_musterinin_siparisi_engellenir(self):
        t = _isle(MESAJLAR[0])  # mesaj 1: musteri 7, sipariş 12 (userId 12)
        self.assertTrue(t.devret)
        self.assertIn(GUVENLIK_UYARISI, t.to_dict()["not"])

    def test_yetkisiz_sorguda_hicbir_sepet_verisi_sizmaz(self):
        cikti = json.dumps(_isle(MESAJLAR[0]).to_dict(), ensure_ascii=False)
        for sizinti in ("Sportbike", "Rolex", "37767", "37.767", "userId=12", "× "):
            self.assertNotIn(sizinti, cikti)

    def test_yetkisiz_ve_bulunamayan_ayni_metni_alir(self):
        # Numara taraması (enumeration) ile siparişin varlığı anlaşılamamalı.
        yetkisiz = _isle(_kayit("12 numaralı siparişim nerede?", musteri_id=7)).cevap_taslagi
        yok = _isle(_kayit("13 numaralı siparişim nerede?", musteri_id=7)).cevap_taslagi
        self.assertEqual(yetkisiz.replace("12", "N"), yok.replace("13", "N"))

    def test_eslesen_siparis_urun_adet_tutar(self):
        t = _isle(MESAJLAR[1])  # mesaj 2: musteri 5, sipariş 5
        self.assertFalse(t.devret)
        for parca in ("Samsung Galaxy Tab White × 4", "Soft Drinks × 4", "1.467,88 USD"):
            self.assertIn(parca, t.cevap_taslagi)

    def test_ingilizce_hashtag_bicimi(self):
        t = _isle(MESAJLAR[5])  # mesaj 6: "order #3", musteri 3
        self.assertFalse(t.devret)
        self.assertIn("Fish Steak × 1", t.cevap_taslagi)

    def test_bulunamayan_siparis_cokmez_devredilmez(self):
        t = _isle(MESAJLAR[2])  # mesaj 3: 9999
        self.assertFalse(t.devret)
        self.assertEqual(t.cevap_taslagi, SIPARIS_BULUNAMADI_SABLONU.format(no=9999))
        self.assertIn("bulunamadı", t.to_dict()["not"])

    def test_coklu_niyette_sahiplik_yine_kontrol_edilir(self):
        t = _isle(_kayit("Güneş kreminin fiyatı ne kadar? 12 numaralı siparişim ne zaman gelir?",
                         musteri_id=4))
        self.assertTrue(t.devret)
        self.assertIn(GUVENLIK_UYARISI, t.to_dict()["not"])
        self.assertNotIn("Sportbike", json.dumps(t.to_dict(), ensure_ascii=False))

    def test_birden_fazla_sipariste_biri_yetkisizse_hicbiri_paylasilmaz(self):
        t = _isle(_kayit("5 numaralı ve 12 numaralı siparişim nerede?", musteri_id=5))
        self.assertTrue(t.devret)
        cikti = json.dumps(t.to_dict(), ensure_ascii=False)
        self.assertNotIn("Samsung", cikti)
        self.assertNotIn("Sportbike", cikti)

    def test_api_hatasi_devredilir(self):
        t = _isle(_kayit("5 numaralı siparişim nerede?", musteri_id=5), SahteIstemci(hatali={5}))
        self.assertTrue(t.devret)
        self.assertIn("ulaşılamadı", t.to_dict()["not"])

    def test_sipariş_numarasi_yoksa_istenir(self):
        t = _isle(_kayit("Siparişim nerede?"))
        self.assertFalse(t.devret)
        self.assertIn("sipariş numaranızı", t.cevap_taslagi)

    def test_siparis_disi_konularda_api_cagrilmaz(self):
        istemci = SahteIstemci()
        for m in MESAJLAR:
            if m["id"] not in (1, 2, 3, 6, 8):
                _isle(m, istemci)
        self.assertEqual(istemci.cagrilar, [])


class CiktiBicimiTesti(unittest.TestCase):
    def test_talepler_json_alanlari(self):
        for m in MESAJLAR:
            d = _isle(m).to_dict()
            self.assertEqual(set(d), {"id", "konu", "devret", "cevap_taslagi", "not"})
            json.dumps(d, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()

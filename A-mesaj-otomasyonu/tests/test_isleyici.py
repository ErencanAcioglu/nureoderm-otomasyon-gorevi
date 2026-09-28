import json
import unittest
from pathlib import Path

from otomasyon.isleyici import (
    DEVIR_SABLONU,
    ONAYLI_SABLONLAR,
    YASAKLI_IFADELER,
    PolitikaIhlali,
    Talep,
    isle,
    politika_denetimi,
)

MESAJLAR = json.loads((Path(__file__).resolve().parents[1] / "mesajlar.json").read_text(encoding="utf-8"))


def _kayit(mesaj, id_=100, musteri_id=1):
    return {"id": id_, "kanal": "whatsapp", "musteri_id": musteri_id, "mesaj": mesaj}


class HassasKonuTesti(unittest.TestCase):
    def test_hassas_konular_her_zaman_devredilir(self):
        for mesaj in ("Kremi sürdüm, yüzüm kızardı ve kaşınıyor.", "Ürün kırık geldi, iade istiyorum.",
                      "Serum sonrası alerji oldu, iade de istiyorum."):
            with self.subTest(mesaj=mesaj):
                t = isle(_kayit(mesaj))
                self.assertTrue(t.devret)
                self.assertEqual(t.cevap_taslagi, ONAYLI_SABLONLAR[t.konu])

    def test_onayli_sablonlarda_oneri_teshis_yok(self):
        for konu, sablon in ONAYLI_SABLONLAR.items():
            for ifade in YASAKLI_IFADELER:
                self.assertNotIn(ifade, sablon.lower(), f"{konu}: {ifade!r}")

    def test_veri_seti_4_ve_5(self):
        for idx in (3, 4):
            t = isle(MESAJLAR[idx])
            self.assertTrue(t.devret)
            self.assertIn("Hassas konu", t.to_dict()["not"])

    def test_istenmeyen_etki_kozmetovijilans_notu(self):
        self.assertIn("kozmetovijilans", isle(MESAJLAR[3]).to_dict()["not"])


class PolitikaDenetimiTesti(unittest.TestCase):
    def test_devredilmeyen_hassas_konu_reddedilir(self):
        with self.assertRaises(PolitikaIhlali):
            politika_denetimi(Talep(1, "istenmeyen-etki", False, ONAYLI_SABLONLAR["istenmeyen-etki"]))

    def test_onaysiz_hassas_taslak_reddedilir(self):
        with self.assertRaises(PolitikaIhlali):
            politika_denetimi(Talep(1, "istenmeyen-etki", True, "Aloe vera içeren bir krem öneririz."))

    def test_bilinmeyen_konu_reddedilir(self):
        with self.assertRaises(PolitikaIhlali):
            politika_denetimi(Talep(1, "kampanya", False, None))


class OtomatikDevirTesti(unittest.TestCase):
    def test_dusuk_guven_devredilir(self):
        t = isle(_kayit("Merhaba"))
        self.assertTrue(t.devret)
        self.assertEqual(t.cevap_taslagi, DEVIR_SABLONU)
        self.assertIn("Düşük Güven Skoru", t.to_dict()["not"])

    def test_coklu_niyet_devredilir(self):
        t = isle(MESAJLAR[7])  # mesaj 8: fiyat + sipariş
        self.assertTrue(t.devret)
        self.assertIn("Çoklu Niyet: siparis-durumu + fiyat", t.to_dict()["not"])

    def test_zayif_urun_adi_coklu_niyet_sayilmaz(self):
        t = isle(MESAJLAR[9])  # mesaj 10: "Nemlendirici krem ne kadar?"
        self.assertFalse(t.devret)
        self.assertNotIn("Çoklu Niyet", t.to_dict()["not"])

    def test_spam_devredilmez_yanitlanmaz(self):
        t = isle(MESAJLAR[6])
        self.assertFalse(t.devret)
        self.assertIsNone(t.cevap_taslagi)


class CiktiBicimiTesti(unittest.TestCase):
    def test_talepler_json_alanlari(self):
        for m in MESAJLAR:
            d = isle(m).to_dict()
            self.assertEqual(set(d), {"id", "konu", "devret", "cevap_taslagi", "not"})
            json.dumps(d, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()

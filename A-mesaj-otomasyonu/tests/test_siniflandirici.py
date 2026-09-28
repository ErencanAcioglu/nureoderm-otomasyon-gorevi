import json
import unittest
from pathlib import Path

from otomasyon.metin import normalize, siparis_numaralari
from otomasyon.siniflandirici import ETIKET_ESLESME_YOK, ETIKET_SPAM, siniflandir

MESAJLAR = json.loads((Path(__file__).resolve().parents[1] / "mesajlar.json").read_text(encoding="utf-8"))

BEKLENEN_KONULAR = {
    1: "siparis-durumu", 2: "siparis-durumu", 3: "siparis-durumu", 4: "istenmeyen-etki",
    5: "iade-sikayet", 6: "siparis-durumu", 7: "diger", 8: "siparis-durumu", 9: "urun-sorusu",
    10: "fiyat", 11: "urun-sorusu", 12: "diger", 13: "urun-sorusu", 14: "fiyat", 15: "urun-sorusu",
}


class MetinTesti(unittest.TestCase):
    def test_turkce_normalizasyon(self):
        self.assertEqual(normalize("SİPARİŞİM hâlâ, IŞIL!"), "siparisim hala isil")

    def test_url_ayiklanir(self):
        self.assertNotIn("bit", normalize("bakın bit.ly/takip-artir"))

    def test_siparis_numarasi_capali(self):
        self.assertEqual(siparis_numaralari(normalize("12 numaralı siparişim")), (12,))
        self.assertEqual(siparis_numaralari(normalize("where is my order #3?")), (3,))
        self.assertEqual(siparis_numaralari(normalize("sipariş no: 45")), (45,))

    def test_hacim_siparis_numarasi_sayilmaz(self):
        self.assertEqual(siparis_numaralari(normalize("Tonik 200 ml mi?")), ())


class SiniflandiriciTesti(unittest.TestCase):
    def test_veri_seti_konulari(self):
        for m in MESAJLAR:
            with self.subTest(id=m["id"]):
                self.assertEqual(siniflandir(m["mesaj"]).konu, BEKLENEN_KONULAR[m["id"]])

    def test_spam_etiketi(self):
        s = siniflandir(MESAJLAR[6]["mesaj"])
        self.assertEqual((s.konu, s.etiket), ("diger", ETIKET_SPAM))

    def test_istenmeyen_etki_spami_ezer(self):
        s = siniflandir("Yüzümde kaşıntı oldu, bakın: bit.ly/x %100 sizin yüzünüzden")
        self.assertEqual(s.konu, "istenmeyen-etki")

    def test_kasim_kasinti_sayilmaz(self):
        self.assertNotEqual(siniflandir("Kasım ayında kampanya var mı?").konu, "istenmeyen-etki")

    def test_eslesme_yok_dusuk_guven(self):
        s = siniflandir("Merhaba")
        self.assertEqual((s.konu, s.etiket), ("diger", ETIKET_ESLESME_YOK))
        self.assertTrue(s.inceleme_gerekli)

    def test_guven_deterministik_ve_aralikta(self):
        for m in MESAJLAR:
            a, b = siniflandir(m["mesaj"]), siniflandir(m["mesaj"])
            self.assertEqual(a.guven, b.guven)
            self.assertGreaterEqual(a.guven, 0.0)
            self.assertLessEqual(a.guven, 1.0)


if __name__ == "__main__":
    unittest.main()

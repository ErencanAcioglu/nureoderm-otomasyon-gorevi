"""Dil algılama, İngilizce şablonlar, ürün arama (bonus) ve raporlama testleri."""

import json
import re
import unittest
from pathlib import Path

from otomasyon.isleyici import ONAYLI_SABLONLAR, isle
from otomasyon.metin import dil_tespit, normalize
from otomasyon.ozet import html_ozeti, istatistik, terminal_ozeti
from otomasyon.sablonlar import METINLER, tutar_bicimle
from otomasyon.urun_arama import Urun, alakali_mi, arama_sorgulari, urun_ara
from tests.sahte_istemci import SahteIstemci, SahteUrunIstemcisi

MESAJLAR = json.loads((Path(__file__).resolve().parents[1] / "mesajlar.json").read_text(encoding="utf-8"))


def _isle(kayit, urun=None):
    return isle(kayit, SahteIstemci(), urun or SahteUrunIstemcisi())


def _kayit(mesaj, musteri_id=1):
    return {"id": 99, "kanal": "instagram", "musteri_id": musteri_id, "mesaj": mesaj}


class DilTesti(unittest.TestCase):
    def test_veri_setinde_yalnizca_mesaj_6_ingilizce(self):
        ingilizce = [m["id"] for m in MESAJLAR if dil_tespit(m["mesaj"]) == "en"]
        self.assertEqual(ingilizce, [6])

    def test_turkce_karakterli_mesaj_turkce(self):
        self.assertEqual(dil_tespit("Order #3 nerede? Şimdi söyler misiniz"), "tr")

    def test_belirsizlikte_turkce(self):
        for metin in ("Nemlendirici krem ne kadar?", "ok", "#12"):
            self.assertEqual(dil_tespit(metin), "tr")

    def test_iki_dilde_ayni_sablon_anahtarlari(self):
        self.assertEqual(set(METINLER["tr"]), set(METINLER["en"]))


class IngilizceSablonTesti(unittest.TestCase):
    def test_mesaj_6_ingilizce_siparis_taslagi(self):
        t = _isle(MESAJLAR[5])
        self.assertEqual(t.dil, "en")
        self.assertTrue(t.cevap_taslagi.startswith("Hello, your order #3 has been verified. Items:"))
        self.assertIn("Fish Steak × 1", t.cevap_taslagi)
        self.assertIn("Total: 1,794.85 USD", t.cevap_taslagi)

    def test_ingilizce_bulunamayan_ve_yetkisiz_ayni_metin(self):
        yetkisiz = _isle(_kayit("Where is my order #12?", musteri_id=7))
        yok = _isle(_kayit("Where is my order #13?", musteri_id=7))
        self.assertTrue(yetkisiz.devret)
        self.assertEqual(yetkisiz.cevap_taslagi.replace("12", "N"), yok.cevap_taslagi.replace("13", "N"))
        self.assertTrue(yok.cevap_taslagi.startswith("Hello"))

    def test_ingilizce_hassas_konu_onayli_sablon(self):
        t = _isle(_kayit("My skin is burning and I have a rash after using it"))
        self.assertEqual((t.konu, t.dil, t.devret), ("istenmeyen-etki", "en", True))
        self.assertEqual(t.cevap_taslagi, ONAYLI_SABLONLAR["en"]["istenmeyen-etki"])

    def test_tutar_bicimi(self):
        self.assertEqual(tutar_bicimle(1467.88, "tr"), "1.467,88 USD")
        self.assertEqual(tutar_bicimle(1467.88, "en"), "1,467.88 USD")


class UrunAramaTesti(unittest.TestCase):
    def test_turkce_terim_ingilizce_sorguya(self):
        self.assertEqual(arama_sorgulari(normalize("Nemlendirici krem ne kadar?")),
                         ("moisturizer", "lotion", "cream"))
        self.assertEqual(arama_sorgulari(normalize("C vitamini serumu")), ("serum", "vitamin c"))
        self.assertEqual(arama_sorgulari(normalize("Hayvanlar üzerinde test ediliyor mu?")), ())

    def test_alaka_filtresi(self):
        self.assertFalse(alakali_mi(Urun("Ice Cream", 5.49, "groceries"), "cream"))
        self.assertFalse(alakali_mi(Urun("Red Lipstick", 12.99, "beauty"), "cream"))
        self.assertTrue(alakali_mi(Urun("Vaseline Men Body and Face Lotion", 9.99, "skin-care"), "lotion"))

    def test_yanlis_pozitifler_elenir(self):
        sonuc = urun_ara(normalize("Nemlendirici krem ne kadar?"), SahteUrunIstemcisi())
        self.assertEqual([u.baslik for u in sonuc.urunler], ["Vaseline Men Body and Face Lotion"])
        self.assertIn("Ice Cream", sonuc.elenenler)

    def test_mesaj_10_taslakta_urun_ve_fiyat(self):
        t = _isle(MESAJLAR[9])
        self.assertIn("Vaseline Men Body and Face Lotion — 9,99 USD", t.cevap_taslagi)
        self.assertNotIn("Ice Cream", t.cevap_taslagi)
        self.assertIn("Ice Cream", t.to_dict()["not"])  # temsilci neyin elendiğini görür

    def test_eslesme_yoksa_genel_taslak(self):
        t = _isle(MESAJLAR[8])  # retinol serum
        self.assertIn("birebir eşleştiremedik", t.cevap_taslagi)
        self.assertIn("uygun eşleşme yok", t.to_dict()["not"])

    def test_arama_hatasi_cokmez(self):
        t = _isle(MESAJLAR[9], SahteUrunIstemcisi(hata=True))
        self.assertFalse(t.devret)
        self.assertIn("arama hatası", t.to_dict()["not"])
        self.assertIsNotNone(t.cevap_taslagi)

    def test_siparis_ve_hassas_mesajlarda_arama_yapilmaz(self):
        urun = SahteUrunIstemcisi()
        for idx in (0, 1, 3, 4, 7):  # 1, 2, 4, 5, 8
            _isle(MESAJLAR[idx], urun)
        self.assertEqual(urun.sorgular, [])


class IddiasizTaslakTesti(unittest.TestCase):
    YASAK_IDDIALAR = ("test edilmez", "test edilmemektedir", "cruelty", "vegan", "alkol içermez",
                      "alkolsüz", "tüm cilt", "uygundur", "200 ml'dir", "hipoalerjenik")

    def test_dogrulanmamis_iddia_uretilmez(self):
        for idx in (8, 10, 12, 14):  # 9, 11, 13, 15
            with self.subTest(id=idx + 1):
                t = _isle(MESAJLAR[idx])
                for iddia in self.YASAK_IDDIALAR:
                    self.assertNotIn(iddia, t.cevap_taslagi.lower())
                self.assertIn("Doğrulanmamış iddia üretilmedi", t.to_dict()["not"])

    def test_teyit_notlari(self):
        self.assertIn("kargo firması", _isle(MESAJLAR[11]).to_dict()["not"])
        self.assertIn("indirim kodu", _isle(MESAJLAR[13]).to_dict()["not"])

    def test_her_yanitlanabilir_mesajin_taslagi_var(self):
        for m in MESAJLAR:
            t = _isle(m)
            if m["id"] != 7:  # spam bilerek yanıtsız
                self.assertTrue(t.cevap_taslagi, m["id"])


class RaporlamaTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.talepler = [_isle(m) for m in MESAJLAR]

    def test_istatistik(self):
        ist = istatistik(self.talepler)
        self.assertEqual((ist.toplam, ist.devredilen, ist.guvenlik_engeli, ist.spam, ist.otomatik),
                         (15, 4, 1, 1, 10))
        self.assertEqual(sum(ist.konu_adet.values()), 15)

    def test_terminal_renksiz_ansi_icermez(self):
        metin = terminal_ozeti(self.talepler, renk=False)
        self.assertNotIn("\033[", metin)
        self.assertRegex(metin, r"TOPLAM\s+15\s+4")

    def test_terminal_renkli(self):
        self.assertIn("\033[", terminal_ozeti(self.talepler, renk=True))

    def test_html_veri_ve_xss_korumasi(self):
        kotu = dict(MESAJLAR[11], id=100, mesaj="</script><img src=x onerror=alert(1)> kargo firması?")
        html = html_ozeti(self.talepler + [_isle(kotu)], "2026-09-28T00:00:00+00:00")
        gomulu = re.search(r'<script id="veri" type="application/json">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn("</script>", gomulu)
        self.assertNotIn("<img", gomulu)
        veri = json.loads(gomulu)
        self.assertEqual(len(veri["talepler"]), 16)
        self.assertIn("<img src=x", veri["talepler"][-1]["mesaj"])  # veri korunur, yalnızca kaçışlanır
        self.assertNotIn("innerHTML", html)

    def test_detay_semasi(self):
        d = self.talepler[5].detay_dict()
        for alan in ("id", "konu", "devret", "cevap_taslagi", "not", "guven", "dil", "islem_zamani"):
            self.assertIn(alan, d)
        self.assertEqual(d["dil"], "en")


if __name__ == "__main__":
    unittest.main()

import io
import json
import os
import unittest
import urllib.error
from unittest import mock

from otomasyon.api import (
    DogrulanmisSepet,
    DummyJSONIstemcisi,
    Sepet,
    SepetUrunu,
    SorguDurumu,
    dogrula,
    sepet_yorumla,
    siparis_bilgi_metni,
)
from otomasyon.metin import normalize, siparis_numaralari

SEPET_5 = Sepet(id=5, user_id=5, urunler=(SepetUrunu("Soft Drinks", 4),), toplam=1467.88)


class _Yanit(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class SiparisNoAyiklamaTesti(unittest.TestCase):
    def test_desteklenen_bicimler(self):
        for metin, beklenen in [("12 numaralı siparişim", (12,)), ("where is my order #3?", (3,)),
                                ("siparişim 4 ne zaman gelir", (4,)), ("Order 77 status", (77,)),
                                ("7 nolu sipariş", (7,))]:
            with self.subTest(metin=metin):
                self.assertEqual(siparis_numaralari(normalize(metin)), beklenen)


class SahiplikDogrulamaTesti(unittest.TestCase):
    def test_eslesen_musteri(self):
        self.assertIsInstance(dogrula(SEPET_5, 5), DogrulanmisSepet)

    def test_farkli_musteri(self):
        self.assertIsNone(dogrula(SEPET_5, 7))

    def test_tur_birebir_olmali(self):
        for musteri_id in ("5", 5.0, None, True):
            with self.subTest(musteri_id=musteri_id):
                self.assertIsNone(dogrula(SEPET_5, musteri_id))

    def test_dogrulanmamis_sepetle_metin_uretilemez(self):
        with self.assertRaises(TypeError):
            siparis_bilgi_metni(SEPET_5)

    def test_bilgi_metni_urun_adet_tutar(self):
        metin = siparis_bilgi_metni(dogrula(SEPET_5, 5))
        self.assertIn("Soft Drinks × 4", metin)
        self.assertIn("1.467,88 USD", metin)


class YanitYorumlamaTesti(unittest.TestCase):
    def test_not_found_mesaji(self):
        q = sepet_yorumla(9999, {"message": "Cart with id '9999' not found"})
        self.assertIs(q.durum, SorguDurumu.BULUNAMADI)

    def test_bozuk_govde_cokmez(self):
        for veri in ({"id": 1}, {"id": 1, "userId": "1", "products": [], "total": 0}, [], None):
            with self.subTest(veri=veri):
                self.assertIs(sepet_yorumla(1, veri).durum, SorguDurumu.HATA)


class HttpIstemciTesti(unittest.TestCase):
    def _http_hatasi(self, kod):
        govde = io.BytesIO(json.dumps({"message": "Cart with id '9999' not found"}).encode())
        return urllib.error.HTTPError("u", kod, "hata", {}, govde)

    def test_404_bulunamadi(self):
        with mock.patch("urllib.request.urlopen", side_effect=self._http_hatasi(404)):
            self.assertIs(DummyJSONIstemcisi().sepet_getir(9999).durum, SorguDurumu.BULUNAMADI)

    def test_ag_hatasi_cokmez_ve_tekrar_dener(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns")) as m:
            q = DummyJSONIstemcisi(deneme_sayisi=2).sepet_getir(1)
        self.assertIs(q.durum, SorguDurumu.HATA)
        self.assertEqual(m.call_count, 2)

    def test_5xx_hata(self):
        with mock.patch("urllib.request.urlopen", side_effect=self._http_hatasi(503)):
            self.assertIs(DummyJSONIstemcisi(deneme_sayisi=1).sepet_getir(1).durum, SorguDurumu.HATA)

    def test_basarili_yanit_ve_onbellek(self):
        govde = json.dumps({"id": 5, "userId": 5, "total": 10.0,
                            "products": [{"title": "X", "quantity": 1}]}).encode()
        with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: _Yanit(govde)) as m:
            istemci = DummyJSONIstemcisi()
            self.assertIs(istemci.sepet_getir(5).durum, SorguDurumu.BULUNDU)
            istemci.sepet_getir(5)
        self.assertEqual(m.call_count, 1)


@unittest.skipUnless(os.environ.get("CANLI_TEST") == "1", "canlı API testi: CANLI_TEST=1 ile çalışır")
class CanliApiTesti(unittest.TestCase):
    def test_gercek_dummyjson(self):
        istemci = DummyJSONIstemcisi()
        self.assertEqual(istemci.sepet_getir(12).sepet.user_id, 12)
        self.assertIs(istemci.sepet_getir(9999).durum, SorguDurumu.BULUNAMADI)


if __name__ == "__main__":
    unittest.main()

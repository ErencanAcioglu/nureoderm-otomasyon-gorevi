"""Bonus: DummyJSON ürün arama (`/products/search?q=`) ve alaka filtresi.

DummyJSON genel bir test mağazasıdır ve kozmetik terimlerini Türkçe bilmez. Bu yüzden:
  1. Mesajdaki Türkçe ürün terimi İngilizce arama sorgularına çevrilir (nemlendirici → moisturizer, lotion).
  2. Dönen sonuçlar filtrelenir: kozmetik kategorisinde olmalı VE sorgu kelimeleri başlıkta geçmeli.
     Filtre olmadan "krem" araması "Ice Cream" (groceries) ve "Red Lipstick" döndürür.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .api import DENEME_SAYISI, TEMEL_URL, ZAMAN_ASIMI_SN, json_getir

KOZMETIK_KATEGORILERI = frozenset({"beauty", "skin-care", "fragrances"})
EN_FAZLA_URUN = 3

# (normalize edilmiş metinde aranan desen, DummyJSON'a gönderilecek İngilizce sorgular)
ARAMA_TERIMLERI: Tuple[Tuple["re.Pattern[str]", Tuple[str, ...]], ...] = tuple(
    (re.compile(desen), sorgular) for desen, sorgular in (
        (r"\bnemlendirici|\bmoisturi[sz]er", ("moisturizer", "lotion")),
        (r"\bgunes krem|\bsunscreen|\bspf\b", ("sunscreen",)),
        (r"\bkrem|\bcream", ("cream",)),
        (r"\bserum", ("serum",)),
        (r"\bretinol", ("retinol",)),
        (r"\bc vitamin|\bvitamin c", ("vitamin c",)),
        (r"\btonik|\btoner", ("toner",)),
        (r"\blosyon|\blotion", ("lotion",)),
        (r"\bruj\b|\blipstick", ("lipstick",)),
        (r"\bmaskara|\bmascara", ("mascara",)),
        (r"\boje\b|\bnail polish", ("nail polish",)),
        (r"\bsabun|\bsoap", ("soap",)),
        (r"\bparfum|\bperfume", ("perfume",)),
        (r"\bsampuan|\bshampoo", ("shampoo",)),
        (r"\btemizleyici|\bcleanser", ("cleanser",)),
        (r"\bdus jel|\bbody wash", ("body wash",)),
    )
)


@dataclass(frozen=True)
class Urun:
    baslik: str
    fiyat: float
    kategori: str


@dataclass(frozen=True)
class AramaSonucu:
    sorgular: Tuple[str, ...]
    urunler: Tuple[Urun, ...]
    elenenler: Tuple[str, ...]  # API'nin döndürüp alaka filtresine takılan ürün başlıkları
    hata: Optional[str] = None

    @property
    def arama_yapildi(self) -> bool:
        return bool(self.sorgular)


def arama_sorgulari(normal_metin: str) -> Tuple[str, ...]:
    sorgular: List[str] = []
    for desen, karsiliklar in ARAMA_TERIMLERI:
        if desen.search(normal_metin):
            sorgular.extend(s for s in karsiliklar if s not in sorgular)
    return tuple(sorgular)


def alakali_mi(urun: Urun, sorgu: str) -> bool:
    baslik = urun.baslik.lower()
    return urun.kategori in KOZMETIK_KATEGORILERI and all(k in baslik for k in sorgu.lower().split())


class UrunAramaIstemcisi:
    def __init__(self, temel_url: str = TEMEL_URL, zaman_asimi: float = ZAMAN_ASIMI_SN,
                 deneme_sayisi: int = DENEME_SAYISI) -> None:
        self.temel_url = temel_url.rstrip("/")
        self.zaman_asimi = zaman_asimi
        self.deneme_sayisi = deneme_sayisi
        self._onbellek: Dict[str, List[Urun]] = {}

    def ara(self, sorgu: str) -> Tuple[List[Urun], Optional[str]]:
        if sorgu in self._onbellek:
            return self._onbellek[sorgu], None
        url = (f"{self.temel_url}/products/search?q={urllib.parse.quote(sorgu)}"
               "&select=title,price,category&limit=20")
        kod, veri, hata = json_getir(url, self.zaman_asimi, self.deneme_sayisi)
        if hata or kod == 404:
            return [], hata or "HTTP 404"
        try:
            urunler = [Urun(str(u["title"]), float(u["price"]), str(u.get("category", "")))
                       for u in veri["products"]]
        except (KeyError, TypeError, ValueError) as hata_:
            return [], f"Beklenmeyen yanıt biçimi: {hata_}"
        self._onbellek[sorgu] = urunler
        return urunler, None


def urun_ara(normal_metin: str, istemci: "UrunAramaIstemcisi") -> AramaSonucu:
    sorgular = arama_sorgulari(normal_metin)
    bulunan: List[Urun] = []
    elenen: List[str] = []
    hatalar: List[str] = []
    for sorgu in sorgular:
        urunler, hata = istemci.ara(sorgu)
        if hata:
            hatalar.append(f"{sorgu}: {hata}")
        for urun in urunler:
            if alakali_mi(urun, sorgu):
                if urun not in bulunan:
                    bulunan.append(urun)
            elif urun.baslik not in elenen:
                elenen.append(urun.baslik)
    elenen = [b for b in elenen if b not in {u.baslik for u in bulunan}]
    return AramaSonucu(sorgular, tuple(bulunan[:EN_FAZLA_URUN]), tuple(elenen),
                       "; ".join(hatalar) or None)

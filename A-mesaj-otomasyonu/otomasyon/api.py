"""DummyJSON sepet (sipariş) istemcisi ve sahiplik doğrulaması.

IDOR koruması iki katmanlıdır:
  1. `dogrula(sepet, musteri_id)` sepetin `userId` değerini mesajı yazan `musteri_id` ile birebir
     (tam sayı, tür dahil) karşılaştırır; eşleşmezse `None` döner.
  2. Sipariş içeriği yalnızca `DogrulanmisSepet` üzerinden metne dökülebilir (`siparis_bilgi_metni`).
     Doğrulama başarısızsa bu nesne hiç oluşmaz; başka müşterinin ürünleri/tutarı hiçbir yola sızamaz.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

try:  # Python 3.8+
    from typing import Protocol
except ImportError:  # pragma: no cover
    Protocol = object  # type: ignore

TEMEL_URL = "https://dummyjson.com"
ZAMAN_ASIMI_SN = 10
DENEME_SAYISI = 2
PARA_BIRIMI = "USD"  # DummyJSON para birimi belirtmiyor; mağaza verisi USD varsayılır.


class SorguDurumu(Enum):
    BULUNDU = "bulundu"
    BULUNAMADI = "bulunamadi"
    HATA = "hata"


@dataclass(frozen=True)
class SepetUrunu:
    baslik: str
    adet: int


@dataclass(frozen=True)
class Sepet:
    id: int
    user_id: int
    urunler: Tuple[SepetUrunu, ...]
    toplam: float


@dataclass(frozen=True)
class SepetSorgusu:
    sepet_id: int
    durum: SorguDurumu
    sepet: Optional[Sepet] = None
    hata: Optional[str] = None


@dataclass(frozen=True)
class DogrulanmisSepet:
    """Sahipliği doğrulanmış sepet. Yalnızca `dogrula` tarafından oluşturulmalıdır."""
    sepet: Sepet
    musteri_id: int


class SepetIstemcisi(Protocol):
    def sepet_getir(self, sepet_id: int) -> SepetSorgusu: ...


def _tam_sayi_mi(deger: Any) -> bool:
    return isinstance(deger, int) and not isinstance(deger, bool)


def sepet_yorumla(sepet_id: int, veri: Any) -> SepetSorgusu:
    """API gövdesini SepetSorgusu'na çevirir; beklenmeyen biçim HATA olur, çökme olmaz."""
    if isinstance(veri, Mapping) and "not found" in str(veri.get("message", "")).lower():
        return SepetSorgusu(sepet_id, SorguDurumu.BULUNAMADI)
    try:
        if not _tam_sayi_mi(veri["userId"]):
            raise ValueError("userId tam sayı değil")
        sepet = Sepet(
            id=int(veri["id"]),
            user_id=veri["userId"],
            urunler=tuple(SepetUrunu(str(u["title"]), int(u["quantity"])) for u in veri["products"]),
            toplam=float(veri["total"]),
        )
    except (KeyError, TypeError, ValueError) as hata:
        return SepetSorgusu(sepet_id, SorguDurumu.HATA, hata=f"Beklenmeyen yanıt biçimi: {hata}")
    return SepetSorgusu(sepet_id, SorguDurumu.BULUNDU, sepet=sepet)


class DummyJSONIstemcisi:
    def __init__(self, temel_url: str = TEMEL_URL, zaman_asimi: float = ZAMAN_ASIMI_SN,
                 deneme_sayisi: int = DENEME_SAYISI) -> None:
        self.temel_url = temel_url.rstrip("/")
        self.zaman_asimi = zaman_asimi
        self.deneme_sayisi = deneme_sayisi
        self._onbellek: Dict[int, SepetSorgusu] = {}

    def sepet_getir(self, sepet_id: int) -> SepetSorgusu:
        if sepet_id not in self._onbellek:
            sonuc = self._istek(sepet_id)
            if sonuc.durum is SorguDurumu.HATA:
                return sonuc  # geçici hatalar önbelleğe alınmaz
            self._onbellek[sepet_id] = sonuc
        return self._onbellek[sepet_id]

    def _istek(self, sepet_id: int) -> SepetSorgusu:
        istek = urllib.request.Request(
            f"{self.temel_url}/carts/{int(sepet_id)}",
            headers={"Accept": "application/json", "User-Agent": "nureoderm-otomasyon/1.0"},
        )
        son_hata = "bilinmeyen hata"
        for _ in range(self.deneme_sayisi):
            try:
                with urllib.request.urlopen(istek, timeout=self.zaman_asimi) as yanit:
                    return sepet_yorumla(sepet_id, json.loads(yanit.read().decode("utf-8")))
            except urllib.error.HTTPError as hata:
                if hata.code == 404:
                    return SepetSorgusu(sepet_id, SorguDurumu.BULUNAMADI)
                son_hata = f"HTTP {hata.code}"
                if hata.code < 500:
                    break  # 4xx tekrar denemekle düzelmez
            except (urllib.error.URLError, socket.timeout, TimeoutError,
                    json.JSONDecodeError, UnicodeDecodeError) as hata:
                son_hata = f"{type(hata).__name__}: {hata}"
        return SepetSorgusu(sepet_id, SorguDurumu.HATA, hata=son_hata)


def dogrula(sepet: Sepet, musteri_id: Any) -> Optional[DogrulanmisSepet]:
    """Sepet mesajı yazan müşteriye aitse DogrulanmisSepet, değilse None."""
    if _tam_sayi_mi(musteri_id) and sepet.user_id == musteri_id:
        return DogrulanmisSepet(sepet, musteri_id)
    return None


def _tutar(deger: float) -> str:
    # 1467.88 → "1.467,88 USD"
    return f"{deger:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + f" {PARA_BIRIMI}"


def siparis_bilgi_metni(dogrulanmis: DogrulanmisSepet) -> str:
    if not isinstance(dogrulanmis, DogrulanmisSepet):
        raise TypeError("Sipariş bilgisi yalnızca sahipliği doğrulanmış sepet için üretilebilir")
    sepet = dogrulanmis.sepet
    satirlar = [f"• {u.baslik} × {u.adet}" for u in sepet.urunler]
    return (
        f"Merhaba, {sepet.id} numaralı siparişiniz sistemimizde kayıtlı. Sipariş içeriği:\n"
        + "\n".join(satirlar)
        + f"\nToplam tutar: {_tutar(sepet.toplam)}\n"
        "Kargo takip bilgisi hazır olduğunda size ayrıca iletilecektir."
    )

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

from .sablonlar import metinler, tutar_bicimle

try:  # Python 3.8+
    from typing import Protocol
except ImportError:  # pragma: no cover
    Protocol = object  # type: ignore

TEMEL_URL = "https://dummyjson.com"
ZAMAN_ASIMI_SN = 10
DENEME_SAYISI = 2


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


def json_getir(url: str, zaman_asimi: float = ZAMAN_ASIMI_SN,
               deneme_sayisi: int = DENEME_SAYISI) -> Tuple[Optional[int], Any, Optional[str]]:
    """GET + JSON. Dönüş: (http_kodu, gövde, hata). Hiçbir durumda istisna fırlatmaz.

    404 hata sayılmaz (kod=404 döner); ağ hatası, zaman aşımı ve 5xx tekrar denenir,
    diğer 4xx tekrar denenmez.
    """
    istek = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "nureoderm-otomasyon/1.0"}
    )
    son_hata = "bilinmeyen hata"
    for _ in range(deneme_sayisi):
        try:
            with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
                return getattr(yanit, "status", 200), json.loads(yanit.read().decode("utf-8")), None
        except urllib.error.HTTPError as hata:
            if hata.code == 404:
                return 404, None, None
            son_hata = f"HTTP {hata.code}"
            if hata.code < 500:
                break
        except (urllib.error.URLError, socket.timeout, TimeoutError,
                json.JSONDecodeError, UnicodeDecodeError) as hata:
            son_hata = f"{type(hata).__name__}: {hata}"
    return None, None, son_hata


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
        kod, veri, hata = json_getir(f"{self.temel_url}/carts/{int(sepet_id)}",
                                     self.zaman_asimi, self.deneme_sayisi)
        if kod == 404:
            return SepetSorgusu(sepet_id, SorguDurumu.BULUNAMADI)
        if hata:
            return SepetSorgusu(sepet_id, SorguDurumu.HATA, hata=hata)
        return sepet_yorumla(sepet_id, veri)


def dogrula(sepet: Sepet, musteri_id: Any) -> Optional[DogrulanmisSepet]:
    """Sepet mesajı yazan müşteriye aitse DogrulanmisSepet, değilse None."""
    if _tam_sayi_mi(musteri_id) and sepet.user_id == musteri_id:
        return DogrulanmisSepet(sepet, musteri_id)
    return None


def siparis_bilgi_metni(dogrulanmis: DogrulanmisSepet, dil: str = "tr") -> str:
    if not isinstance(dogrulanmis, DogrulanmisSepet):
        raise TypeError("Sipariş bilgisi yalnızca sahipliği doğrulanmış sepet için üretilebilir")
    sepet = dogrulanmis.sepet
    m = metinler(dil)
    satirlar = [f"• {u.baslik} × {u.adet}" for u in sepet.urunler]
    return "\n".join(
        [m["siparis_baslik"].format(no=sepet.id), *satirlar,
         m["siparis_toplam"].format(tutar=tutar_bicimle(sepet.toplam, dil)), m["siparis_kargo"]]
    )

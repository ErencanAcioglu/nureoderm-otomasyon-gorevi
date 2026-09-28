"""Metin normalizasyonu ve temizleme.

Kural motoru tek bir kanonik biçim üzerinde çalışır: Türkçe'ye uygun küçük harf,
aksansız ASCII (ç→c, ğ→g, ı→i, ö→o, ş→s, ü→u), noktalama yerine boşluk.
Böylece "Siparişim", "SİPARİŞİM" ve "siparisim" aynı desene düşer.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Tuple

_TR_KATLAMA = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    "â": "a", "î": "i", "û": "u",
})

# Açık URL'ler ve "bit.ly/xyz" gibi şemasız kısa linkler.
_URL_RE = re.compile(
    r"(https?://\S+|www\.\S+|\b[a-z0-9-]+\.(?:ly|me|com|net|org|io|co|link|xyz|site|shop)/\S*)",
    re.IGNORECASE,
)

# Sipariş numarası yalnızca bir çapa ifadesinin yanındaysa kabul edilir;
# "200 ml" gibi rastgele sayılar sipariş numarası sayılmaz.
_SIPARIS_NO_DESENLERI = (
    re.compile(r"#\s*(\d{1,10})\b"),
    re.compile(r"\b(\d{1,10})\s*(?:numarali|nolu|no lu|no)\b"),
    re.compile(r"\b(?:siparis|order)\w*\s*(?:no|numarasi|numara|number|num)?\s*(\d{1,10})\b"),
)


def _turkce_kucuk_harf(metin: str) -> str:
    # str.lower() "I"yı "i"ye, "İ"yi "i̇"ye (birleşik nokta ile) çevirir; önce düzeltiyoruz.
    return metin.replace("I", "ı").replace("İ", "i").lower()


def normalize(metin: str) -> str:
    """Eşleştirme için kanonik biçim: küçük harf, ASCII, sadece [a-z0-9#% ]."""
    metin = unicodedata.normalize("NFC", metin)
    metin = _turkce_kucuk_harf(metin).translate(_TR_KATLAMA)
    metin = "".join(
        c for c in unicodedata.normalize("NFKD", metin) if not unicodedata.combining(c)
    )
    metin = _URL_RE.sub(" ", metin)
    metin = re.sub(r"[^a-z0-9#%\s]", " ", metin)
    return re.sub(r"\s+", " ", metin).strip()


_TR_HARFLERI = frozenset("çğıöşüÇĞİÖŞÜâÂ")
_EN_ISARETLERI = frozenset({
    "order", "status", "shipping", "shipped", "delivery", "tracking", "where", "is", "my", "hi",
    "hello", "the", "it", "has", "been", "week", "please", "price", "how", "much", "when", "thanks",
    "thank", "you", "what", "can", "refund", "return", "your", "do", "does", "have", "i",
})
_TR_ISARETLERI = frozenset({
    "merhaba", "ne", "mi", "mu", "var", "siparis", "siparisim", "nerede", "kadar", "nedir", "acaba",
    "urun", "fiyat", "bir", "ve", "icin", "misiniz", "musunuz", "hangi", "zaman", "numarali",
})


def dil_tespit(ham_metin: str) -> str:
    """Hafif dil kontrolü: 'en' yalnızca mesaj bariz İngilizceyse, aksi halde 'tr'.

    Türkçe'ye özgü harf varsa Türkçe; yoksa en az 2 İngilizce işaret kelimesi olmalı ve
    Türkçe işaretlerden fazla olmalı. Belirsizlikte varsayılan dil Türkçe'dir.
    """
    if any(c in _TR_HARFLERI for c in ham_metin):
        return "tr"
    kelimeler = normalize(ham_metin).split()
    en = sum(k in _EN_ISARETLERI for k in kelimeler)
    tr = sum(k in _TR_ISARETLERI for k in kelimeler)
    return "en" if en >= 2 and en > tr else "tr"


def url_iceriyor(ham_metin: str) -> bool:
    return bool(_URL_RE.search(ham_metin))


def siparis_numaralari(normal_metin: str) -> Tuple[int, ...]:
    """Normalize edilmiş metinden sipariş numaralarını sırayı koruyarak çıkarır."""
    bulunan: List[int] = []
    for desen in _SIPARIS_NO_DESENLERI:
        for eslesme in desen.finditer(normal_metin):
            numara = int(eslesme.group(1))
            if numara not in bulunan:
                bulunan.append(numara)
    return tuple(bulunan)

"""Kural tabanlı konu sınıflandırıcı.

Karar sırası (yukarıdaki kazanır):
  1. istenmeyen-etki  — sağlık riski; tek bir eşleşme yeterli, hiçbir kural bunu ezemez.
  2. spam             — en az 2 spam sinyali → 'diger' + 'Spam/İlgisiz'.
  3. iade-sikayet     — hassas konu; eşleşme varsa diğer konuların önüne geçer.
  4. puanlama         — siparis-durumu / fiyat / urun-sorusu / diger arasında en yüksek puan;
                        eşitlikte ONCELIK sırası.
  5. hiçbir kural yok — 'diger' + düşük güven.

Güven skoru deterministiktir (aynı girdi → aynı skor), olasılık değildir:
  * mutlak kararlar (1-3):  0.5 + 0.5 * p / (p + 1)            p = konu puanı / sinyal sayısı
  * puanlama (4):           0.5 * s1 / (s1 + 1) + 0.5 * (s1 - s2) / s1
                            s1 = kazanan puan, s2 = ikinci en yüksek puan
  İlk terim sinyal gücünü (doygunlaşan), ikincisi rakip konulara karşı farkı ölçer.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .metin import normalize, siparis_numaralari, url_iceriyor

KONULAR = ("urun-sorusu", "fiyat", "siparis-durumu", "iade-sikayet", "istenmeyen-etki", "diger")
HASSAS_KONULAR = frozenset({"iade-sikayet", "istenmeyen-etki"})

# Puanlama adımında eşitlik bozma sırası.
ONCELIK = ("siparis-durumu", "fiyat", "urun-sorusu", "diger")

DUSUK_GUVEN_ESIGI = 0.6
SPAM_ESIGI = 2
SIPARIS_NO_AGIRLIGI = 2.0

ETIKET_SPAM = "Spam/İlgisiz"
ETIKET_ESLESME_YOK = "Eşleşme yok"


@dataclass(frozen=True)
class Kural:
    konu: str
    ad: str
    desen: "re.Pattern[str]"
    agirlik: float


def _k(konu: str, ad: str, desen: str, agirlik: float = 1.0) -> Kural:
    return Kural(konu, ad, re.compile(desen), agirlik)


# Desenler normalize edilmiş (küçük harf, ASCII) metin üzerinde çalışır.
KURALLAR: Tuple[Kural, ...] = (
    # --- istenmeyen-etki ---
    _k("istenmeyen-etki", "yanma", r"\byan(di|iyor|ma|mis)", 2),
    _k("istenmeyen-etki", "kizariklik", r"\bkizar", 2),
    _k("istenmeyen-etki", "kasinti", r"\bkasin", 2),
    _k("istenmeyen-etki", "alerji", r"alerj|allerg", 2),
    _k("istenmeyen-etki", "cilt-lezyonu", r"\b(dokuntu|sivilce|egzama|kurdesen|pul pul)", 2),
    _k("istenmeyen-etki", "sislik", r"\bsis(ti|lik|me|kin)\b", 2),
    _k("istenmeyen-etki", "tahris", r"tahris|irrit", 2),
    _k("istenmeyen-etki", "reaksiyon", r"reaksiyon|reaction", 2),
    _k("istenmeyen-etki", "en-belirti", r"\b(burn(ed|ing|s)?|rash|itch\w*|swell\w*)\b", 2),
    _k("istenmeyen-etki", "saglik-kurumu", r"\b(doktor|hastane|dermatolog)", 1.5),
    # --- iade-sikayet ---
    _k("iade-sikayet", "iade", r"\biade", 2),
    _k("iade-sikayet", "hasarli-urun", r"\b(ezik|kirik|hasarli|bozuk|patlak|akmis|yirtik)\b", 2),
    _k("iade-sikayet", "sikayet", r"sikayet", 2),
    _k("iade-sikayet", "geri-odeme", r"geri odeme|para iade|refund", 2),
    _k("iade-sikayet", "yanlis-eksik", r"yanlis urun|eksik urun|eksik geldi", 2),
    _k("iade-sikayet", "degisim", r"\bdegisim|degistir", 1.5),
    _k("iade-sikayet", "memnuniyetsizlik", r"memnun degil|rezalet|berbat|magdur", 1.5),
    _k("iade-sikayet", "en-iade", r"\b(damaged|broken|return)\b", 2),
    # --- siparis-durumu ---
    _k("siparis-durumu", "siparisim", r"\bsiparis(im|imin|imiz|imizin|imi|ime)\b", 2),
    _k("siparis-durumu", "konum", r"\b(nerede|nerde|where is)\b", 1.5),
    _k("siparis-durumu", "teslim-zamani", r"ne zaman (gelir|gelecek|ulasir|kargoya)|kargoya veril", 1.5),
    _k("siparis-durumu", "ulasmadi", r"\b(ulasmadi|gelmedi)\b", 1.5),
    _k("siparis-durumu", "durum", r"\b(durumu|status)\b", 1.5),
    _k("siparis-durumu", "kargo-takip", r"\bkargom|kargo takip|takip no", 1.5),
    _k("siparis-durumu", "en-siparis", r"\b(my order|tracking|shipped)\b", 2),
    # --- fiyat ---
    _k("fiyat", "fiyat", r"\bfiyat", 2),
    _k("fiyat", "ne-kadar", r"\bne kadar\b", 2),
    _k("fiyat", "tutar", r"\b(kac tl|kac para|kaca|ucret\w*)\b", 2),
    _k("fiyat", "indirim", r"\b(indirim|kampanya|kupon|promosyon)", 2),
    _k("fiyat", "en-fiyat", r"\b(price|cost|how much|discount)\b", 2),
    # --- urun-sorusu ---
    _k("urun-sorusu", "var-mi", r"\bvar mi\b", 1),
    _k("urun-sorusu", "icerik", r"\b(icerig\w*|icerik\w*|formul\w*)", 1.5),
    _k("urun-sorusu", "bilesen", r"\b(alkol|paraben|parfum|silikon|vegan)\b", 1.5),
    _k("urun-sorusu", "cilt-tipi", r"\bcilt tip|\b(kuru|yagli|karma|hassas|akneli) cilt", 1.5),
    _k("urun-sorusu", "uygunluk", r"\buygun", 1),
    _k("urun-sorusu", "kullanim", r"\b(kullanilir|kullanabilir|nasil kullan|kullanim)", 1.5),
    _k("urun-sorusu", "hayvan-testi", r"\b(test edil|hayvan|cruelty)", 1.5),
    _k("urun-sorusu", "hacim", r"\b\d+\s*(ml|gr|g|mg)\b", 1),
    _k("urun-sorusu", "urun-geneli", r"\b(urun(unuz|leriniz|unuzde)|stok|mevcut mu)", 1),
    # Ürün adları zayıf sinyaldir: "krem ne kadar?" fiyat sorusudur, ürün sorusu değil.
    _k("urun-sorusu", "urun-terimi",
       r"\b(serum\w*|krem\w*|tonik\w*|nemlendirici|temizleyici|maske\w*|sampuan\w*|retinol|vitamin\w*|spf)\b",
       0.5),
    # --- diger (genel bilgi) ---
    _k("diger", "kargo-firmasi", r"\b(hangi kargo|kargo firma|kargo sirket|teslimat sure)", 2),
    _k("diger", "magaza-bilgisi", r"\b(magaza|adres|calisma saat|iletisim|telefon)", 1.5),
)

SPAM_DESENLERI: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("takipci-begeni", re.compile(r"takipci|follower|begeni|abone kas")),
    ("abarti-vaat", re.compile(r"%\s*100|\bbedava\b|\bkazan(in|mak)\b|\btikla|\bclick\b|\bdm\b")),
)


@dataclass(frozen=True)
class Siniflandirma:
    konu: str
    guven: float
    etiket: Optional[str]
    eslesen_kurallar: Tuple[str, ...]
    ikincil_konular: Tuple[str, ...]
    siparis_numaralari: Tuple[int, ...]

    @property
    def hassas(self) -> bool:
        return self.konu in HASSAS_KONULAR

    @property
    def inceleme_gerekli(self) -> bool:
        return self.guven < DUSUK_GUVEN_ESIGI


def _mutlak_guven(puan: float) -> float:
    return round(0.5 + 0.5 * puan / (puan + 1), 2)


def _karsilastirmali_guven(s1: float, s2: float) -> float:
    return round(0.5 * s1 / (s1 + 1) + 0.5 * (s1 - s2) / s1, 2)


def spam_sinyalleri(ham_metin: str, normal_metin: str) -> List[str]:
    sinyaller = ["link"] if url_iceriyor(ham_metin) else []
    sinyaller += [ad for ad, desen in SPAM_DESENLERI if desen.search(normal_metin)]
    return sinyaller


def siniflandir(mesaj: str) -> Siniflandirma:
    normal = normalize(mesaj)
    numaralar = siparis_numaralari(normal)

    puanlar: Dict[str, float] = defaultdict(float)
    eslesenler: List[str] = []
    for kural in KURALLAR:
        if kural.desen.search(normal):
            puanlar[kural.konu] += kural.agirlik
            eslesenler.append(f"{kural.konu}:{kural.ad}")
    if numaralar:
        puanlar["siparis-durumu"] += SIPARIS_NO_AGIRLIGI
        eslesenler.append("siparis-durumu:siparis-no")

    def sonuc(konu: str, guven: float, etiket: Optional[str] = None,
              ekstra: Tuple[str, ...] = ()) -> Siniflandirma:
        ikincil = tuple(
            k for k, _ in sorted(puanlar.items(), key=lambda kv: -kv[1]) if k != konu and puanlar[k] > 0
        )
        return Siniflandirma(konu, guven, etiket, tuple(eslesenler) + ekstra, ikincil, numaralar)

    # 1) Sağlık riski: spam veya başka konu gibi görünse bile kaçırılmamalı.
    if puanlar["istenmeyen-etki"] > 0:
        return sonuc("istenmeyen-etki", _mutlak_guven(puanlar["istenmeyen-etki"]))

    # 2) Spam
    spam = spam_sinyalleri(mesaj, normal)
    if len(spam) >= SPAM_ESIGI:
        return sonuc("diger", _mutlak_guven(len(spam)), ETIKET_SPAM,
                     tuple(f"spam:{s}" for s in spam))

    # 3) İade / şikâyet
    if puanlar["iade-sikayet"] > 0:
        return sonuc("iade-sikayet", _mutlak_guven(puanlar["iade-sikayet"]))

    # 4) Puanlama
    adaylar = sorted(
        ((puanlar[k], k) for k in ONCELIK if puanlar[k] > 0),
        key=lambda pk: (-pk[0], ONCELIK.index(pk[1])),
    )
    if adaylar:
        s1, kazanan = adaylar[0]
        s2 = adaylar[1][0] if len(adaylar) > 1 else 0.0
        return sonuc(kazanan, _karsilastirmali_guven(s1, s2))

    # 5) Hiçbir kural eşleşmedi
    return sonuc("diger", 0.2, ETIKET_ESLESME_YOK)

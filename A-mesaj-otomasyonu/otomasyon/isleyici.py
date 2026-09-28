"""Politika katmanı: sınıflandırma sonucunu temsilciye gidecek iş kaydına (Talep) çevirir.

Güvenlik sınırları burada kodla sabitlenir; serbest metin üretimi yoktur:
  * Hassas konular (istenmeyen-etki, iade-sikayet) → her zaman devret, yalnızca onaylı şablon.
    Ürün önerisi, tedavi ya da teşhis içeren yanıt üretilmez.
  * Güven < DUSUK_GUVEN_ESIGI veya çoklu niyet → devret + "Düşük Güven Skoru / Çoklu Niyet" notu.
  * Spam → yanıt üretilmez, devredilmez.
Her Talep, dışarı verilmeden önce `politika_denetimi` ile tekrar doğrulanır; ileride eklenecek
taslak üreticileri (sipariş sorgusu, ürün arama) bu sınırları delemez.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .siniflandirici import (
    DUSUK_GUVEN_ESIGI,
    ETIKET_SPAM,
    HASSAS_KONULAR,
    KONULAR,
    Siniflandirma,
    siniflandir,
)

# İkinci bir konu, kazanan konunun puanının en az bu oranına ulaşıyorsa ve kendi başına
# güçlü bir sinyal taşıyorsa (tek bir zayıf ürün adı değil) çoklu niyet sayılır.
COKLU_NIYET_ORANI = 0.5
COKLU_NIYET_MIN_PUAN = 2.0

ONAYLI_SABLONLAR: Dict[str, str] = {
    "istenmeyen-etki": (
        "Merhaba, yaşadığınız durum adına üzgünüz. Mesajınızı uzman ekibimize ilettik; "
        "uzman temsilcimiz konuyu ivedilikle inceleyerek size en kısa sürede dönüş yapacaktır."
    ),
    "iade-sikayet": (
        "Merhaba, yaşadığınız durum adına üzgünüz. Talebiniz ilgili ekibimize iletildi; "
        "uzman temsilcimiz konuyu ivedilikle inceleyerek size en kısa sürede dönüş yapacaktır."
    ),
}

DEVIR_SABLONU = (
    "Merhaba, mesajınız için teşekkür ederiz. Talebiniz ilgili temsilcimize iletildi; "
    "en kısa sürede size dönüş yapılacaktır."
)

# Hassas konulardaki yanıtta asla geçmemesi gereken ifadeler (öneri / tedavi / teşhis).
YASAKLI_IFADELER: Tuple[str, ...] = (
    "öner", "tavsiye", "kullanın", "kullanmay", "sürün", "uygulayın", "tedavi", "teşhis",
    "ilaç", "krem", "serum", "doktor", "alerji", "reaksiyon", "normaldir", "geçer",
)


class PolitikaIhlali(Exception):
    """Bir Talep güvenlik politikasını çiğniyorsa fırlatılır."""


@dataclass
class Talep:
    id: int
    konu: str
    devret: bool
    cevap_taslagi: Optional[str]
    notlar: List[str] = field(default_factory=list)
    siniflandirma: Optional[Siniflandirma] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """talepler.json biçimi: { id, konu, devret, cevap_taslagi, not }"""
        return {
            "id": self.id,
            "konu": self.konu,
            "devret": self.devret,
            "cevap_taslagi": self.cevap_taslagi,
            "not": " | ".join(self.notlar),
        }


def coklu_niyet(s: Siniflandirma) -> Tuple[str, ...]:
    """Kazanan konuyla yarışan güçlü ikincil konular (yoksa boş)."""
    kazanan = s.puan(s.konu)
    if kazanan <= 0:
        return ()
    return tuple(
        k for k in s.ikincil_konular
        if s.puan(k) >= COKLU_NIYET_MIN_PUAN and s.puan(k) / kazanan >= COKLU_NIYET_ORANI
    )


def politika_denetimi(talep: Talep) -> None:
    if talep.konu not in KONULAR:
        raise PolitikaIhlali(f"#{talep.id}: bilinmeyen konu {talep.konu!r}")
    if talep.konu in HASSAS_KONULAR:
        if not talep.devret:
            raise PolitikaIhlali(f"#{talep.id}: hassas konu devredilmeden bırakıldı")
        if talep.cevap_taslagi != ONAYLI_SABLONLAR[talep.konu]:
            raise PolitikaIhlali(f"#{talep.id}: hassas konuda onaysız cevap taslağı")
    taslak = (talep.cevap_taslagi or "").lower()
    if talep.konu in HASSAS_KONULAR and any(ifade in taslak for ifade in YASAKLI_IFADELER):
        raise PolitikaIhlali(f"#{talep.id}: hassas yanıtta yasaklı ifade")


def isle(kayit: Mapping[str, Any]) -> Talep:
    s = siniflandir(kayit["mesaj"])
    talep = Talep(id=kayit["id"], konu=s.konu, devret=False, cevap_taslagi=None, siniflandirma=s)

    if s.hassas:
        talep.devret = True
        talep.cevap_taslagi = ONAYLI_SABLONLAR[s.konu]
        talep.notlar.append(
            f"Hassas konu ({s.konu}): uzman temsilciye devredildi; öneri/teşhis içeren yanıt üretilmedi."
        )
        if s.konu == "istenmeyen-etki":
            talep.notlar.append("İstenmeyen etki kaydı (kozmetovijilans) açılmalı.")
    elif s.etiket == ETIKET_SPAM:
        talep.notlar.append("Spam/İlgisiz: yanıt üretilmedi, mesajdaki linke tıklanmamalı.")
    else:
        nedenler = []
        if s.guven < DUSUK_GUVEN_ESIGI:
            nedenler.append(f"Düşük Güven Skoru ({s.guven:.2f})")
        rakipler = coklu_niyet(s)
        if rakipler:
            nedenler.append("Çoklu Niyet: " + " + ".join((s.konu,) + rakipler))
        if nedenler:
            talep.devret = True
            talep.cevap_taslagi = DEVIR_SABLONU
            talep.notlar.append("Otomatik devir — " + "; ".join(nedenler))
        else:
            talep.notlar.append("Cevap taslağı sonraki adımda (sipariş sorgusu / ürün arama) üretilecek.")

    if s.siparis_numaralari:
        talep.notlar.append("Sipariş no: " + ", ".join(map(str, s.siparis_numaralari)))

    politika_denetimi(talep)
    return talep

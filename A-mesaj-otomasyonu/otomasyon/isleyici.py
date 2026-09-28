"""Politika katmanı: sınıflandırma sonucunu temsilciye gidecek iş kaydına (Talep) çevirir.

Güvenlik sınırları burada kodla sabitlenir; serbest metin üretimi yoktur:
  * Hassas konular (istenmeyen-etki, iade-sikayet) → her zaman devret, yalnızca onaylı şablon.
    Ürün önerisi, tedavi ya da teşhis içeren yanıt üretilmez.
  * Güven < DUSUK_GUVEN_ESIGI veya çoklu niyet → devret + "Düşük Güven Skoru / Çoklu Niyet" notu.
  * Spam → yanıt üretilmez, devredilmez.
  * siparis-durumu → DummyJSON'dan sepet çekilir; userId ≠ musteri_id ise hiçbir sipariş bilgisi
    paylaşılmaz, devret + güvenlik notu. Bulunamayan siparişle yetkisiz sipariş müşteriye AYNI
    metinle yanıtlanır: dışarıdan bakan biri numaraları deneyerek hangi siparişlerin var olduğunu
    öğrenemez (sipariş numarası taraması / enumeration koruması).
Her Talep, dışarı verilmeden önce `politika_denetimi` ile tekrar doğrulanır; ileride eklenecek
taslak üreticileri (sipariş sorgusu, ürün arama) bu sınırları delemez.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .api import DummyJSONIstemcisi, SepetIstemcisi, SorguDurumu, dogrula, siparis_bilgi_metni
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

GUVENLIK_UYARISI = (
    "GÜVENLİK UYARISI: Sipariş sahibi (userId) ile müşteri (musteri_id) eşleşmiyor"
    " - Yetkisiz sorgulama engellendi"
)

# Hem bulunamayan hem de başka müşteriye ait sipariş için kullanılır (enumeration koruması).
SIPARIS_BULUNAMADI_SABLONU = (
    "Merhaba, {no} numaralı sipariş hesabınızla eşleşen kayıtlarımızda bulunamadı. "
    "Sipariş numaranızı kontrol ederek tekrar iletebilir misiniz? "
    "Dilerseniz müşteri temsilcimiz de size yardımcı olacaktır."
)

SIPARIS_NO_ISTEME_SABLONU = (
    "Merhaba, siparişinizi kontrol edebilmemiz için sipariş numaranızı paylaşır mısınız?"
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
    if any(n.startswith(GUVENLIK_UYARISI) for n in talep.notlar) and not talep.devret:
        raise PolitikaIhlali(f"#{talep.id}: yetkisiz sipariş sorgusu devredilmeden bırakıldı")
    taslak = (talep.cevap_taslagi or "").lower()
    if talep.konu in HASSAS_KONULAR and any(ifade in taslak for ifade in YASAKLI_IFADELER):
        raise PolitikaIhlali(f"#{talep.id}: hassas yanıtta yasaklı ifade")


_varsayilan_istemci: Optional[DummyJSONIstemcisi] = None


def _istemci_al() -> DummyJSONIstemcisi:
    global _varsayilan_istemci
    if _varsayilan_istemci is None:
        _varsayilan_istemci = DummyJSONIstemcisi()
    return _varsayilan_istemci


def _siparis_durumu(talep: Talep, musteri_id: Any, numaralar: Sequence[int],
                    istemci: SepetIstemcisi) -> None:
    """siparis-durumu mesajı için sepeti çeker, sahipliği doğrular, taslak ve notu doldurur."""
    if not numaralar:
        if not talep.devret:
            talep.cevap_taslagi = SIPARIS_NO_ISTEME_SABLONU
        talep.notlar.append("Mesajda sipariş numarası yok; müşteriden istendi.")
        return

    no_metni = ", ".join(map(str, numaralar))
    sorgular = [istemci.sepet_getir(n) for n in numaralar]
    bulunanlar = [q for q in sorgular if q.durum is SorguDurumu.BULUNDU]

    # 1) Sahiplik: tek bir yetkisiz sepet bile varsa hiçbir sipariş bilgisi paylaşılmaz.
    yetkisiz = [q.sepet_id for q in bulunanlar if dogrula(q.sepet, musteri_id) is None]
    if yetkisiz:
        talep.devret = True
        talep.cevap_taslagi = SIPARIS_BULUNAMADI_SABLONU.format(no=no_metni)
        talep.notlar.append(
            f"{GUVENLIK_UYARISI} (sorgulanan sipariş: #{', #'.join(map(str, yetkisiz))}, "
            f"musteri_id={musteri_id})"
        )
        return

    # 2) Sipariş sistemine ulaşılamadı: sessizce geçme, insana devret.
    hatalar = [q for q in sorgular if q.durum is SorguDurumu.HATA]
    if hatalar:
        talep.devret = True
        talep.cevap_taslagi = DEVIR_SABLONU
        talep.notlar.append("Sipariş sistemine ulaşılamadı: " + "; ".join(
            f"#{q.sepet_id} {q.hata}" for q in hatalar))
        return

    dogrulama_notlari = [
        f"Sipariş #{q.sepet_id}: " + ("sahiplik doğrulandı (userId = musteri_id)."
                                      if q.durum is SorguDurumu.BULUNDU else "sistemde bulunamadı.")
        for q in sorgular
    ]

    # 3) Başka bir sebeple zaten devredildiyse (çoklu niyet vb.) taslak nötr kalır.
    if talep.devret or len(sorgular) > 1:
        if not talep.devret:
            talep.devret = True
            talep.cevap_taslagi = DEVIR_SABLONU
            talep.notlar.append("Otomatik devir — birden fazla sipariş numarası")
        talep.notlar.extend(dogrulama_notlari)
        return

    sorgu = sorgular[0]
    if sorgu.durum is SorguDurumu.BULUNAMADI:
        talep.cevap_taslagi = SIPARIS_BULUNAMADI_SABLONU.format(no=no_metni)
        talep.notlar.append(f"Sipariş #{sorgu.sepet_id} sistemde bulunamadı (API: not found).")
        return

    talep.cevap_taslagi = siparis_bilgi_metni(dogrula(sorgu.sepet, musteri_id))
    talep.notlar.extend(dogrulama_notlari)
    talep.notlar.append("API kargo durumu içermiyor; takip bilgisi temsilci tarafından eklenmeli.")


def isle(kayit: Mapping[str, Any], istemci: Optional[SepetIstemcisi] = None) -> Talep:
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

        if s.konu == "siparis-durumu":
            _siparis_durumu(talep, kayit.get("musteri_id"), s.siparis_numaralari,
                            istemci or _istemci_al())
        elif not nedenler:
            talep.notlar.append("Cevap taslağı sonraki adımda (ürün arama) üretilecek.")

    if s.siparis_numaralari and s.konu != "siparis-durumu":
        talep.notlar.append("Mesajdaki sipariş no: " + ", ".join(map(str, s.siparis_numaralari))
                            + " (sahiplik doğrulanmadı)")

    politika_denetimi(talep)
    return talep

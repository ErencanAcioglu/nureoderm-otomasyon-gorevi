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
  * urun-sorusu / fiyat / diger → ürün arama (bonus) + doğrulanmış veri gerektirmeyen iddiasız taslak.
Mesaj bariz İngilizceyse (metin.dil_tespit) tüm taslaklar İngilizce üretilir.
Her Talep, dışarı verilmeden önce `politika_denetimi` ile tekrar doğrulanır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .api import DummyJSONIstemcisi, SepetIstemcisi, SorguDurumu, dogrula, siparis_bilgi_metni
from .metin import dil_tespit, normalize
from .sablonlar import DILLER, bilgi_taslagi, dogrulama_konulari, metinler
from .siniflandirici import (
    DUSUK_GUVEN_ESIGI,
    ETIKET_SPAM,
    HASSAS_KONULAR,
    KONULAR,
    Siniflandirma,
    siniflandir,
)
from .urun_arama import AramaSonucu, UrunAramaIstemcisi, urun_ara

# İkinci bir konu, kazanan konunun puanının en az bu oranına ulaşıyorsa ve kendi başına
# güçlü bir sinyal taşıyorsa (tek bir zayıf ürün adı değil) çoklu niyet sayılır.
COKLU_NIYET_ORANI = 0.5
COKLU_NIYET_MIN_PUAN = 2.0

ONAYLI_SABLONLAR: Dict[str, Dict[str, str]] = {
    dil: {konu: metinler(dil)[konu] for konu in HASSAS_KONULAR} for dil in DILLER
}
DEVIR_SABLONU = metinler("tr")["devir"]
SIPARIS_BULUNAMADI_SABLONU = metinler("tr")["siparis_bulunamadi"]

GUVENLIK_UYARISI = (
    "GÜVENLİK UYARISI: Sipariş sahibi (userId) ile müşteri (musteri_id) eşleşmiyor"
    " - Yetkisiz sorgulama engellendi"
)

# Hassas konulardaki yanıtta asla geçmemesi gereken ifadeler (öneri / tedavi / teşhis).
YASAKLI_IFADELER: Tuple[str, ...] = (
    "öner", "tavsiye", "kullanın", "kullanmay", "sürün", "uygulayın", "tedavi", "teşhis",
    "ilaç", "krem", "serum", "doktor", "alerji", "reaksiyon", "normaldir", "geçer",
    "recommend", "suggest", "apply", "treat", "diagnos", "medic", "cream", "doctor", "allerg",
    "reaction", "normal",
)


class PolitikaIhlali(Exception):
    """Bir Talep güvenlik politikasını çiğniyorsa fırlatılır."""


def _simdi() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class Talep:
    id: int
    konu: str
    devret: bool
    cevap_taslagi: Optional[str]
    notlar: List[str] = field(default_factory=list)
    dil: str = "tr"
    siniflandirma: Optional[Siniflandirma] = field(default=None, repr=False)
    kayit: Mapping[str, Any] = field(default_factory=dict, repr=False)
    islem_zamani: str = field(default_factory=_simdi)

    def to_dict(self) -> Dict[str, Any]:
        """talepler.json biçimi: { id, konu, devret, cevap_taslagi, not }"""
        return {
            "id": self.id,
            "konu": self.konu,
            "devret": self.devret,
            "cevap_taslagi": self.cevap_taslagi,
            "not": " | ".join(self.notlar),
        }

    def detay_dict(self) -> Dict[str, Any]:
        """talepler_detay.json biçimi: zorunlu alanlar + analitik alanlar."""
        s = self.siniflandirma
        return {
            **self.to_dict(),
            "kanal": self.kayit.get("kanal"),
            "musteri_id": self.kayit.get("musteri_id"),
            "mesaj": self.kayit.get("mesaj"),
            "dil": self.dil,
            "guven": s.guven if s else None,
            "etiket": s.etiket if s else None,
            "ikincil_konular": list(s.ikincil_konular) if s else [],
            "siparis_numaralari": list(s.siparis_numaralari) if s else [],
            "eslesen_kurallar": list(s.eslesen_kurallar) if s else [],
            "notlar": list(self.notlar),
            "islem_zamani": self.islem_zamani,
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
        if talep.cevap_taslagi != ONAYLI_SABLONLAR.get(talep.dil, {}).get(talep.konu):
            raise PolitikaIhlali(f"#{talep.id}: hassas konuda onaysız cevap taslağı")
    if any(n.startswith(GUVENLIK_UYARISI) for n in talep.notlar) and not talep.devret:
        raise PolitikaIhlali(f"#{talep.id}: yetkisiz sipariş sorgusu devredilmeden bırakıldı")
    taslak = (talep.cevap_taslagi or "").lower()
    if talep.konu in HASSAS_KONULAR and any(ifade in taslak for ifade in YASAKLI_IFADELER):
        raise PolitikaIhlali(f"#{talep.id}: hassas yanıtta yasaklı ifade")


_varsayilan_sepet_istemcisi: Optional[DummyJSONIstemcisi] = None
_varsayilan_urun_istemcisi: Optional[UrunAramaIstemcisi] = None


def _sepet_istemcisi() -> DummyJSONIstemcisi:
    global _varsayilan_sepet_istemcisi
    if _varsayilan_sepet_istemcisi is None:
        _varsayilan_sepet_istemcisi = DummyJSONIstemcisi()
    return _varsayilan_sepet_istemcisi


def _urun_istemcisi() -> UrunAramaIstemcisi:
    global _varsayilan_urun_istemcisi
    if _varsayilan_urun_istemcisi is None:
        _varsayilan_urun_istemcisi = UrunAramaIstemcisi()
    return _varsayilan_urun_istemcisi


def _siparis_durumu(talep: Talep, musteri_id: Any, numaralar: Sequence[int],
                    istemci: SepetIstemcisi) -> None:
    """siparis-durumu mesajı için sepeti çeker, sahipliği doğrular, taslak ve notu doldurur."""
    m = metinler(talep.dil)
    if not numaralar:
        if not talep.devret:
            talep.cevap_taslagi = m["siparis_no_iste"]
        talep.notlar.append("Mesajda sipariş numarası yok; müşteriden istendi.")
        return

    no_metni = ", ".join(map(str, numaralar))
    sorgular = [istemci.sepet_getir(n) for n in numaralar]
    bulunanlar = [q for q in sorgular if q.durum is SorguDurumu.BULUNDU]

    # 1) Sahiplik: tek bir yetkisiz sepet bile varsa hiçbir sipariş bilgisi paylaşılmaz.
    yetkisiz = [q.sepet_id for q in bulunanlar if dogrula(q.sepet, musteri_id) is None]
    if yetkisiz:
        talep.devret = True
        talep.cevap_taslagi = m["siparis_bulunamadi"].format(no=no_metni)
        talep.notlar.append(
            f"{GUVENLIK_UYARISI} (sorgulanan sipariş: #{', #'.join(map(str, yetkisiz))}, "
            f"musteri_id={musteri_id})"
        )
        return

    # 2) Sipariş sistemine ulaşılamadı: sessizce geçme, insana devret.
    hatalar = [q for q in sorgular if q.durum is SorguDurumu.HATA]
    if hatalar:
        talep.devret = True
        talep.cevap_taslagi = m["devir"]
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
            talep.cevap_taslagi = m["devir"]
            talep.notlar.append("Otomatik devir — birden fazla sipariş numarası")
        talep.notlar.extend(dogrulama_notlari)
        return

    sorgu = sorgular[0]
    if sorgu.durum is SorguDurumu.BULUNAMADI:
        talep.cevap_taslagi = m["siparis_bulunamadi"].format(no=no_metni)
        talep.notlar.append(f"Sipariş #{sorgu.sepet_id} sistemde bulunamadı (API: not found).")
        return

    talep.cevap_taslagi = siparis_bilgi_metni(dogrula(sorgu.sepet, musteri_id), talep.dil)
    talep.notlar.extend(dogrulama_notlari)
    talep.notlar.append("API kargo durumu içermiyor; kargo takip bilgisi temsilci tarafından eklenmeli.")


def _arama_notu(arama: AramaSonucu) -> str:
    sorgular = ", ".join(arama.sorgular)
    if arama.urunler:
        sonuc = "uygun eşleşme: " + ", ".join(f"{u.baslik} ({u.fiyat})" for u in arama.urunler)
    else:
        sonuc = "uygun eşleşme yok"
    if arama.elenenler:
        sonuc += " · alaka filtresiyle elenen: " + ", ".join(arama.elenenler)
    if arama.hata:
        sonuc += f" · arama hatası: {arama.hata}"
    return f"Ürün arama [{sorgular}] → {sonuc}"


def _bilgi_talebi(talep: Talep, s: Siniflandirma, mesaj: str,
                  urun_istemcisi: UrunAramaIstemcisi) -> None:
    """urun-sorusu / fiyat / genel diger: ürün arama + iddiasız taslak + temsilci notları."""
    arama = AramaSonucu((), (), ())
    if s.konu in ("urun-sorusu", "fiyat"):
        arama = urun_ara(normalize(mesaj), urun_istemcisi)
        if arama.arama_yapildi:
            talep.notlar.append(_arama_notu(arama))

    talep.cevap_taslagi = bilgi_taslagi(
        talep.dil, s.konu, s.eslesen_kurallar,
        [(u.baslik, u.fiyat) for u in arama.urunler], arama.arama_yapildi,
    )

    dogrulama = dogrulama_konulari(s.eslesen_kurallar)
    if dogrulama:
        adlar = {"k_icerik": "içerik/hacim", "k_cilt": "cilt tipi/kullanım", "k_hayvan": "hayvan testi"}
        talep.notlar.append("Doğrulanmamış iddia üretilmedi (" + ", ".join(adlar[k] for k in dogrulama)
                            + "); yanıt ürün verisiyle teyit edilmeli.")
    kurallar = set(s.eslesen_kurallar)
    if "fiyat:indirim" in kurallar:
        talep.notlar.append("Aktif indirim kodu / fiyat listesi temsilci tarafından teyit edilmeli.")
    if "diger:kargo-firmasi" in kurallar:
        talep.notlar.append("Anlaşmalı kargo firması adı temsilci tarafından eklenmeli.")


def isle(kayit: Mapping[str, Any], istemci: Optional[SepetIstemcisi] = None,
         urun_istemcisi: Optional[UrunAramaIstemcisi] = None) -> Talep:
    s = siniflandir(kayit["mesaj"])
    dil = dil_tespit(kayit["mesaj"])
    m = metinler(dil)
    talep = Talep(id=kayit["id"], konu=s.konu, devret=False, cevap_taslagi=None,
                  dil=dil, siniflandirma=s, kayit=kayit)

    if s.hassas:
        talep.devret = True
        talep.cevap_taslagi = ONAYLI_SABLONLAR[dil][s.konu]
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
            talep.cevap_taslagi = m["devir"]
            talep.notlar.append("Otomatik devir — " + "; ".join(nedenler))

        if s.konu == "siparis-durumu":
            _siparis_durumu(talep, kayit.get("musteri_id"), s.siparis_numaralari,
                            istemci or _sepet_istemcisi())
        elif not nedenler:
            _bilgi_talebi(talep, s, kayit["mesaj"], urun_istemcisi or _urun_istemcisi())

    if s.siparis_numaralari and s.konu != "siparis-durumu":
        talep.notlar.append("Mesajdaki sipariş no: " + ", ".join(map(str, s.siparis_numaralari))
                            + " (sahiplik doğrulanmadı)")
    if dil == "en":
        talep.notlar.append("Dil: İngilizce — taslak İngilizce üretildi.")

    politika_denetimi(talep)
    return talep

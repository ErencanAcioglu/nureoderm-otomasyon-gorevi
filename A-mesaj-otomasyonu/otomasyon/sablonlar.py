"""Müşteriye giden tüm metinler (TR / EN) tek yerde.

Metinler bilerek iddiasızdır: içerik, cilt tipine uygunluk, hayvan testi, kargo firması gibi
doğrulanmış verisi olmayan konularda bilgi uydurulmaz; müşteriden ürün adı istenir ve
temsilciye not düşülür. Hassas konu şablonları `isleyici.politika_denetimi` ile korunur.
"""

from __future__ import annotations

from typing import Dict, Iterable, Sequence, Tuple

DILLER = ("tr", "en")
PARA_BIRIMI = "USD"  # DummyJSON para birimi belirtmiyor; mağaza verisi USD varsayılır.

METINLER: Dict[str, Dict[str, str]] = {
    "tr": {
        # --- hassas konular (onaylı, değiştirilemez) ---
        "istenmeyen-etki": (
            "Merhaba, yaşadığınız durum adına üzgünüz. Mesajınızı uzman ekibimize ilettik; "
            "uzman temsilcimiz konuyu ivedilikle inceleyerek size en kısa sürede dönüş yapacaktır."
        ),
        "iade-sikayet": (
            "Merhaba, yaşadığınız durum adına üzgünüz. Talebiniz ilgili ekibimize iletildi; "
            "uzman temsilcimiz konuyu ivedilikle inceleyerek size en kısa sürede dönüş yapacaktır."
        ),
        # --- devir / sipariş ---
        "devir": (
            "Merhaba, mesajınız için teşekkür ederiz. Talebiniz ilgili temsilcimize iletildi; "
            "en kısa sürede size dönüş yapılacaktır."
        ),
        "siparis_bulunamadi": (
            "Merhaba, {no} numaralı sipariş hesabınızla eşleşen kayıtlarımızda bulunamadı. "
            "Sipariş numaranızı kontrol ederek tekrar iletebilir misiniz? "
            "Dilerseniz müşteri temsilcimiz de size yardımcı olacaktır."
        ),
        "siparis_no_iste": (
            "Merhaba, siparişinizi kontrol edebilmemiz için sipariş numaranızı paylaşır mısınız?"
        ),
        "siparis_baslik": "Merhaba, {no} numaralı siparişiniz sistemimizde kayıtlı. Sipariş içeriği:",
        "siparis_toplam": "Toplam tutar: {tutar}",
        "siparis_kargo": "Kargo takip bilgisi hazır olduğunda size ayrıca iletilecektir.",
        # --- çoklu niyet: sipariş kısmı yanıtlandı, kalan kısım temsilcide ---
        "kismi_devir": "{konular} sorunuzu ilgili temsilcimize ilettik; en kısa sürede size dönüş yapılacaktır.",
        "kismi_devir_genel": (
            "Mesajınızın diğer kısmını ilgili temsilcimize ilettik; en kısa sürede size dönüş yapılacaktır."
        ),
        "ka_fiyat": "fiyat", "ka_urun-sorusu": "ürün", "ka_diger": "diğer",
        # --- ürün / fiyat / genel bilgi ---
        "selam": "Merhaba, sorunuz için teşekkür ederiz.",
        "urun_bulundu": "Kataloğumuzda sorunuzla eşleşen ürünler:",
        "urun_eslesmedi": "Sorduğunuz ürünü kataloğumuzda birebir eşleştiremedik.",
        "indirim": "Güncel kampanya ve indirim kodlarımızı web sitemizin kampanyalar bölümünden takip edebilirsiniz.",
        "dogrulama": (
            "{konular} konusunda doğrulanmış bilgiyi iletebilmemiz için "
            "ilgilendiğiniz ürünün tam adını paylaşır mısınız?"
        ),
        "urun_adi_iste": "İlgilendiğiniz ürünün tam adını paylaşırsanız güncel bilgiyi hemen iletelim.",
        "kargo_firmasi": (
            "Siparişiniz kargoya verildiğinde kargo firması ve takip numarası bilgisi tarafınıza iletilir."
        ),
        "magaza": "İletişim ve mağaza bilgilerimize web sitemizin iletişim sayfasından ulaşabilirsiniz.",
        "kapanis": "Başka bir konuda yardımcı olabileceğimiz bir şey olursa bize yazabilirsiniz.",
        # --- doğrulama konusu adları ---
        "k_icerik": "ürün içeriği ve hacmi",
        "k_cilt": "cilt tipine uygunluk ve kullanım",
        "k_hayvan": "hayvan deneyi politikası",
        "ve": " ve ",
    },
    "en": {
        "istenmeyen-etki": (
            "Hello, we are sorry to hear about your experience. Your message has been forwarded to our "
            "specialist team; a specialist representative will review it promptly and get back to you "
            "as soon as possible."
        ),
        "iade-sikayet": (
            "Hello, we are sorry to hear about your experience. Your request has been forwarded to the "
            "relevant team; a specialist representative will review it promptly and get back to you "
            "as soon as possible."
        ),
        "devir": (
            "Hello, thank you for your message. Your request has been forwarded to one of our "
            "representatives, who will get back to you as soon as possible."
        ),
        "siparis_bulunamadi": (
            "Hello, we could not find order #{no} among the records linked to your account. "
            "Could you please double-check your order number and send it again? "
            "One of our representatives will also be happy to help."
        ),
        "siparis_no_iste": "Hello, could you please share your order number so we can check your order?",
        "siparis_baslik": "Hello, your order #{no} has been verified. Items:",
        "siparis_toplam": "Total: {tutar}",
        "siparis_kargo": "We will send you the tracking details as soon as your shipment is ready.",
        "kismi_devir": (
            "Your {konular} question has been forwarded to one of our representatives, "
            "who will get back to you as soon as possible."
        ),
        "kismi_devir_genel": (
            "The rest of your message has been forwarded to one of our representatives, "
            "who will get back to you as soon as possible."
        ),
        "ka_fiyat": "pricing", "ka_urun-sorusu": "product", "ka_diger": "other",
        "selam": "Hello, thank you for your question.",
        "urun_bulundu": "Products in our catalogue matching your question:",
        "urun_eslesmedi": "We could not find an exact match for this product in our catalogue.",
        "indirim": "You can follow our current campaigns and discount codes in the campaigns section of our website.",
        "dogrulama": (
            "To share verified information about {konular}, could you please tell us the full name "
            "of the product you are interested in?"
        ),
        "urun_adi_iste": "If you share the full product name, we will send you up-to-date details right away.",
        "kargo_firmasi": "Once your order is shipped, the carrier name and tracking number will be sent to you.",
        "magaza": "You can find our contact and store details on the contact page of our website.",
        "kapanis": "Please feel free to write to us if there is anything else we can help with.",
        "k_icerik": "ingredients and volume",
        "k_cilt": "skin-type suitability and usage",
        "k_hayvan": "our animal testing policy",
        "ve": " and ",
    },
}

# Sınıflandırıcı kural adı → doğrulama gerektiren alt konu
DOGRULAMA_KURALLARI: Dict[str, str] = {
    "urun-sorusu:icerik": "k_icerik", "urun-sorusu:bilesen": "k_icerik", "urun-sorusu:hacim": "k_icerik",
    "urun-sorusu:cilt-tipi": "k_cilt", "urun-sorusu:uygunluk": "k_cilt", "urun-sorusu:kullanim": "k_cilt",
    "urun-sorusu:hayvan-testi": "k_hayvan",
}


def metinler(dil: str) -> Dict[str, str]:
    return METINLER.get(dil, METINLER["tr"])


def tutar_bicimle(deger: float, dil: str = "tr") -> str:
    """tr: 1.467,88 USD · en: 1,467.88 USD"""
    metin = f"{deger:,.2f}"
    if dil != "en":
        metin = metin.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{metin} {PARA_BIRIMI}"


def kismi_devir_metni(dil: str, konular: Sequence[str]) -> str:
    """Çoklu niyette temsilciye bırakılan konular için tek cümle (ör. 'Fiyat sorunuzu … ilettik')."""
    m = metinler(dil)
    adlar = [m[f"ka_{k}"] for k in konular if f"ka_{k}" in m]
    if not adlar:
        return m["kismi_devir_genel"]
    metin = m["ve"].join(adlar)
    return m["kismi_devir"].format(konular=metin[0].upper() + metin[1:] if dil == "tr" else metin)


def dogrulama_konulari(kural_adlari: Iterable[str]) -> Tuple[str, ...]:
    """Eşleşen kurallardan, doğrulanmış veri gerektiren alt konuları (sırayı koruyarak) çıkarır."""
    konular = []
    for kural in kural_adlari:
        anahtar = DOGRULAMA_KURALLARI.get(kural)
        if anahtar and anahtar not in konular:
            konular.append(anahtar)
    return tuple(konular)


def bilgi_taslagi(dil: str, konu: str, kural_adlari: Sequence[str],
                  urunler: Sequence[Tuple[str, float]], arama_yapildi: bool) -> str:
    """urun-sorusu / fiyat / genel 'diger' için iddiasız cevap taslağı."""
    m = metinler(dil)
    kurallar = set(kural_adlari)
    parcalar = [m["selam"]]

    if urunler:
        parcalar.append(m["urun_bulundu"] + "\n" + "\n".join(
            f"• {baslik} — {tutar_bicimle(fiyat, dil)}" for baslik, fiyat in urunler))
    elif arama_yapildi:
        parcalar.append(m["urun_eslesmedi"])

    if "fiyat:indirim" in kurallar:
        parcalar.append(m["indirim"])
    if "diger:kargo-firmasi" in kurallar:
        parcalar.append(m["kargo_firmasi"])
    if "diger:magaza-bilgisi" in kurallar:
        parcalar.append(m["magaza"])

    dogrulama = dogrulama_konulari(kural_adlari)
    if dogrulama:
        konular = m["ve"].join(m[k] for k in dogrulama)
        parcalar.append(m["dogrulama"].format(konular=konular[0].upper() + konular[1:]
                                               if dil == "tr" else konular))
    elif konu in ("urun-sorusu", "fiyat") and not urunler:
        parcalar.append(m["urun_adi_iste"])

    parcalar.append(m["kapanis"])
    return "\n".join(parcalar)

"""Raporlama: ANSI terminal özeti ve tek sayfalık HTML dashboard (ozet.html).

HTML tamamen bağımsızdır (dış font/JS/CSS yok, çevrimdışı açılır). Müşteri mesajları sayfaya
JSON olarak gömülür ve DOM'a yalnızca `textContent` ile yazılır; mesaj içeriği HTML/JS olarak
yorumlanamaz (XSS koruması).
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .isleyici import GUVENLIK_UYARISI, Talep
from .siniflandirici import ETIKET_SPAM, KONULAR


@dataclass(frozen=True)
class Istatistik:
    toplam: int
    devredilen: int
    otomatik: int
    guvenlik_engeli: int
    spam: int
    ortalama_guven: float
    konu_adet: Dict[str, int]
    konu_devir: Dict[str, int]
    diller: Dict[str, int]


def istatistik(talepler: Sequence[Talep]) -> Istatistik:
    konu_adet = Counter(t.konu for t in talepler)
    konu_devir = Counter(t.konu for t in talepler if t.devret)
    guvenler = [t.siniflandirma.guven for t in talepler if t.siniflandirma]
    return Istatistik(
        toplam=len(talepler),
        devredilen=sum(t.devret for t in talepler),
        otomatik=sum(1 for t in talepler if not t.devret and t.cevap_taslagi),
        guvenlik_engeli=sum(1 for t in talepler if any(n.startswith(GUVENLIK_UYARISI) for n in t.notlar)),
        spam=sum(1 for t in talepler if t.siniflandirma and t.siniflandirma.etiket == ETIKET_SPAM),
        ortalama_guven=round(sum(guvenler) / len(guvenler), 2) if guvenler else 0.0,
        konu_adet={k: konu_adet[k] for k in KONULAR},
        konu_devir={k: konu_devir[k] for k in KONULAR},
        diller=dict(Counter(t.dil for t in talepler)),
    )


# --------------------------------------------------------------------------- terminal

_ANSI = {"kalin": "1", "soluk": "2", "kirmizi": "31", "yesil": "32", "sari": "33",
         "mavi": "34", "mor": "35", "camgobegi": "36", "gri": "90"}
KONU_RENGI = {"urun-sorusu": "mavi", "fiyat": "mor", "siparis-durumu": "camgobegi",
              "iade-sikayet": "sari", "istenmeyen-etki": "kirmizi", "diger": "gri"}


def renk_destekleniyor(akis=sys.stdout) -> bool:
    return "NO_COLOR" not in os.environ and hasattr(akis, "isatty") and akis.isatty()


def terminal_ozeti(talepler: Sequence[Talep], renk: Optional[bool] = None) -> str:
    renk = renk_destekleniyor() if renk is None else renk

    def r(metin: str, *stiller: str) -> str:
        if not renk:
            return metin
        return "\033[" + ";".join(_ANSI[s] for s in stiller) + "m" + metin + "\033[0m"

    ist = istatistik(talepler)
    genislik = 30
    en_cok = max(ist.konu_adet.values()) or 1
    oran = f"%{round(100 * ist.devredilen / ist.toplam)}" if ist.toplam else "%0"

    satirlar = [
        "",
        r(" NUREODERM · MÜŞTERİ MESAJI ÖZETİ ", "kalin", "camgobegi"),
        r("─" * 64, "gri"),
        f"  Toplam mesaj     {r(str(ist.toplam), 'kalin')}",
        f"  Devredilen       {r(str(ist.devredilen), 'kalin', 'kirmizi')} ({oran})",
        f"  Otomatik taslak  {r(str(ist.otomatik), 'kalin', 'yesil')}",
        f"  Güvenlik engeli  {r(str(ist.guvenlik_engeli), 'kalin', 'sari')}   "
        f"Spam {r(str(ist.spam), 'kalin')}   Ort. güven {r(f'{ist.ortalama_guven:.2f}', 'kalin')}",
        "",
        r(f"  {'KONU':<17}{'ADET':>5}{'DEVİR':>7}   DAĞILIM", "kalin"),
    ]
    for konu in KONULAR:
        adet, devir = ist.konu_adet[konu], ist.konu_devir[konu]
        dolu = round(genislik * adet / en_cok)
        devir_dolu = round(genislik * devir / en_cok)
        cubuk = r("█" * (dolu - devir_dolu), KONU_RENGI[konu]) + r("▓" * devir_dolu, "kirmizi")
        cubuk += r("·" * (genislik - dolu), "gri")
        devir_metni = r(f"{devir:>7}", "kirmizi") if devir else f"{devir:>7}"
        satirlar.append(f"  {r(f'{konu:<17}', KONU_RENGI[konu])}{adet:>5}{devir_metni}   {cubuk}")
    satirlar += [
        r("─" * 64, "gri"),
        f"  {'TOPLAM':<17}{ist.toplam:>5}{ist.devredilen:>7}   "
        + r("▓", "kirmizi") + r(" = devredilen", "gri"),
        "",
        r("  Devredilen mesajlar:", "kalin"),
    ]
    for t in talepler:
        if t.devret:
            neden = t.notlar[0] if t.notlar else ""
            satirlar.append(f"   {r(f'#{t.id:<3}', 'kirmizi')} {t.konu:<16} {neden[:70]}")
    satirlar.append(
        "  " + r("Diller: ", "gri") + " · ".join(f"{d} {n}" for d, n in sorted(ist.diller.items()))
    )
    return "\n".join(satirlar)


# --------------------------------------------------------------------------- html

def html_ozeti(talepler: Sequence[Talep], olusturulma: str) -> str:
    ist = istatistik(talepler)
    veri = {
        "olusturulma": olusturulma,
        "konular": list(KONULAR),
        "istatistik": ist.__dict__,
        "talepler": [t.detay_dict() for t in talepler],
    }
    # </script> kaçışı: gömülü JSON sayfa yapısını bozamaz.
    gomulu = json.dumps(veri, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    return _HTML_SABLONU.replace("__VERI__", gomulu)


_HTML_SABLONU = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mesaj Özeti · Nureoderm</title>
<style>
:root {
  --bg: #f6f7f9; --panel: #ffffff; --panel-2: #f1f3f6; --text: #111827; --muted: #6b7280;
  --line: #e5e7eb; --accent: #0f766e; --danger: #dc2626; --danger-bg: #fef2f2;
  --ok: #15803d; --ok-bg: #f0fdf4; --warn: #b45309; --warn-bg: #fffbeb;
  --k-urun-sorusu: #2563eb; --k-fiyat: #7c3aed; --k-siparis-durumu: #0d9488;
  --k-iade-sikayet: #d97706; --k-istenmeyen-etki: #e11d48; --k-diger: #64748b;
  --shadow: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08);
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0b0f14; --panel: #121821; --panel-2: #18202b; --text: #e5e7eb; --muted: #9ca3af;
    --line: #243040; --accent: #2dd4bf; --danger: #f87171; --danger-bg: #2a1215;
    --ok: #4ade80; --ok-bg: #0f2418; --warn: #fbbf24; --warn-bg: #2a2110;
    --k-urun-sorusu: #60a5fa; --k-fiyat: #a78bfa; --k-siparis-durumu: #2dd4bf;
    --k-iade-sikayet: #fbbf24; --k-istenmeyen-etki: #fb7185; --k-diger: #94a3b8;
    --shadow: none; color-scheme: dark;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
.kap { max-width: 1180px; margin: 0 auto; padding: 28px 16px 48px; }
header { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 8px 24px; margin-bottom: 20px; }
h1 { margin: 0; font-size: 24px; letter-spacing: -.01em; }
.alt { color: var(--muted); font-size: 13px; }
.kartlar { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 16px; }
.kart { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; box-shadow: var(--shadow); }
.kart .etiket { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.kart .deger { font-size: 28px; font-weight: 650; margin-top: 2px; font-variant-numeric: tabular-nums; }
.kart .ek { color: var(--muted); font-size: 12px; }
.kart.kirmizi .deger { color: var(--danger); } .kart.yesil .deger { color: var(--ok); } .kart.sari .deger { color: var(--warn); }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 16px; box-shadow: var(--shadow); }
.izgara { display: grid; grid-template-columns: 1.3fr 1fr; gap: 12px; margin-bottom: 16px; }
@media (max-width: 860px) { .izgara { grid-template-columns: 1fr; } }
h2 { font-size: 15px; margin: 0 0 12px; }
.dagilim { display: grid; gap: 9px; }
.dsatir { display: grid; grid-template-columns: 128px 1fr 64px; align-items: center; gap: 10px; font-size: 13px; }
.cubuk { height: 12px; background: var(--panel-2); border-radius: 6px; overflow: hidden; display: flex; }
.cubuk span { display: block; height: 100%; }
.cubuk .dv { background: repeating-linear-gradient(135deg, var(--danger) 0 4px, transparent 4px 7px); opacity: .9; }
.sayi { text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }
.lejant { display: flex; gap: 16px; color: var(--muted); font-size: 12px; margin-top: 12px; }
.lejant i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; background: var(--muted); }
.lejant i.dv { background: repeating-linear-gradient(135deg, var(--danger) 0 3px, transparent 3px 5px); }
.dikkat { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.dikkat li { display: grid; grid-template-columns: 38px 1fr; gap: 8px; font-size: 13px; }
.dikkat b { color: var(--danger); font-variant-numeric: tabular-nums; }
.dikkat span { color: var(--muted); }
.dikkat .konu { display: flex; margin-bottom: 2px; }
.dikkat .konu span { color: var(--text); }
.filtre { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.cip { border: 1px solid var(--line); background: var(--panel); color: var(--text); border-radius: 999px; padding: 5px 12px;
  font: inherit; font-size: 13px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.cip[aria-pressed="true"] { background: var(--text); color: var(--bg); border-color: var(--text); }
.cip .n { opacity: .65; font-variant-numeric: tabular-nums; }
.nokta { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none; }
.bosluk { flex: 1; }
select, input[type=search] { font: inherit; font-size: 13px; color: var(--text); background: var(--panel);
  border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px; }
input[type=search] { min-width: 220px; }
@media (max-width: 560px) { input[type=search] { min-width: 0; width: 100%; } .bosluk { display: none; } }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th { text-align: left; font-weight: 600; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
  padding: 8px 10px; border-bottom: 1px solid var(--line); }
td { padding: 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
tr.satir { cursor: pointer; } tr.satir:hover td { background: var(--panel-2); }
tr.satir:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.konu { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; font-weight: 550; }
.rozet { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.rozet.devret { color: var(--danger); background: var(--danger-bg); }
.rozet.oto { color: var(--ok); background: var(--ok-bg); }
.rozet.sessiz { color: var(--muted); background: var(--panel-2); }
.rozet.guv { color: var(--warn); background: var(--warn-bg); margin-left: 4px; }
.guven { display: flex; align-items: center; gap: 8px; font-variant-numeric: tabular-nums; }
.guven .cubuk { width: 54px; height: 6px; }
.guven .cubuk span { background: var(--accent); }
.mesaj { max-width: 420px; }
.kucuk { color: var(--muted); font-size: 12px; }
tr.detay td { background: var(--panel-2); }
.detay-izgara { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 760px) { .detay-izgara { grid-template-columns: 1fr; } }
.detay h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin: 0 0 6px; }
.taslak { white-space: pre-wrap; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; margin: 0; font: inherit; }
.notlar { margin: 0; padding-left: 18px; } .notlar li { margin-bottom: 4px; }
.notlar li.uyari { color: var(--danger); font-weight: 600; }
.bos { text-align: center; color: var(--muted); padding: 28px; }
@media (max-width: 720px) {
  thead { display: none; }
  table, tbody, tr, td { display: block; width: 100%; }
  tr.satir { border-bottom: 1px solid var(--line); padding: 10px 0; }
  tr.satir td { border: 0; padding: 3px 4px; }
  td[data-b]::before { content: attr(data-b); display: inline-block; min-width: 72px; color: var(--muted); font-size: 12px; }
  .mesaj { max-width: none; }
  td .guven { display: inline-flex; }
}
footer { color: var(--muted); font-size: 12px; margin-top: 16px; }
</style>
</head>
<body>
<div class="kap">
  <header>
    <div>
      <h1>Müşteri Mesajı Özeti</h1>
      <div class="alt">Nureoderm · WhatsApp &amp; Instagram · <span id="zaman"></span></div>
    </div>
    <div class="alt">Kaynak: mesajlar.json · Sipariş verisi: DummyJSON</div>
  </header>

  <section class="kartlar" id="kartlar"></section>

  <section class="izgara">
    <div class="panel">
      <h2>Konu dağılımı</h2>
      <div class="dagilim" id="dagilim"></div>
      <div class="lejant"><span><i></i>Otomatik taslak</span><span><i class="dv"></i>Devredilen</span></div>
    </div>
    <div class="panel">
      <h2>Temsilci bekleyenler</h2>
      <ul class="dikkat" id="dikkat"></ul>
    </div>
  </section>

  <section class="panel">
    <div class="filtre" id="konuFiltre" role="group" aria-label="Konu filtresi"></div>
    <div class="filtre">
      <select id="durum" aria-label="Durum filtresi">
        <option value="hepsi">Tüm durumlar</option>
        <option value="devret">Yalnızca devredilenler</option>
        <option value="oto">Yalnızca otomatik taslaklar</option>
      </select>
      <span class="bosluk"></span>
      <input type="search" id="ara" placeholder="Mesaj, not veya taslakta ara…" aria-label="Ara">
    </div>
    <table>
      <thead><tr><th>#</th><th>Kanal</th><th>Konu</th><th>Güven</th><th>Durum</th><th>Mesaj</th></tr></thead>
      <tbody id="govde"></tbody>
    </table>
    <div class="kucuk" style="margin-top:10px">Satıra tıklayarak cevap taslağını ve temsilci notlarını açın.</div>
  </section>
  <footer>Otomatik üretildi · Güven skoru deterministik kural puanıdır, olasılık değildir.</footer>
</div>

<script id="veri" type="application/json">__VERI__</script>
<script>
(function () {
  "use strict";
  var V = JSON.parse(document.getElementById("veri").textContent);
  var T = V.talepler, S = V.istatistik;
  var durum = { konu: "hepsi", filtre: "hepsi", q: "" };
  var acik = {};

  function el(etiket, ozellik, cocuklar) {
    var d = document.createElement(etiket);
    if (ozellik) for (var k in ozellik) {
      if (k === "text") d.textContent = ozellik[k];
      else if (k === "style") d.style.cssText = ozellik[k];
      else d.setAttribute(k, ozellik[k]);
    }
    (cocuklar || []).forEach(function (c) { if (c) d.appendChild(c); });
    return d;
  }
  function renk(konu) { return "var(--k-" + konu + ")"; }
  function nokta(konu) { return el("span", { "class": "nokta", style: "background:" + renk(konu) }); }

  var z = new Date(V.olusturulma);
  document.getElementById("zaman").textContent = isNaN(z) ? V.olusturulma : z.toLocaleString("tr-TR");

  // KPI kartları
  var yuzde = S.toplam ? Math.round(100 * S.devredilen / S.toplam) : 0;
  [
    ["Toplam mesaj", S.toplam, S.toplam + " kayıt işlendi", ""],
    ["Devredilen", S.devredilen, "%" + yuzde + " temsilciye", "kirmizi"],
    ["Otomatik taslak", S.otomatik, "onaya hazır", "yesil"],
    ["Güvenlik engeli", S.guvenlik_engeli, "yetkisiz sipariş sorgusu", "sari"],
    ["Ort. güven", S.ortalama_guven.toFixed(2), "spam: " + S.spam, ""]
  ].forEach(function (k) {
    document.getElementById("kartlar").appendChild(el("div", { "class": "kart " + k[3] }, [
      el("div", { "class": "etiket", text: k[0] }), el("div", { "class": "deger", text: String(k[1]) }),
      el("div", { "class": "ek", text: k[2] })
    ]));
  });

  // Dağılım
  var enCok = Math.max.apply(null, V.konular.map(function (k) { return S.konu_adet[k]; })) || 1;
  V.konular.forEach(function (k) {
    var adet = S.konu_adet[k], devir = S.konu_devir[k];
    var cubuk = el("div", { "class": "cubuk", role: "img", "aria-label": k + ": " + adet + " mesaj, " + devir + " devredilen" }, [
      el("span", { style: "width:" + (100 * (adet - devir) / enCok) + "%;background:" + renk(k) }),
      el("span", { "class": "dv", style: "width:" + (100 * devir / enCok) + "%;background-color:" + renk(k) })
    ]);
    document.getElementById("dagilim").appendChild(el("div", { "class": "dsatir" }, [
      el("span", { "class": "konu" }, [nokta(k), el("span", { text: k })]), cubuk,
      el("span", { "class": "sayi", text: adet + (devir ? " · " + devir + "↗" : "") })
    ]));
  });

  // Temsilci bekleyenler
  var dikkat = document.getElementById("dikkat");
  T.filter(function (t) { return t.devret; }).forEach(function (t) {
    dikkat.appendChild(el("li", null, [el("b", { text: "#" + t.id }),
      el("div", null, [el("div", { "class": "konu" }, [nokta(t.konu), el("span", { text: t.konu })]),
                       el("span", { text: t.notlar[0] || "" })])]));
  });
  if (!dikkat.children.length) dikkat.appendChild(el("li", { text: "Devredilen mesaj yok." }));

  // Konu filtre çipleri
  var konuFiltre = document.getElementById("konuFiltre");
  ["hepsi"].concat(V.konular).forEach(function (k) {
    var n = k === "hepsi" ? T.length : S.konu_adet[k];
    var b = el("button", { type: "button", "class": "cip", "data-konu": k, "aria-pressed": String(k === "hepsi") },
      [k === "hepsi" ? null : nokta(k), el("span", { text: k === "hepsi" ? "Tümü" : k }), el("span", { "class": "n", text: String(n) })]);
    b.addEventListener("click", function () {
      durum.konu = k;
      konuFiltre.querySelectorAll(".cip").forEach(function (c) { c.setAttribute("aria-pressed", String(c === b)); });
      ciz();
    });
    konuFiltre.appendChild(b);
  });
  document.getElementById("durum").addEventListener("change", function (e) { durum.filtre = e.target.value; ciz(); });
  document.getElementById("ara").addEventListener("input", function (e) { durum.q = e.target.value.toLocaleLowerCase("tr"); ciz(); });

  function durumRozeti(t) {
    if (t.devret) return el("span", { "class": "rozet devret", text: "Devret" });
    if (t.cevap_taslagi) return el("span", { "class": "rozet oto", text: "Otomatik" });
    return el("span", { "class": "rozet sessiz", text: t.etiket || "Yanıtsız" });
  }

  function detaySatiri(t) {
    var notlar = el("ul", { "class": "notlar" }, t.notlar.map(function (n) {
      return el("li", { "class": n.indexOf("GÜVENLİK UYARISI") === 0 ? "uyari" : "", text: n });
    }));
    var ek = "Dil: " + t.dil + " · musteri_id: " + t.musteri_id +
      (t.siparis_numaralari.length ? " · sipariş no: " + t.siparis_numaralari.join(", ") : "") +
      " · işlem: " + t.islem_zamani;
    return el("tr", { "class": "detay" }, [el("td", { colspan: "6" }, [el("div", { "class": "detay-izgara" }, [
      el("div", null, [el("h3", { text: "Cevap taslağı" }),
        t.cevap_taslagi ? el("pre", { "class": "taslak", text: t.cevap_taslagi })
                        : el("div", { "class": "kucuk", text: "Taslak üretilmedi." })]),
      el("div", null, [el("h3", { text: "Temsilci notları" }), notlar,
        el("div", { "class": "kucuk", style: "margin-top:8px", text: ek })])
    ])])]);
  }

  function ciz() {
    var govde = document.getElementById("govde");
    govde.textContent = "";
    var liste = T.filter(function (t) {
      if (durum.konu !== "hepsi" && t.konu !== durum.konu) return false;
      if (durum.filtre === "devret" && !t.devret) return false;
      if (durum.filtre === "oto" && (t.devret || !t.cevap_taslagi)) return false;
      if (durum.q) {
        var hay = [t.mesaj, t.not, t.cevap_taslagi || "", t.konu].join(" ").toLocaleLowerCase("tr");
        if (hay.indexOf(durum.q) < 0) return false;
      }
      return true;
    });
    liste.forEach(function (t) {
      var guven = el("div", { "class": "guven" }, [el("span", { text: t.guven.toFixed(2) }),
        el("div", { "class": "cubuk" }, [el("span", { style: "width:" + (100 * t.guven) + "%" })])]);
      var durumHucre = el("td", { "data-b": "Durum" }, [durumRozeti(t)]);
      if (t.notlar.some(function (n) { return n.indexOf("GÜVENLİK UYARISI") === 0; }))
        durumHucre.appendChild(el("span", { "class": "rozet guv", text: "Güvenlik" }));
      var satir = el("tr", { "class": "satir", tabindex: "0", "aria-expanded": String(!!acik[t.id]) }, [
        el("td", { "data-b": "#", text: String(t.id) }),
        el("td", { "data-b": "Kanal", text: t.kanal }),
        el("td", { "data-b": "Konu" }, [el("span", { "class": "konu" }, [nokta(t.konu), el("span", { text: t.konu })])]),
        el("td", { "data-b": "Güven" }, [guven]),
        durumHucre,
        el("td", { "data-b": "Mesaj", "class": "mesaj", text: t.mesaj })
      ]);
      function degistir() { acik[t.id] = !acik[t.id]; ciz(); }
      satir.addEventListener("click", degistir);
      satir.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); degistir(); } });
      govde.appendChild(satir);
      if (acik[t.id]) govde.appendChild(detaySatiri(t));
    });
    if (!liste.length) govde.appendChild(el("tr", null, [el("td", { colspan: "6", "class": "bos", text: "Filtreye uyan mesaj yok." })]));
  }
  ciz();
})();
</script>
</body>
</html>
"""

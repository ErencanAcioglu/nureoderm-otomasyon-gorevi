"""Müşteri mesajlarını işler; talepler.json, talepler_detay.json ve ozet.html üretir.

Kullanım:
    python3 A-mesaj-otomasyonu/main.py            # çıktı dosyaları + ANSI terminal özeti
    python3 A-mesaj-otomasyonu/main.py --detay    # her mesaj için kural, not ve taslak da gösterilir
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from otomasyon import isle
from otomasyon.isleyici import Talep
from otomasyon.ozet import html_ozeti, istatistik, terminal_ozeti

KLASOR = Path(__file__).resolve().parent
VERI_DOSYASI = KLASOR / "mesajlar.json"
TALEPLER_DOSYASI = KLASOR / "talepler.json"
DETAY_DOSYASI = KLASOR / "talepler_detay.json"
HTML_DOSYASI = KLASOR / "ozet.html"


def _yaz_json(yol: Path, veri: Any) -> None:
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _kisalt(metin: str, uzunluk: int) -> str:
    return metin if len(metin) <= uzunluk else metin[: uzunluk - 1] + "…"


def _detay_yazdir(talepler: List[Talep]) -> None:
    print(f"{'ID':>3}  {'KONU':<15}  {'GÜVEN':>5}  {'DİL':<3}  {'DEVRET':<6}  MESAJ")
    print("-" * 100)
    for t in talepler:
        s = t.siniflandirma
        print(f"{t.id:>3}  {t.konu:<15}  {s.guven:>5.2f}  {t.dil:<3}  "
              f"{'EVET' if t.devret else '-':<6}  {_kisalt(t.kayit['mesaj'], 58)}")
        print(f"{'':>5}kurallar: {', '.join(s.eslesen_kurallar) or '-'}")
        print(f"{'':>5}not     : {t.to_dict()['not'] or '-'}")
        taslak = (t.cevap_taslagi or "-").replace("\n", "\n" + " " * 15)
        print(f"{'':>5}taslak  : {taslak}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Müşteri mesajı otomasyonu")
    parser.add_argument("--detay", action="store_true", help="kurallar, notlar ve taslakları göster")
    parser.add_argument("--renksiz", action="store_true", help="ANSI renklerini kapat")
    args = parser.parse_args()

    mesajlar = json.loads(VERI_DOSYASI.read_text(encoding="utf-8"))
    talepler = [isle(m) for m in mesajlar]
    olusturulma = datetime.now(timezone.utc).isoformat(timespec="seconds")

    _yaz_json(TALEPLER_DOSYASI, [t.to_dict() for t in talepler])
    ist = istatistik(talepler)
    _yaz_json(DETAY_DOSYASI, {
        "meta": {
            "olusturulma": olusturulma,
            "kaynak": VERI_DOSYASI.name,
            "api": "https://dummyjson.com",
            "toplam": ist.toplam,
            "devredilen": ist.devredilen,
            "konu_dagilimi": ist.konu_adet,
            "diller": ist.diller,
        },
        "talepler": [t.detay_dict() for t in talepler],
    })
    HTML_DOSYASI.write_text(html_ozeti(talepler, olusturulma), encoding="utf-8")

    if args.detay:
        _detay_yazdir(talepler)
    print(terminal_ozeti(talepler, renk=False if args.renksiz else None))
    print()
    for yol in (TALEPLER_DOSYASI, DETAY_DOSYASI, HTML_DOSYASI):
        print(f"  → {yol.relative_to(KLASOR.parent)}")


if __name__ == "__main__":
    main()

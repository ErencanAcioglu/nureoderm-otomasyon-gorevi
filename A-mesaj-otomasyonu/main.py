"""15 müşteri mesajını işleyip sonuçları terminalde gösterir.

Kullanım:
    python3 A-mesaj-otomasyonu/main.py            # tablo + konu/devir dağılımı
    python3 A-mesaj-otomasyonu/main.py --detay    # eşleşen kurallar, notlar ve taslaklar da gösterilir
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from otomasyon import KONULAR, isle

VERI_DOSYASI = Path(__file__).resolve().parent / "mesajlar.json"


def _kisalt(metin: str, uzunluk: int) -> str:
    return metin if len(metin) <= uzunluk else metin[: uzunluk - 1] + "…"


def main() -> None:
    parser = argparse.ArgumentParser(description="Müşteri mesajı otomasyonu")
    parser.add_argument("--detay", action="store_true", help="kurallar, notlar ve taslakları göster")
    args = parser.parse_args()

    mesajlar = json.loads(VERI_DOSYASI.read_text(encoding="utf-8"))

    print(f"{'ID':>3}  {'KANAL':<9}  {'KONU':<15}  {'GÜVEN':>5}  {'DEVRET':<6}  {'NOT':<34}  MESAJ")
    print("-" * 120)
    dagilim: Counter = Counter()
    devir: Counter = Counter()
    for m in mesajlar:
        t = isle(m)
        s = t.siniflandirma
        dagilim[t.konu] += 1
        devir[t.konu] += t.devret

        print(f"{m['id']:>3}  {m['kanal']:<9}  {t.konu:<15}  {s.guven:>5.2f}  "
              f"{'EVET' if t.devret else '-':<6}  {_kisalt(t.to_dict()['not'], 34):<34}  "
              f"{_kisalt(m['mesaj'], 36)}")
        if args.detay:
            print(f"{'':>5}kurallar: {', '.join(s.eslesen_kurallar) or '-'}")
            print(f"{'':>5}not     : {t.to_dict()['not'] or '-'}")
            print(f"{'':>5}taslak  : {t.cevap_taslagi or '-'}")

    print("-" * 120)
    print(f"{'Konu':<17}{'Adet':>4}  {'Devir':>5}")
    for konu in KONULAR:
        print(f"  {konu:<15}{dagilim[konu]:>4}  {devir[konu]:>5}")
    print(f"  {'TOPLAM':<15}{sum(dagilim.values()):>4}  {sum(devir.values()):>5}")


if __name__ == "__main__":
    main()

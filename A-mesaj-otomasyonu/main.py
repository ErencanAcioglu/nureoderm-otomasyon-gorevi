"""15 müşteri mesajını sınıflandırıp sonuçları terminalde gösterir.

Kullanım:
    python3 A-mesaj-otomasyonu/main.py            # tablo + konu dağılımı
    python3 A-mesaj-otomasyonu/main.py --detay    # eşleşen kurallar da gösterilir
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from otomasyon import KONULAR, siniflandir

VERI_DOSYASI = Path(__file__).resolve().parent / "mesajlar.json"


def _kisalt(metin: str, uzunluk: int) -> str:
    return metin if len(metin) <= uzunluk else metin[: uzunluk - 1] + "…"


def main() -> None:
    parser = argparse.ArgumentParser(description="Müşteri mesajı sınıflandırıcı")
    parser.add_argument("--detay", action="store_true", help="eşleşen kuralları göster")
    args = parser.parse_args()

    mesajlar = json.loads(VERI_DOSYASI.read_text(encoding="utf-8"))

    print(f"{'ID':>3}  {'KANAL':<9}  {'KONU':<15}  {'GÜVEN':>5}  {'NOT':<26}  MESAJ")
    print("-" * 110)
    dagilim: Counter = Counter()
    for m in mesajlar:
        s = siniflandir(m["mesaj"])
        dagilim[s.konu] += 1

        notlar = []
        if s.etiket:
            notlar.append(s.etiket)
        if s.hassas:
            notlar.append("HASSAS")
        if s.siparis_numaralari:
            notlar.append("sip#" + ",".join(map(str, s.siparis_numaralari)))
        if s.inceleme_gerekli:
            notlar.append("düşük güven")
        if s.ikincil_konular and not s.etiket:
            notlar.append("+" + s.ikincil_konular[0])

        print(f"{m['id']:>3}  {m['kanal']:<9}  {s.konu:<15}  {s.guven:>5.2f}  "
              f"{_kisalt(' | '.join(notlar), 26):<26}  {_kisalt(m['mesaj'], 44)}")
        if args.detay:
            print(f"{'':>5}kurallar: {', '.join(s.eslesen_kurallar) or '-'}")

    print("-" * 110)
    print("Konu dağılımı:")
    for konu in KONULAR:
        print(f"  {konu:<15} {dagilim[konu]:>2}")
    print(f"  {'TOPLAM':<15} {sum(dagilim.values()):>2}")


if __name__ == "__main__":
    main()

"""Claude Code oturum kaydını (~/.claude/projects/.../<oturum>.jsonl) okunur bir Markdown loguna çevirir.

İçerik: kullanıcı mesajları (olduğu gibi), Claude'un görünür yanıtları (olduğu gibi), araç çağrıları
(komut/açıklama) ve kısaltılmış araç çıktıları. Hariç tutulanlar: araç ortamının eklediği sistem
hatırlatmaları (<system-reminder>), boş 'thinking' blokları, görseller (yer tutucu yazılır).
Gizlilik: git kimliği dışındaki e-posta adresleri maskelenir.

Kullanım:
    python3 promptlar/oturum_logu_cikar.py <oturum.jsonl> promptlar/ham-oturum-logu.md
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List

IZINLI_EPOSTALAR = {"erencanacioglu@gmail.com", "noreply@anthropic.com"}
EPOSTA_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SISTEM_RE = re.compile(r"<system-reminder>.*?</system-reminder>|<ide_[a-z_]+>.*?</ide_[a-z_]+>", re.S)
TR = timezone(timedelta(hours=3))
CIKTI_SATIR = 30
CIKTI_KARAKTER = 3000


def maskele(metin: str) -> str:
    return EPOSTA_RE.sub(lambda m: m.group(0) if m.group(0) in IZINLI_EPOSTALAR else "[e-posta gizlendi]", metin)


def saat(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TR).strftime("%H:%M:%S")


def kisalt(metin: str) -> str:
    satirlar = metin.splitlines()
    kisa = "\n".join(satirlar[:CIKTI_SATIR])[:CIKTI_KARAKTER]
    if len(kisa) < len(metin):
        kisa += f"\n… [kısaltıldı: toplam {len(satirlar)} satır, {len(metin)} karakter]"
    return kisa


def kod_blogu(metin: str, dil: str = "") -> str:
    cit = "````" if "```" in metin else "```"
    return f"{cit}{dil}\n{metin}\n{cit}"


def sonuc_metni(icerik: Any) -> str:
    if isinstance(icerik, str):
        return icerik
    parcalar = []
    for b in icerik or []:
        if b.get("type") == "text":
            parcalar.append(b.get("text", ""))
        elif b.get("type") == "image":
            parcalar.append("[görsel]")
    return "\n".join(parcalar)


def arac_girdisi(ad: str, girdi: dict) -> str:
    if ad == "Bash":
        return f"_{girdi.get('description', '')}_\n\n" + kod_blogu(girdi.get("command", ""), "bash")
    if ad == "Write":
        icerik = girdi.get("content", "")
        return f"`{girdi.get('file_path')}` — {len(icerik.splitlines())} satır yazıldı (içerik repoda)"
    if ad == "Edit":
        return (f"`{girdi.get('file_path')}`\n\n**eski:**\n" + kod_blogu(kisalt(girdi.get("old_string", "")))
                + "\n**yeni:**\n" + kod_blogu(kisalt(girdi.get("new_string", ""))))
    if ad == "Read":
        return f"`{girdi.get('file_path')}`" + (f" (satır {girdi['offset']}+)" if girdi.get("offset") else "")
    return kod_blogu(kisalt(json.dumps(girdi, ensure_ascii=False, indent=2)), "json")


def donustur(jsonl: Path) -> str:
    kayitlar = [json.loads(s) for s in jsonl.read_text(encoding="utf-8").splitlines() if s.strip()]
    mesajlar = [k for k in kayitlar if k.get("type") in ("user", "assistant") and k.get("message")]
    zamanlar = [k["timestamp"] for k in mesajlar if k.get("timestamp")]
    cikti: List[str] = []
    kullanici_no = 0

    for k in mesajlar:
        icerik = k["message"].get("content")
        ts = saat(k["timestamp"]) if k.get("timestamp") else "--:--:--"
        bloklar = [{"type": "text", "text": icerik}] if isinstance(icerik, str) else (icerik or [])
        for b in bloklar:
            tur = b.get("type")
            if k["type"] == "user" and tur == "text":
                metin = SISTEM_RE.sub("", b.get("text", "")).strip()
                if not metin or metin.startswith("[Image:"):
                    continue
                kullanici_no += 1
                cikti.append(f"\n---\n\n## [{ts}] 👤 Kullanıcı — mesaj {kullanici_no}\n\n{kod_blogu(metin, 'text')}\n")
            elif k["type"] == "user" and tur == "tool_result":
                metin = sonuc_metni(b.get("content")).strip()
                etiket = "Hata" if b.get("is_error") else "Çıktı"
                if metin:
                    cikti.append(f"<details><summary>{etiket}</summary>\n\n{kod_blogu(kisalt(metin))}\n\n</details>\n")
            elif k["type"] == "assistant" and tur == "text" and b.get("text", "").strip():
                cikti.append(f"\n### [{ts}] 🤖 Claude\n\n{b['text'].strip()}\n")
            elif k["type"] == "assistant" and tur == "tool_use":
                cikti.append(f"\n#### [{ts}] 🔧 {b.get('name')}\n\n{arac_girdisi(b.get('name', ''), b.get('input') or {})}\n")

    bas = datetime.fromisoformat(min(zamanlar).replace("Z", "+00:00")).astimezone(TR)
    son = datetime.fromisoformat(max(zamanlar).replace("Z", "+00:00")).astimezone(TR)
    baslik = [
        "# Ham Oturum Logu — Claude Code",
        "",
        f"- Oturum: `{jsonl.stem}`",
        f"- Zaman aralığı (UTC+3): {bas:%Y-%m-%d %H:%M:%S} → {son:%H:%M:%S}",
        f"- Kullanıcı mesajı: {kullanici_no}",
        f"- Kaynak: `~/.claude/projects/<proje>/{jsonl.name}` → `promptlar/oturum_logu_cikar.py` ile üretildi",
        "- İçerik: kullanıcı mesajları ve Claude'un görünür yanıtları **olduğu gibi**; araç çağrıları ve kısaltılmış çıktıları.",
        "- Hariç tutulanlar: araç ortamının eklediği sistem hatırlatmaları ve IDE bildirimleri (`<ide_opened_file>` vb.), görseller (yer tutucu), boş düşünce blokları.",
        "- Gizlilik: git kimliği dışındaki e-posta adresleri `[e-posta gizlendi]` olarak maskelendi.",
        "- Not: Log, üretildiği ana kadarki kayıtları içerir; son teslim mesajının yanıtı dosya yazıldıktan sonra tamamlandığından eksik olabilir.",
    ]
    return maskele("\n".join(baslik) + "\n" + "".join(cikti))


if __name__ == "__main__":
    kaynak, hedef = Path(sys.argv[1]), Path(sys.argv[2])
    hedef.write_text(donustur(kaynak), encoding="utf-8")
    print(f"{hedef} yazıldı ({hedef.stat().st_size // 1024} KB)")

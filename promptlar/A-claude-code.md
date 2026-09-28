# Bölüm A — Claude Code Prompt Kaydı

Araç: Claude Code (VS Code eklentisi), model: Claude Opus 5.5
Kural: Promptlar silinmeden, sırasıyla ve olduğu gibi eklenir (başarısız denemeler dahil).
Her promptun altında, o adımda yapay zekânın ne yaptığı kısa bir özet olarak yer alır.

---

## Prompt 1 — Proje iskeleti, git kuralı, prompt kaydı, veri analizi

> Ek bağlam olarak `@case-brief.md` ve `@mesajlar.json` dosyaları iliştirildi.

```text
Merhaba. Nureoderm kozmetik e-ticaret müşteri mesajları otomasyonu ve n8n entegrasyonu projesine sıfırdan başlıyoruz.

KESİN GİT KURALI: Bu projede yapılacak tüm Git işlemleri ve commit/push hareketleri YALNIZCA şu uzak repoya ve şu kullanıcı kimliğiyle yapılacaktır:
Repo: https://github.com/ErencanAcioglu/nureoderm-otomasyon-gorevi.git
Git Kullanıcı Adı: ErencanAcioglu
Git E-posta: erencanacioglu@gmail.com

KRİTİK PROMPT KAYIT KURALI (ANINDA GÜNCELLEME):
Görev kuralı gereği yazdığımız tüm promptlar, aldığımız kararlar ve diyaloglar EKSİKSİZ, SIRASIYLA ve ANINDA kaydedilmelidir.
Bundan sonraki her adımda, işi bitirip commit atmadan önce:
- Gönderdiğim promptu ve yaptığın işi ANINDA ilgili dosyaya ('promptlar/A-claude-code.md' veya 'promptlar/B-n8n.md') ekleyeceksin.
- Dosya asla boş kalmayacak; her prompt o adımın commit'ine dahil olacak.

İlk olarak şu hazırlıkları yapalım:
1. Git yerel yapılandırmasını doğrula:
   git config user.name "ErencanAcioglu"
   git config user.email "erencanacioglu@gmail.com"
2. Kök dizine kapsamlı bir '.gitignore' ekle (venv, __pycache__, .env, .DS_Store vb.).
3. Dizin yapısını kur:
   - A-mesaj-otomasyonu/
   - B-n8n/
   - promptlar/
4. 'A-mesaj-otomasyonu/mesajlar.json' dosyasını 15 müşteri mesajı verisiyle oluştur.
5. 'promptlar/A-claude-code.md' dosyasını oluştur ve bu gönderdiğim ilk promptu içine ekle.
6. İlk atomik commit'i at:
   git add . && git commit -m "chore: initial project structure, gitignore, dataset and prompt logger"

Dosyaları oluşturup commit attıktan sonra 'mesajlar.json'ı analiz et; niyet dağılımını, potansiyel güvenlik/regülasyon risklerini ve ekleyebileceğimiz mühendislik inisiyatiflerini özetle. Henüz uygulama kodu yazma.
```

### Yapılanlar (Claude)

- `git init -b main`; yerel `user.name=ErencanAcioglu`, `user.email=erencanacioglu@gmail.com` ayarlandı ve doğrulandı.
- `origin` uzak reposu `https://github.com/ErencanAcioglu/nureoderm-otomasyon-gorevi.git` olarak eklendi (push istenmediği için yapılmadı).
- Kök dizine `.gitignore` eklendi (Python, venv, `.env`, Node/n8n, OS, IDE, log dosyaları).
- `A-mesaj-otomasyonu/`, `B-n8n/` (boş klasör git'te görünsün diye `.gitkeep`), `promptlar/` oluşturuldu.
- Verilen `mesajlar.json` birebir korunarak `A-mesaj-otomasyonu/mesajlar.json` konumuna taşındı; JSON geçerliliği ve 15 kayıt (id 1–15) doğrulandı.
- **Karar / sapma:** `case-brief.md` değerlendiricinin kişisel e-posta adresini içerdiği ve repo public olacağı için `.gitignore`'a eklendi, commit'e girmedi. İstenirse tek satır silinerek eklenebilir.
- İlk commit atıldı: `chore: initial project structure, gitignore, dataset and prompt logger`.

### Analiz çıktısı (commit sonrası, kod yazılmadan)

API gerçekten sorgulanarak doğrulandı (`/carts/{12,5,9999,3,4}`, `/products/search`, `/products/category/{beauty,skin-care}`).

**Önerilen konu dağılımı:** siparis-durumu 5 (1,2,3,6,8) · urun-sorusu 4 (9,11,13,15) · fiyat 2 (10,14) · diger 2 (7 spam, 12 genel kargo sorusu) · iade-sikayet 1 (5) · istenmeyen-etki 1 (4). Devret: 4, 5, 1 (+3 karara bağlı).

**Sipariş sahipliği (canlı API):** #12 → userId 12 ≠ müşteri 7 → **başka müşterinin siparişi, bilgi verilmez, devret**. #5 → 5 = 5 eşleşir. #9999 → not found. #3 (`#3` yazımı, İngilizce) → 3 = 3 eşleşir. #4 → 4 = 4 eşleşir.

**Riskler:** IDOR / sipariş sızıntısı (mesaj 1); eşleşmeyen yanıtta siparişin varlığını bile doğrulamamak; sayı çıkarımında "200 ml" gibi sipariş olmayan sayılar; çok niyetli mesaj (8: fiyat + sipariş); istenmeyen etkide tıbbi tavsiye/teşhis yasağı ve kozmetovijilans kaydı; içerik/hayvan testi/cilt tipi sorularında doğrulanmamış iddia üretmeme; spam/phishing linki (7); LLM kullanılırsa prompt injection → güvenlik kararları deterministik kodda kalmalı.

**Bonus bulgusu:** Türkçe terimler API'de sonuç vermiyor; `serum`, `sunscreen`, `toner`, `moisturizer` → 0 sonuç; `cream` → "Ice Cream" (yanlış pozitif). Kategori filtresi (beauty/skin-care) ve TR→EN terim eşlemesi gerekiyor.

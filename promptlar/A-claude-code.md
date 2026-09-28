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

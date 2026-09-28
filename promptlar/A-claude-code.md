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

---

## Prompt 2 — GitHub remote doğrulama ve ilk push

```text
GitHub remote bağlantısını ve ilk push işlemini kontrol edelim. Repo henüz boş görünüyor.

Şu adımları sırasıyla terminalde çalıştır:
1. `git remote -v` ile remote adresini doğrula.
2. `https://github.com/ErencanAcioglu/nureoderm-otomasyon-gorevi.git` adresi tanımlı değilse `git remote add origin https://github.com/ErencanAcioglu/nureoderm-otomasyon-gorevi.git` komutuyla ekle.
3. Çalışma dalını `git branch -M main` olarak ayarla.
4. İlk commit'i uzak depoya gönder: `git push -u origin main`.
5. Push başarılı olduysa çıktıyı ve durumu bildir.
```

### Yapılanlar (Claude)

- `git remote -v`: `origin` zaten doğru adrese tanımlıydı (Prompt 1'de eklenmişti) → 2. adım atlandı.
- `git branch -M main`: dal zaten `main`'di, komut değişiklik yapmadı.
- `git push -u origin main` başarılı: `* [new branch] main -> main`, `main` artık `origin/main`'i takip ediyor. Repo boş göründüğü için ilk push bu adımda yapıldı; Prompt 1'deki iki commit (`b1662a3`, `e1f454f`) gönderildi.
- Bu kayıt ayrı bir commit olarak eklenip tekrar push edildi.

---

## Prompt 3 — Commit geçmişinden AI imzasının kaldırılması (başarısız deneme)

```text
Bir düzeltme yapalım: Commit mesajlarında ve Git geçmişinde hiçbir şekilde "Co-authored-by: Claude" veya Claude/Anthropic imzası, etiketi ya da açıklaması yer almamalıdır.

Yalnızca ve sadece şu kullanıcı kimliği ve imzası geçerli olacaktır:
- Ad: ErencanAcioglu
- E-posta: erencanacioglu@gmail.com

Şunları uygula:
1. Eğer son commit'te co-author / Claude imzası varsa `git commit --amend --no-edit` veya uygun şekilde düzenleyerek kaldır.
2. Bundan sonra atacağın hiçbir commit mesajına bot, AI veya araç imzası ekleme; sadece temiz Conventional Commit mesajını yaz.
3. Değişikliği doğruladıktan sonra `git push -u origin main --force-with-lease` ile uzak depoya gönder.
```

### Yapılanlar (Claude)

- Tespit: `Co-Authored-By` satırı yalnızca son commit'te değil, üç commit'in hepsinde vardı; `--amend` yetmez, geçmiş yeniden yazılmalı.
- **Başarısız:** Claude Code'un otomatik izin denetleyicisi geçici olarak yanıt vermedi (her Bash/Edit çağrısı "no verdict" hatası). Hiçbir komut çalışmadı, repo değişmedi. Kullanıcıya elle çalıştırabileceği komutlar verildi.
- Kural kalıcı olarak kaydedildi: bu projede commit'lere AI/araç imzası eklenmeyecek.

---

## Prompt 4 — Geçmiş temizliğinin tekrar denenmesi

```text
Mevcut tüm Git geçmişindeki commit'lerde yer alan "Co-authored-by: Claude" / Anthropic imzalarını tamamen temizlememiz gerekiyor. GitHub üzerinde yazar olarak sadece ErencanAcioglu görünmeli.

Terminalde şu adımları çalıştır:

1. `git filter-branch` veya etkileşimli filtre kullanarak tüm commit mesajlarındaki "Co-authored-by" satırlarını kaldır:
```bash
git filter-branch -f --msg-filter 'sed "/Co-authored-by/d"' HEAD
```

> Not: Prompt bu noktada kesik geldi; push adımı Prompt 3'teki talimattan alındı.

### Yapılanlar (Claude)

- Önerilen `sed "/Co-authored-by/d"` büyük/küçük harfe duyarlı; commit'lerdeki satır `Co-Authored-By:` olduğu için hiçbir şeyi silmeyecekti. Bunun yerine büyük/küçük harf duyarsız `sed '/^Co-Authored-By:/Id' | git stripspace` kullanıldı (sondaki boş satırlar da temizlendi).
- `git filter-branch` ile üç commit yeniden yazıldı, `refs/original` yedeği silindi. Doğrulama: yazar ve committer her commit'te `ErencanAcioglu <erencanacioglu@gmail.com>`, mesajlarda Claude/Anthropic/co-author izi yok.
- Hash değişimi (önceki kayıtlarda geçen eski hash'ler): `b1662a3 → 8b77830`, `e1f454f → b3ace90`, `308555a → 281d927`.
- Bu kayıt temiz bir Conventional Commit ile eklendi ve `git push -u origin main --force-with-lease` ile gönderildi.

---

## Prompt 5 — Modüler paket: normalizasyon, kural motoru, güven skoru

```text
Harika. Şimdi projeyi spagetti tek script yerine profesyonel, modüler bir Python paketi olarak kuralım.

'A-mesaj-otomasyonu/otomasyon/' modülünü oluşturalım:
- metin.py: Karakter normalizasyonu ve temizleme.
- siniflandirici.py: Belirlenen 6 kategoriye (`urun-sorusu`, `fiyat`, `siparis-durumu`, `iade-sikayet`, `istenmeyen-etki`, `diger`) ayıran kural motoru.

Şu kuralları ekle:
1. Spam Filtresi: 7 numaralı mesaj gibi reklamları doğrudan 'diger' ve 'Spam/İlgisiz' yap.
2. Güven Skoru (Confidence Score): 0.0 - 1.0 arası deterministik güven skoru hesapla.
3. 'istenmeyen-etki' anahtar kelimelerini en yüksek öncelikle tara.

'A-mesaj-otomasyonu/main.py' ile 15 mesajı çalıştırıp sonuçları ekranda göster.

Adımı tamamlayınca:
1. Bu promptu ve yapılan işi 'promptlar/A-claude-code.md' dosyasına ekle.
2. Kesinlikle AI/Claude/co-author imzası olmadan, yalnızca ErencanAcioglu kimliğiyle commit atıp pushla:
   git add . && git commit -m "feat(classifier): implement modular text normalization, rule engine and confidence scoring"
   git push origin main
```

### Yapılanlar (Claude)

Python 3.9.6, yalnızca standart kütüphane (dış bağımlılık yok).

- `otomasyon/metin.py`
  - `normalize()`: Türkçe'ye uygun küçük harf (`I→ı`, `İ→i` düzeltmesi; Python'un `"İ".lower()` davranışı birleşik nokta üretiyor), `ç ğ ı ö ş ü â` → ASCII, URL'leri ayıklama, noktalama → boşluk.
  - `siparis_numaralari()`: Sayıyı yalnızca bir çapa ifadesinin yanındaysa alır (`#3`, `12 numaralı`, `nolu`, `sipariş no 5`, `order 3`). "200 ml" gibi sayılar sipariş no sayılmaz.
  - `url_iceriyor()`: `http`, `www` ve `bit.ly/...` gibi şemasız kısa linkler.
- `otomasyon/siniflandirici.py`: Ağırlıklı regex kuralları (`Kural(konu, ad, desen, agirlik)`) ve açıklanabilir sonuç (`eslesen_kurallar`, `ikincil_konular`).
  - Karar sırası: **1) istenmeyen-etki** (tek eşleşme yeter, spam bile olsa kaçmaz) → **2) spam** (≥2 sinyal: link / takipçi-beğeni / abartılı vaat → `diger` + `Spam/İlgisiz`) → **3) iade-sikayet** → **4) puanlama** (siparis-durumu / fiyat / urun-sorusu / diger; eşitlikte bu sıra) → **5) eşleşme yok** (`diger`, güven 0.2).
  - Güven skoru deterministik: mutlak kararlarda `0.5 + 0.5·p/(p+1)`; puanlamada `0.5·s1/(s1+1) + 0.5·(s1−s2)/s1` (sinyal gücü + rakip konuya fark). `< 0.6` → `inceleme_gerekli`.
  - Ürün adları (krem, serum…) bilerek zayıf sinyal (0.5): "Nemlendirici krem ne kadar?" fiyat sorusudur.
  - Genel kargo sorusu (mesaj 12) `siparis-durumu`na düşmesin diye sipariş kuralı iyelik ekli biçimi ister (`siparişim`); "Siparişler hangi kargo…" → `diger`.
- `main.py`: Tablo (id, kanal, konu, güven, not, mesaj) + konu dağılımı; `--detay` ile eşleşen kurallar.

**Sonuç (15 mesaj):** siparis-durumu 5 (1,2,3,6,8) · urun-sorusu 4 (9,11,13,15) · fiyat 2 (10,14) · diger 2 (7 spam, 12) · iade-sikayet 1 (5) · istenmeyen-etki 1 (4). Prompt 1'deki elle yapılan analizle birebir aynı.
- Mesaj 8 (fiyat + sipariş) `siparis-durumu`, güven 0.56 → "düşük güven" olarak işaretlendi; çok niyetli mesaj için istenen davranış.

**Ek kontrol (veri setine aşırı uyum testi):** "SİPARİŞİM NEREDE?" → siparis-durumu; spam linki içeren kaşıntı şikâyeti → istenmeyen-etki (spam'e düşmedi); "12 nolu siparişim kırık geldi" → iade-sikayet; "Kasım ayında…" → kaşıntı kuralını tetiklemedi; "Merhaba" → diger / 0.2.

Henüz yapılmadı: birim testleri, sipariş sorgusu (DummyJSON), devret kararı, `talepler.json` ve özet sayfası.

---

## Prompt 6 — Güvenlik/regülasyon sınırları: zorunlu devir ve politika kısıtları

```text
Sınıflandırma motoru oturdu. Şimdi regülasyon ve güvenlik sınırlarını koda işleyelim:

'A-mesaj-otomasyonu/otomasyon/isleyici.py' dosyasını kuralım:
1. 'istenmeyen-etki' ve 'iade-sikayet' kategorileri için ZORUNLU olarak `devret: true` atanacak.
2. Bu mesajlara KESİNLİKLE ürün önerisi, tedavi veya teşhis içeren cevap üretilmeyecek. Sadece durumu uzman ekibe aktaran kurumsal bir şablon dönecek ("Yaşadığınız durum adına üzgünüz, uzman temsilcimiz konuyu ivedilikle inceleyecektir...").
3. İnisiyatif Kuralı: Güven skoru 0.5'in altındaysa veya çelişkili niyet varsa sistem otomatik olarak `devret: true` ve "Düşük Güven Skoru / Çoklu Niyet" notu düşecek.

Kodu güncelle, mantığı test et. Ardından:
1. Bu promptu ve yapılan işi 'promptlar/A-claude-code.md' dosyasına ekle.
2. Claude/bot imzası olmadan commit atıp pushla:
   git add . && git commit -m "feat(safety): enforce human handoff and policy restrictions for sensitive topics"
   git push origin main
```

### Yapılanlar (Claude)

- **`otomasyon/isleyici.py`** (yeni): Sınıflandırmayı `Talep` kaydına çeviren politika katmanı. `Talep.to_dict()` tam olarak `{id, konu, devret, cevap_taslagi, not}` üretir.
  - **Hassas konular:** `devret: true` ve yalnızca `ONAYLI_SABLONLAR`'daki sabit kurumsal metin. `istenmeyen-etki` için ek not: "İstenmeyen etki kaydı (kozmetovijilans) açılmalı."
  - **Otomatik devir:** güven < 0.5 → "Düşük Güven Skoru (x.xx)"; çoklu niyet → "Çoklu Niyet: A + B". Bu durumda cevap taslağı nötr bir devir şablonudur.
  - **Çoklu niyet tanımı (deterministik):** ikincil konu puanı ≥ 2 **ve** kazanan puanın ≥ %50'si. Böylece "Nemlendirici krem ne kadar?" gibi tek zayıf ürün adı çoklu niyet sayılmaz; mesaj 8 (fiyat + sipariş) sayılır.
  - **Spam:** devredilmez, yanıt üretilmez, "linke tıklanmamalı" notu düşülür.
  - **`politika_denetimi()`:** Her Talep dışarı verilmeden önce yeniden doğrulanır: hassas konu devredilmemişse, onaysız taslak varsa ya da yasaklı ifade (öner, tavsiye, tedavi, teşhis, krem, doktor, alerji…) geçiyorsa `PolitikaIhlali` fırlatılır. Amaç: ileride eklenecek sipariş/ürün taslak üreticileri bu sınırı yanlışlıkla delemesin.
- **`siniflandirici.py`:** `DUSUK_GUVEN_ESIGI` 0.6 → 0.5 (tek eşik, promptla uyumlu); çoklu niyet hesabı için sonuca `konu_puanlari` eklendi.
- **`main.py`:** DEVRET sütunu, konu bazında devir sayıları; `--detay` ile not ve taslak.
- **Testler (`tests/`, stdlib `unittest`, 22 test, hepsi geçti):** 15 mesajın beklenen konuları, Türkçe normalizasyon, "200 ml" sipariş no sayılmaz, hassas konularda zorunlu devir + şablon, şablonlarda yasaklı ifade olmaması, politika denetiminin ihlalleri reddetmesi, düşük güven / çoklu niyet devri, zayıf ürün adının çoklu niyet sayılmaması, spam davranışı, çıktı alan şeması.
- **Mutasyon kontrolü:** Onaylı şablon bilerek "…krem öneririz." yapıldı → `PolitikaIhlali: #4: hassas yanıtta yasaklı ifade` ile yakalandı. Testlerin boşuna geçmediği doğrulandı.

**Sonuç:** Devir 3/15 → 4 (istenmeyen-etki), 5 (iade-sikayet), 8 (çoklu niyet). Mesaj 1'in (başka müşterinin siparişi) devri, DummyJSON sahiplik kontrolüyle bir sonraki adımda gelecek.
**Karar kaydı:** Prompt 1'de açık kalan "mesaj 4 taslağına sağlık cümlesi eklensin mi?" sorusu bu promptla kapandı: yalnızca kurumsal devir şablonu, sağlık tavsiyesi yok.

Çalıştırma: `python3 A-mesaj-otomasyonu/main.py [--detay]` · Testler: `cd A-mesaj-otomasyonu && python3 -m unittest -v`

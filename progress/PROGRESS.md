# Match Lens — durum raporu

Son güncelleme: 21 Ekim 2026. Bu dosya iki kişilik ekibin ortak durum özetidir: ne yapıyoruz, yarışma ne istiyor, ne yaptık, neredeyiz, sırada ne var. Ayrıntılı ve sıralı iş listesi [TODO.md](../TODO.md); çalıştırma komutları [README.md](../README.md); proje kuralları [AGENTS.md](../AGENTS.md).

## 1. Ne yapıyoruz

**Match Lens**, sentetik bir futbol maçını tarayıcıda oynatan ve maçın kritik anlarını *kanıtıyla* açıklayan bir uygulama. Üç uzman yapay zekâ agent'ı birlikte çalışır:

- **Tactical Analyst**: kanıt paketindeki olaylara ve metriklere dayanarak iddialar üretir.
- **Evidence Editor**: her iddiayı kanıta karşı onaylar ya da reddeder (bir kez düzeltme isteyebilir).
- **Audience Storyteller**: yalnızca onaylanan iddiaları iki farklı izleyiciye yazar — veri meraklısı **analist** ve **sıradan taraftar**.

Temel ilke: **ekrandaki her sayı koddan gelir, modelden değil.** Modeller metne rakam yazamaz; sayının yerine `{pass_completion.nbr.frac}` gibi bir yer tutucu yazar, değeri kod yerleştirir. Model bir adımda başarısız olursa (geçersiz çıktı, red, zaman aşımı) ekranda deterministik bir şablon kart kalır; skor ve replay hiç durmaz.

Veri tamamen sentetik ve kurgusal: Northbridge FC – Harbour Athletic, 2. devre 58:00–62:00 kesiti (`scenarios/synthetic-01`, 97 olay). Senaryo dört an içerir: sabırlı oyun kurma → Harbour'un yüksek baskısı (Northbridge'in pas isabeti düşer) → top kazanımı ve 8,4 sn'de gol (0-1) → Northbridge'in tehditsiz cevabı.

## 2. Yarışma ne istiyor (resmî kuralların özeti)

Microsoft Premier League "Inside the Game" Developer Hackathon. Kuralların tam metni depoda tutulmuyor (üçüncü taraf metni); aşağıdaki özet bizim okumamızdır.

**Takvim (İstanbul saati):** teslim sonu **28 Ekim 2026 09:59** (27 Ekim 23:59 Pacific). Değerlendirme 27 Ekim – 10 Kasım; kazananlar en geç 20 Kasım.

**Meydan okuma — beş aşamalı bir akış:**
1. *Ingest*: sentetik maç olaylarını içeri al.
2. *Interpret*: anlamlı istatistiklere ve örüntülere çevir.
3. *Explain*: bir anın *neden* önemli olduğunu açıkla.
4. *Render*: maçın yanında ekranda duracak biçimde göster.
5. *Personalize*: aynı bilgiyi analist ve sıradan taraftara **gerçekten farklı iki deneyim** olarak sun (tutulan kulüp, oyuncu odağı, dil gibi seçenekler önerilir).

Ayrıca önerilenler: oyuncu etiketleme, pas kalitesi/mesafesi, hız metrikleri, anlatı ve maç özeti, çok dilli metin, sentetik veri üretimi.

**Veri:** sentetik ve futbol açısından gerçekçi olmalı; organizatör görüntü veya veri vermiyor; üçüncü taraf materyalinin hakları bize ait olmalı.

**Kategoriler:** iki büyük ödül + kategori ödülleri (Microsoft Foundry kullanımı, Enterprise, **Multi-Agent**, Azure Cloud Native). Hedefimiz **Best Multi-Agent System**: ayrı rolleri olan agent'lar, ortak durum ve düzgün devirler, hatadan toparlanma, tek bir agent'ın aynı etkinlikle yapamayacağı uçtan uca sonuç.

**Puanlama:** 1. aşama geçti/kaldı — proje temaya uyuyor ve gerekli teknolojileri makul ölçüde kullanıyor mu. 2. aşama: beş eşit ağırlıklı ölçüt (%20'şer) — teknik uygulama (Microsoft Foundry, Agent Framework, Azure MCP, GitHub Copilot vb. "hero" teknolojiler, kod kalitesi), agent tasarımı ve yenilik, gerçek dünya etkisi, kullanıcı deneyimi ve sunum, kategoriye uyum.

**Teslimde gerekenler:**
- Yarışma başladıktan sonra yapılmış yeni proje (ilk commit'imiz 20 Ekim).
- Kısa tanıtım (pitch): ne yaptık, hangi Microsoft/Azure teknolojileri, hangi sorunu çözüyor.
- **2 dakikadan kısa** demo videosu (YouTube/Vimeo vb. public link; izinsiz müzik veya marka yok).
- **Public GitHub deposu.**
- Jürinin değerlendirme süresince **ücretsiz ve kısıtsız** erişebileceği çalışan bir demo (link veya test sürümü).
- Bütün materyaller **İngilizce** (ya da İngilizce çevirisi).
- Takım olarak katılıyorsak teslimi yapacak bir **temsilci** belirlenmeli.

## 3. Ne yaptık

| Parça | Durum | Nerede |
|---|---|---|
| Olay sözleşmesi + doğrulayan yükleyici (hatalı veriyi düzeltmez, kodla reddeder) | Tamam | `src/contracts/events.py`, `src/domain/ingest.py` |
| Seed'li sentetik senaryo (her üretimde birebir aynı) | Tamam | `scenarios/synthetic-01/` |
| Deterministik snapshot, skor, 60 sn pencere metrikleri, şablon kartlar (gol, baskı) | Tamam | `src/domain/` |
| Salt-okunur replay API (FastAPI); hiçbir cevap izlenen andan sonrasını göstermez | Tamam | `services/api/app.py`, sözleşme `src/contracts/api.py` |
| Web replay: saha, kontroller (1x/4x/16x), skor, kanıtlı kartlar, metrik tablosu, erişilebilirlik | Tamam | `apps/web/` |
| Tarayıcıda uçtan uca testler (gerçek API'ye karşı 9 akış) | Tamam | `apps/web/e2e/` |
| Agent sözleşmesi: olgu (fact) tablosu, iddia, inceleme, persona metni, içgörü, izleme kaydı | Tamam | `src/contracts/agents.py` |
| Üç agent + deterministik koordinatör + kod denetimleri + sahte model istemcisi | Tamam (sahte modelle) | `src/agents/`, `src/workflow/` |
| Tek-agent karşılaştırma yolu (aynı girdi, aynı denetim) | Tamam (ölçüm yok) | `src/workflow/single_agent.py` |
| Public'e uygunluk: özel linkler, kuralların kopyası, ham çıktılar depodan çıkarıldı | Tamam | `.gitignore`, `AGENTS.md` |

**Testler (21 Ekim, `main`):** backend 352, web 62, tarayıcı e2e 9/9, hepsi yeşil. `npm audit` 0 açık.

**Önemli kararlar ve neden:**
- *Sayılar yer tutucuyla.* Önceki tasarımda model sayıları serbest metne yazıyor, kod sonradan doğrulamaya çalışıyordu; inceleme turları beş kez uydurma sayının geçtiğini buldu ("48 of 52 passes", yanlış skor). Yeni tasarımda model hiç rakam yazmıyor.
- *Agent'lar an seçmez.* Önemli anları ve kanıt paketini deterministik kod hazırlar; agent'lar o anın sonrasını hiç görmez.
- *Storyteller olayları görmez,* yalnızca onaylanmış iddiaları ve onların olgularını görür; böylece reddedilmiş bir iddia yayına sızamaz.
- *`/meta` maçın sonucunu sızdırmaz.* Senaryonun önemli an açıklamaları (test için var) API'den çıkarıldı.

## 4. Neredeyiz (21 Ekim akşamı)

- **Çalışan:** sentetik maç replay'i, gerçek API'den skor/metrik/şablon kartlar, sahte modelle çalışan agent pipeline'ı (iki an yayınlanıyor).
- **`main`'e girdi:** yer tutucu tasarımı ve uçtan uca incelemenin düzeltmeleri (`wip/facts-v2`). Bağımsız inceleme engelleyici bulmadı; 8 iyileştirme bulgusu çıktı.
- **Devam eden (`wip/story-review`):** Evidence Editor artık hikâye metnini de inceleyecek (inceleme, doğru sayıların etrafında yanlış cümle kurulabildiğini gösterdi: pencerelerin yer değiştirmesi, golü yanlış takıma yazma); Storyteller'a bir düzeltme hakkı; "one up", "second goal", "brace" gibi sayı ifadeleri; "their half of the pitch" gibi yanlış retler; pencere sınırının devre/kesit başına kırpılması; web'de hızlı ileri-geri sonrası takılan istek ve "as of" etiketinin kontrastı.
- **Henüz yok — 1. aşama (geçti/kaldı) riski:**
  1. Gerçek yapay zekâ modeli yok (Microsoft Foundry bağlantısı bekleniyor) → çalışan üründe Microsoft teknolojisi yok.
  2. Agent içgörüleri ve analist/taraftar seçimi arayüzde görünmüyor.
  3. Dağıtım, video, İngilizce pitch yok.

## 5. Sırada ne var (ayrıntı: [TODO.md](../TODO.md))

1. `wip/story-review`'u incelemeden geçirip `main`'e almak.
2. **Foundry model istemcisi**: gerçek modelle iki anın uçtan uca denenmesi, maliyet ve gecikmenin ölçülmesi.
3. **İçgörüleri ürüne taşımak**: `/insights` uç noktası, analist/taraftar seçimi, sonuç rozeti (yayınlandı / yedek kart / çekimser), kanıtın sahada vurgulanması.
4. **Dağıtım ve CI**: tek container, Azure Container Apps, GitHub Actions.
5. **Microsoft Agent Framework**: koordinatörü MAF workflow olarak sarmak.
6. **Ölçümlü değerlendirme**: çok-agent vs tek-agent; sonuç ne çıkarsa dürüstçe raporlanacak.
7. **Teslim**: geçmiş temizliği, İngilizce README/pitch, video, erken teslim (27 Ekim).

## 6. Ekipten karar/bilgi bekleyenler

- **Foundry erişimi:** Azure aboneliği, `az login`, proje endpoint'i ve model dağıtım adı (2. adımın ön şartı).
- **Depo:** public `gokaysari/match-lens` (yalnız `main`). Takım arkadaşının yazma yetkisi için GitHub kullanıcı adı gerekiyor.
- **Lisans sahibi adı:** `LICENSE` şu an tek kişinin adını taşıyor; ekip adı veya iki isim istenebilir.
- **Temsilci:** teslimi kimin yapacağı.
- **İş bölümü:** iki kişi arasında 2–7. adımların paylaşımı.

## 7. Çalışma düzeni

- Ana geliştirme oturumu planlar, sözleşmeleri yazar, işleri küçük görevlere böler. Uzman geliştirme agent'ları (yerelde tutulur, depoda yok) görevleri uygular; her görev bağımsız bir inceleme agent'ından geçer, en fazla iki düzeltme turu yapılır, kullanıcı akışı değiştiyse tarayıcı testi yazılır. Bunlar geliştirme araçlarıdır, ürünün çalışma zamanındaki agent'ları değildir.
- Sözleşmeler (`src/contracts`) önce değişir, sonra kod. Testler önce yazılır.
- Depo public olacak: kişisel veri, özel link, üçüncü taraf metni veya ham uzak servis çıktısı commit'lenmez; dosyalar tek tek eklenir. Commit mesajlarında yapay zekâ/araç ibaresi yok.
- Paralel işler ayrı git worktree'lerinde yürür, sonra birleştirilir; `main` her zaman yeşil kalır.

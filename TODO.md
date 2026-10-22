# Yapılacaklar

Tarihler İstanbul saatiyle. Teslim sonu **28 Ekim 2026 09:59** (resmî kurallar §1). Sıra, 21 Ekim uçtan uca incelemesine göre önceliklendirildi; her adım bir öncekinin çıktısına dayanıyor. Ekip için özet durum: [progress/PROGRESS.md](progress/PROGRESS.md).

## Tamamlananlar

- [x] Kayıt; `git init`; klasör yapısı; MIT lisansı; tek kural dosyası (`AGENTS.md`); geliştirme agent ekibi.
- [x] Olay sözleşmesi, doğrulayan yükleyici, seed'li sentetik senaryo `synthetic-01` (97 olay, 4 an).
- [x] Deterministik snapshot/skor, `metrics-v1` pencere metrikleri, şablon kartlar (gol, baskı), salt-okunur replay API.
- [x] Web replay (saha, kontroller, skor, kartlar + kanıt, metrikler) ve Playwright e2e (9 akış, gerçek API).
- [x] Agent sözleşmesi + üç rol + deterministik koordinatör + kod denetimleri + sahte model + tek-agent baseline yolu.
- [x] Public'i bozacak dosyalar depodan çıkarıldı (yerelde duruyor).

## 1. Sayılar için yer tutucu tasarımı + önemli düzeltmeler (21 Ekim)

- [x] Sözleşme v2: model metninde rakam yok, sayılar `{fact}` yer tutucusu; `Fact` tablosu; `PublishedClaim`; `InsightOutcome`; `/meta` → `MatchInfo` (maç sonucunu sızdırmıyor).
- [x] Agent pipeline'ı: fact tablosu (pencere, önceki pencere, skor, saat, top sahipliği), yeni denetimler, render, istemler p3, düzeltme girdisinde önceki çıktı, kod bloğu toleransı, adil baseline, tek fixture kopyası.
- [x] Domain/API: eksik sonuç/oyuncu, devre-saat, seed, top sahipliği tutarlılığı, çift `match_id`, UTF-8 hataları; kilit dosyaları runtime/dev ayrımı; README doğruluğu ve taşınabilir kurulum.
- [x] Web: `MatchInfo`; gecikmede canlılık (tek uçuşta istek); doğru metrik başlığı; "as of" eskilik işareti; gol/kart duyuruları; saha kontrastı; snapshot dışı kanıt işareti; okunur metin ve etiketler; 390 px skor çubuğu.
- [x] Üç dalın birleştirilmesi, tam test + e2e, `reviewer` ile yeniden inceleme, `main`'e birleştirme (`c08f8fe`).
- [x] Düzeltme turu (`wip/story-review`, `main`'de): hikâye metninin Editor incelemesi + Storyteller düzeltme hakkı; sayı ifadeleri ("one up", "second goal", "brace"); "half of the pitch" yanlış retleri; pencere kırpma; fact anahtarı çakışması; web'de takılan istek, "as of" kontrastı, tablo adı; ajan şema sürümü 2.0.

## 2. Foundry model istemcisi (22 Ekim)

- [ ] Foundry projesi ve model dağıtımı (kullanıcı: `az login`, proje endpoint'i ve dağıtım adı).
- [ ] `FoundryModelClient` (`azure-ai-projects` 2.x, `DefaultAzureCredential`, env `FOUNDRY_PROJECT_ENDPOINT` / `FOUNDRY_MODEL_DEPLOYMENT`); sürümleri Microsoft Learn'den doğrula ve sabitle.
- [ ] Katı structured output: şemaları "tüm alanlar zorunlu" kuralına uyarlama (Learn'de doğrula); ret/content-filter → istisna; zaman aşımları gerçek gecikmeye göre ayar.
- [ ] Gerçek modelle iki anın uçtan uca denemesi; maliyet ve gecikmeyi ölç (çağrı sayısı, token).

## 3. İçgörüleri ürüne taşımak (22–23 Ekim)

- [ ] Sözleşme: `/insights?at_seq=N` (aynı watermark ve tazelik kuralları), `InsightList`; Insight ↔ kart bağı (`card_id`).
- [ ] Backend: içgörüleri önceden üret ve önbelleğe al (replay deterministik); izleme kaydını sakla.
- [ ] Web: Insight TS tipleri; analist / sıradan taraftar seçimi; sonuç rozeti (yayınlandı / yedek / çekimser); analist görünümünde iddialar, olgular ve kanıt; kanıtın sahada vurgulanması; önemli anlara atlama düğmeleri ve zaman çizelgesinde işaretler.
- [ ] Tutulan kulüp seçimi (kurallar kişiselleştirme örneği olarak sayıyor); zaman kalırsa ikinci dil.
- [ ] e2e: persona geçişi (metin değişir, sayılar aynı kalır), her sonuç rozeti.
- [ ] Tipler ve sahte API yükleri JSON şemalarına karşı test edilsin (elle yazılan TS tipleri sapmasın).

## 4. Dağıtım ve CI (24 Ekim)

- [ ] Tek container: FastAPI derlenmiş SPA'yı aynı origin'den sunar; Dockerfile.
- [ ] Azure Container Apps + managed identity ile Foundry erişimi; jüri için ücretsiz, kısıtsız erişim (kurallar §4.8).
- [ ] GitHub Actions: pytest, vitest, tsc, şema tazeliği, build; mümkünse e2e.

## 5. Microsoft Agent Framework (24–25 Ekim, zaman kutulu)

- [ ] Koordinatörü MAF workflow olarak sar (kategori metni "supported orchestration approach" diyor); deterministik denetimler aynen kalsın; API'yi Learn'den doğrula.
- [ ] İsteğe bağlı: domain fonksiyonları üzerinde dört salt-okunur aracı sunan Python MCP adaptörü; `mcp-tests/` JS prototipinin yerini alır.

## 6. Ölçümlü değerlendirme (25 Ekim)

- [ ] 20–30 sabit pencere: normal, kırılma, eksik/tekrarlı/geç olay, yanıltıcı trend, kanıt uyuşmazlığı, timeout.
- [ ] Ölç: desteklenmeyen iddia oranı, yedeğe düşme oranı, kanıt bağlantı doğruluğu, p50/p95 gecikme, an başına maliyet.
- [ ] Çok-agent vs tek-agent aynı model, girdi, bütçe ve düzeltme hakkıyla; sonuç ne çıkarsa dürüstçe raporla.

## 7. Teslim (26–27 Ekim)

- [x] Yayın: public GitHub deposu `gokaysari/match-lens`; yalnız `main`, yerel geliştirme geçmişinden temizlenmiş bir kopyadan push edilir (yerel araç dosyaları, özel araştırma ve ham çıktılar hiç yayınlanmaz; yazar kimliği gokaysari999@gmail.com).
- [ ] İngilizce: README (pitch, kurulum, test erişimi), `docs/` (mimari, değerlendirme sonuçları, sınırlamalar); bu dosya ya çevrilir ya da depodan çıkarılır.
- [ ] < 2 dakikalık video (problem → replay + persona → kanıt zinciri → hata toparlama → ölçüm ve Microsoft stack).
- [ ] Ölçülmemiş iddia yok ("real time", "hallucination-free" vb.); resmî Microsoft/Premier League ürünü izlenimi yok; sayı denetiminin sınırı belgelenir.
- [ ] Son kontrol ve 27 Ekim'de erken teslim.

## Backlog (engelleyici değil)

- Baskı kartı eşiğe tam eşit tetikleniyor (6/10 = 0,6); seed değişirse kart kaybolabilir — senaryo eşikten uzaklaştırılmalı veya birkaç seed için test edilmeli.
- Analist için ek deterministik metrikler: tehdit göstergesi (son üçte bir / ceza sahası girişi, şut mesafesi), oyuncu bazlı kırılımlar, pas mesafesi/hızı (kurallar §4.1 öneriyor).
- `high_ball_wins` tanımı "rakip yarı saha" — futboldaki "high" anlamından geniş; adı veya tanımı netleştir.
- Sayı metrikleri JSON'da float (`16.0`); `EventPage`/`WindowMetrics` `watermark_seq` taşımıyor.
- Senaryo gerçekçiliği: baskı turundaki "tackle won"un önünde top taşıyan yok; pas ritmi tekdüze.
- Backend testleri ~9 sn (kartlar her sequence için API'den); gerekirse örnekle. Starlette `httpx2` uyarısı.
- Web: hız değişince kalan bekleme baştan başlıyor; oynatma zamanlaması için entegrasyon testi yok; e2e'de otomatik erişilebilirlik (axe) taraması yok.
- Paket adları (`agents`, `contracts`, `domain`, `workflow`) genel; SDK eklerken çakışmaya dikkat (ör. openai-agents).

## Kapsam dışı

Gerçek veri sağlayıcısı (lisans/anahtar gerekir), otomatik video etiketleme, DBHub/Qdrant/AntV, A2A, tam maç motoru.

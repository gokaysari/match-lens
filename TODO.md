# Yapılacaklar

Tarihler İstanbul saatiyle. Kayıt sonu **20 Ekim 22:00**, teslim sonu **28 Ekim 09:59** (resmî kurallar §1).

## Bugün (20 Ekim)

- [x] Hackathon kaydı tamamlandı.
- [ ] Kategori kararı: Best Multi-Agent mi, başka kategori mi?
- [ ] Takım: tek kişi mi, en fazla 4 kişi mi? Takvimdeki kesintiler buna göre.
- [ ] Gerçek model erişimi: Foundry aboneliği, bölge, model kotası, `az login` (Azure CLI kurulu değil).
- [ ] Önceki sohbetteki fikir varsa elle buraya aktar; raporlardaki ürün kapsamı bunun yerine kurulmuş bir varsayım.
- [x] `git init` (yerel, `main`).
- [ ] Public GitHub deposu (yeni proje şartı, secret yok).
- [x] Tek sentetik senaryo + olay şeması: `src/contracts/events.py`, `src/domain/ingest.py`, `scenarios/synthetic-01` (97 olay, 4 an, 107 test; 2 düzeltme turu sonrası reviewer Spec ✅ Kalite ✅).

## 21 Ekim — uçtan uca ince dilim

- [x] Klasör yapısı: `apps/web`, `services/api`, `src/{workflow,agents,domain,contracts}`, `scenarios`, `evals`, `docs`, `infra`.
- [x] Deterministik snapshot/skor, pencereli metrikler (`metrics-v1`), şablon kartlar (gol, baskı), salt-okunur replay API (175 test).
- [x] Web replay: saha, kontroller, skor, kartlar + kanıt, metrik tablosu (48 test) ve Playwright e2e (9 akış, gerçek API).
- [ ] Football MCP fixture'daki dört fonksiyonu gerçek veri katmanına taşı (önce doğrudan fonksiyon, MCP adaptörü sonra). Mevcut 11 test sözleşme testi olarak korunur.

## 22 Ekim — agentlar

- [x] Agent sözleşmesi (`src/contracts/agents.py`) ve üç rol + deterministik koordinatör + kod denetimleri + sahte model (`src/agents`, `src/workflow`; 261 test).
- [x] Tek-agent baseline yolu (`workflow/single_agent.py`), aynı denetimler.
- [ ] Foundry `ModelClient` (azure-ai-projects 2.x, DefaultAzureCredential, env `FOUNDRY_PROJECT_ENDPOINT` / `FOUNDRY_MODEL_DEPLOYMENT`); katı structured output için şema uyarlaması; ret/content-filter ele alma.
- [ ] Microsoft Agent Framework: koordinatörü MAF workflow olarak sarmak (hero teknoloji).
- [ ] Insight'ları API'ye ve UI'a bağlamak (persona seçimi).

## 23 Ekim — UX ve hata toparlama

- [ ] İki persona (analist / casual), gerçekten farklı içerik.
- [ ] Kanıt çekmecesi (kart → olaylar → pencere).
- [ ] Tek düzeltme hakkı, expiry kontrolü, timeout'ta kanıtlı şablon; skor/replay kesilmez.
- [ ] Storyteller sonrası deterministik sayı/ID/güncellik kontrolü.

## 24 Ekim — değerlendirme

- [ ] 20–30 sabit pencere: normal, kırılma, eksik/tekrarlı/geç olay, yanıltıcı trend, kanıt uyuşmazlığı, timeout.
- [ ] Ölç: desteklenmeyen iddia oranı, kanıt bağlantı doğruluğu, p50/p95 gecikme, çıktı başına maliyet, toparlama başarısı.
- [ ] Multi-agent vs tek-agent sonucu ne çıkarsa dürüstçe raporla.

## 25 Ekim — dağıtım

- [ ] Dağıtım (ör. Container Apps); temiz tarayıcıdan jüri erişimi; ücretsiz, kısıtsız erişim süresi.
- [ ] Playwright MCP ile persona geçişi ve kanıt çekmecesi uçtan uca testi.
- [ ] README (İngilizce): kurulum, seed ile tekrar üretim, verinin sentetik olduğu.

## 26 Ekim — teslim materyalleri

- [ ] < 2 dakikalık video (hedef 110 sn: problem 10 / replay+persona 55 / kanıt zinciri 15 / hata toparlama 15 / ölçüm+stack 15).
- [ ] Tüm materyaller İngilizce; Türkçe raporlardan gerekenleri çevir.
- [ ] Ölçülmeyen iddiaları kullanma ("real time", "hallucination-free", "enterprise-ready"…); resmî Microsoft/PL ürünü izlenimi verme.

## 27 Ekim — erken teslim

- [ ] Son kontrol: public repo + video linki, secret taraması, seed tekrar üretimi, jüri erişimi.
- [ ] Teslim; 28 Ekim 09:59 sınırına tampon bırak.

## Backlog (inceleme notları, engelleyici değil)

- Baskı kartı eşiğe tam eşit tetikleniyor (6/10 = 0,6); senaryo yeniden üretilirse 2060–2062'ye kayabilir.
- Backend testleri 0,5 sn → 9 sn (kartlar her sequence için API'den çağrılıyor); gerekirse örnekle.
- `fixes2.test.tsx` "past the watermark" testi ara durumu da doğrulamalı (t≈160 ms'de snapshot null).
- Boş `p[role=status]` skor çubuğunda sıfır boyutlu öğe olarak gap'e katılıyor.
- `useAnalysis`: bekleyen trailing timer varken `matchId` değişirse eski closure çalışır (bugün erişilemez).
- Starlette TestClient `httpx2` uyarısı.
- Sayı denetimi sayının kaynağını doğruluyor, anlamını değil ("60 pressures" ← "60 s" penceresi geçer); anlam kontrolü Evidence Editor'da. Gerekirse sayı→metrik bağlama (claim içinde `{metric}` yer tutucuları).
- Bilinen yanlış retler (nadir): "final third", "a one-two", "sixteen", "4-4-2", alıntılanmayan olay saatleri.

## Kapsam dışı (zaman kalırsa)

İkinci dil, oyuncu lensi, gelişmiş animasyon, gerçek veri sağlayıcısı (SportMonks/API-Football: lisans ve anahtar gerekir), DBHub/Qdrant/AntV, A2A.

## Depo hijyeni

- [x] `reports/`, `research_notes/` (özel link + kuralların kopyası) ve uzak MCP ham çıktıları depodan çıkarıldı, yerelde duruyor.
- [ ] Public'e açmadan önce geçmişi temizle: eski commit'lerde bu dosyalar ve kişisel e-posta var → tek temiz commit'le, GitHub noreply e-postasıyla yayınla.

# Yapılacaklar

Tarihler İstanbul saatiyle. Kayıt sonu **20 Ekim 22:00**, teslim sonu **28 Ekim 09:59** (resmî kurallar §1).

## Bugün (20 Ekim)

- [ ] **Hackathon kaydını kontrol et / tamamla — 22:00'de kapanıyor.**
- [ ] Kategori kararı: Best Multi-Agent mi, başka kategori mi?
- [ ] Takım: tek kişi mi, en fazla 4 kişi mi? Takvimdeki kesintiler buna göre.
- [ ] Gerçek model erişimi: Foundry aboneliği, bölge, model kotası, `az login` (Azure CLI kurulu değil).
- [ ] Önceki sohbetteki fikir varsa elle buraya aktar; raporlardaki ürün kapsamı bunun yerine kurulmuş bir varsayım.
- [x] `git init` (yerel, `main`).
- [ ] Public GitHub deposu (yeni proje şartı, secret yok).
- [ ] Tek sentetik senaryo + olay şeması (`match_id`, `event_id`, `sequence`, `event_time_ms`, `team_id`, `player_id`, `type`, `outcome`, koordinatlar, `scenario_seed`, `synthetic=true`).

## 21 Ekim — uçtan uca ince dilim

- [x] Klasör yapısı: `apps/web`, `services/api`, `src/{workflow,agents,domain,contracts}`, `scenarios`, `evals`, `docs`, `infra`.
- [ ] Deterministik reducer + metrikler (`domain`), replay, skor, şablon kart.
- [ ] Football MCP fixture'daki dört fonksiyonu gerçek veri katmanına taşı (önce doğrudan fonksiyon, MCP adaptörü sonra). Mevcut 11 test sözleşme testi olarak korunur.

## 22 Ekim — agentlar

- [ ] Tactical Analyst, Evidence Editor, Audience Storyteller; Agent Framework workflow'u (state machine).
- [ ] Typed devir artefact'ı (`run_id`, `snapshot_version`, `candidate_id`, `trace_id`, claims, review, overlay).
- [ ] Tek-agent baseline (aynı model, metrik, kanıt paketi ve çıktı şeması).

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

## Kapsam dışı (zaman kalırsa)

İkinci dil, oyuncu lensi, gelişmiş animasyon, gerçek veri sağlayıcısı (SportMonks/API-Football: lisans ve anahtar gerekir), DBHub/Qdrant/AntV, A2A.

## Depo hijyeni

- [ ] `mcp-tests/azure-tools.json` (1,3 MB) ve `results.json` (369 KB) public depoda tutulacak mı karar ver.
- [ ] `research_notes/.../official-rules-snapshot.md` kuralların kopyası; teslim deposuna konup konmayacağını kontrol et.

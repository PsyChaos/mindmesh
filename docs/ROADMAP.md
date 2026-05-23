# MindMesh Roadmap

Zorluk ve karmaşıklık sırasına göre. Her özellik bağımsız olarak implement edilebilir.

## Kısa Vadeli (MVP+1)

### 1. Finding severity filter
**Zorluk: Düşük** | Etki: Orta

Tool'lara `--min-severity` parametresi ekle. Reporter'da filtreleme yap.
- `src/mindmesh/output/report.py` — severity filtresi
- Tool'lara `min_severity` parametresi

### 2. Dry-run tüm tool'lara
**Zorluk: Düşük** | Etki: Orta

`review_code` zaten `dry_run` destekliyor. Aynı pattern'i `security_audit`, `bug_investigate`, `compare_providers`, `delegate_task`'a ekle.
- Her tool'a `dry_run: bool = False` parametresi
- `_run_review` zaten yönlendiriyor, sadece parametre eklenmeli

### 3. Endpoint health check
**Zorluk: Düşük** | Etki: Düşük

`list_endpoints` tool'una `--check` modu ekle. Basit prompt gönder, yanıt alırsa `healthy`, almazsa `unreachable`.
- `src/mindmesh/tools/list_endpoints.py` — health check modu
- Timeout kısa tut (5s)

### 4. Response caching
**Zorluk: Orta** | Etki: Yüksek

Aynı scope+prompt+endpoint kombinasyonu için cache. SQLite veya dosya tabanlı.
- `src/mindmesh/cache/` — yeni modül
- Cache key: hash(scope_content + template + endpoint)
- TTL config'den okunur
- `--no-cache` override

### 5. Custom prompt override
**Zorluk: Orta** | Etki: Orta

Kullanıcı `.mindmesh.yml`'de kendi prompt template path'ini belirtebilsin.
- `config.py` — `prompts_dir` alanı
- `PromptLoader` — custom dir desteği
- Fallback: built-in template'ler

### 6. Finding dedup / akıllı merge
**Zorluk: Orta** | Etki: Yüksek

Merger'da aynı dosya+satır+category'deki finding'leri daha akıllı grupla. Duplicate bulguları birleştir, unique olanları öne çıkar.
- `src/mindmesh/output/merger.py` — fuzzy match geliştirme
- Levenshtein veya embedding tabanlı benzerlik (opsiyonel)

## Uzun Vadeli

### 7. CI/CD entegrasyonu (GitHub Actions)
**Zorluk: Orta** | Etki: Yüksek

PR açıldığında otomatik review. SARIF output formatı.
- GitHub Action workflow dosyası
- `--output sarif` modu
- PR comment entegrasyonu (`gh pr comment`)

### 8. Typer CLI
**Zorluk: Orta** | Etki: Orta

Claude Code dışından kullanım. Mevcut tool fonksiyonlarını CLI'ya bağla.
- `src/mindmesh/cli.py` — Typer app
- Her tool → CLI komutu
- `pyproject.toml` — CLI entry point

### 9. Streaming response
**Zorluk: Yüksek** | Etki: Orta

Büyük plan/review'lar için kademeli sonuç. SSE veya streaming MCP.
- Adapter'lara streaming desteği
- MCP transport değişikliği (stdio → SSE)
- Progressive finding emit

### 10. Dashboard / history
**Zorluk: Yüksek** | Etki: Orta

Finding history, maliyet takibi, provider karşılaştırma istatistikleri.
- SQLite tabanlı history store
- FastAPI dashboard backend
- Basit web UI (React veya htmx)

### 11. Worktree isolation
**Zorluk: Yüksek** | Etki: Yüksek

Provider patch önerilerini izole git worktree'de test.
- `git worktree add` entegrasyonu
- Patch apply + test run + rollback
- Claude review sonrası merge kararı

## Faz 2 — Maliyet Optimizasyonu ve Otomasyon

### 12. Yerel güvenlik tarayıcı entegrasyonu (LLM-Free)
**Zorluk: Düşük-Orta** | Etki: Yüksek

LLM çağrısı yapmadan yerel CLI araçları (semgrep, bandit, snyk) çalıştır, JSON çıktıyı Finding formatına normalize et.
- `src/mindmesh/scanners/` — yeni modül
- Desteklenen araçlar: semgrep, bandit, snyk (otomatik tespit)
- JSON çıktı → Finding normalize → Reporter pipeline
- `mindmesh scan` CLI komutu + `local_scan` MCP tool
- Sıfır API maliyeti, offline çalışır
- Claude sadece "şu dosyanın 42. satırındaki SQL Injection'ı düzelt" talimatı alır

### 13. Context sıkıştırma (tree-sitter + LLM summarizer)
**Zorluk: Orta** | Etki: Yüksek

Büyük codebase context'ini sıkıştırarak token maliyetini %70-80 düşür.

**Aşama A — tree-sitter skeleton (LLM-free):**
- tree-sitter ile dosyadan fonksiyon/class imzaları çıkar, body'leri at
- Dosya başına ~%80 boyut azalması
- Scope `skeleton` olarak ekle
- LLM çağrısı yok, sıfır maliyet

**Aşama B — LLM summarizer:**
- Büyük dosyaları ucuz provider'a gönder, özet context üret
- Claude sadece özeti okur, gerektiğinde tam dosyaya gider
- Config: `context_compression.enabled`, `context_compression.endpoint`
- Kullanıcı hangi endpoint'i kullanacağını seçer (ör. `gemini-flash`, `ollama-local`)
- Seçilmezse config'deki en ucuz default endpoint kullanılır
- Default endpoint hata verirse → tree-sitter skeleton'a fallback (LLM-free)
- Fallback zinciri: kullanıcı endpoint → default endpoint → tree-sitter → ham dosya

### 14. Akıllı Git commit / PR açıklaması
**Zorluk: Düşük** | Etki: Orta

Git diff'i ucuz provider'a gönder, Conventional Commits formatında commit mesajı / PR açıklaması üret.
- `mindmesh commit` CLI komutu → diff al → ucuz endpoint → commit message
- `mindmesh pr` CLI komutu → tüm branch diff → PR title + body
- Provider seçimi: config'deki en ucuz endpoint veya `--endpoint` ile override
- Çıktı: conventional commit formatı (feat/fix/refactor/docs/test/chore)
- Claude token'ı harcanmaz, günlük iş akışı hızlanır

### 15. Maliyet ve token takibi
**Zorluk: Düşük** | Etki: Düşük-Orta

MindMesh provider çağrılarının token ve maliyet takibi.
- Provider response header'larından token sayısı parse et (OpenAI: usage.total_tokens)
- History store'a `input_tokens`, `output_tokens`, `estimated_cost_usd` ekle
- `mindmesh stats` komutuna maliyet kolonu ekle
- Config'de bütçe limiti: `budget.monthly_limit_usd`
- Limit aşılınca uyarı veya blok

---

## Durum Takibi

| # | Özellik | Durum |
|---|---------|-------|
| 1 | Severity filter | Tamamlandı |
| 2 | Dry-run tüm tool'lar | Tamamlandı |
| 3 | Endpoint health check | Tamamlandı |
| 4 | Response caching | Tamamlandı |
| 5 | Custom prompt override | Tamamlandı |
| 6 | Finding dedup / akıllı merge | Tamamlandı |
| 7 | CI/CD (GitHub Actions) | Tamamlandı |
| 8 | Typer CLI | Tamamlandı |
| 9 | Streaming response | Tamamlandı |
| 10 | Dashboard / history | Tamamlandı |
| 11 | Worktree isolation | Tamamlandı |
| 12 | Yerel güvenlik tarayıcı (LLM-Free) | Tamamlandı |
| 13 | Context sıkıştırma (AST + LLM) | Tamamlandı |
| 14 | Akıllı Git commit / PR | Tamamlandı |
| 15 | Maliyet ve token takibi | Tamamlandı |

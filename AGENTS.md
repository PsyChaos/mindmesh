# MindMesh — Agent Instructions

## Proje Nedir?

MindMesh, Claude Code icinde calisan bir MCP tabanli AI provider orchestration sistemidir. Claude ana karar verici olarak kalir, disardaki provider'lar (OpenAI, Gemini, Z.ai, Ollama) danisma/reviewer olarak calisir.

Temel akis:

```
Claude Code → MindMesh Plugin → MCP Server (stdio) → Provider Router → AI Provider
```

## Temel Felsefe

- Claude karar verir, MindMesh danisir, provider'lar gorus uretir
- Provider'lar repo uzerinde islem yapmaz, sadece analiz/oneri uretir
- Guvenlik varsayilan olarak siki: redaction zorunlu, block list aktif, fail-closed policy
- MindMesh karmasik eslesme/karar mantigi uygulamaz — veriyi organize eder, karari Claude'a birakir

## Domain Kavramlari

Bu kavramlar CONTEXT.md'de tanimlidir. Kod yazarken bu terimleri tutarli kullan:

| Kavram | Tanim |
|--------|-------|
| **Provider** | Dis AI servisi (OpenAI, Gemini, Ollama, Z.ai). Auth, API formati, rate limit |
| **Model** | Provider icerisindeki spesifik AI modeli (gpt-5.1, o3, gemini-2.5-pro) |
| **Endpoint** | Provider + Model + config. Tool'larin cagirdigi birim |
| **Finding** | Bir endpoint'in urettigi tek bulgu. Severity, category, dosya, satir, oneri icerir |
| **Merger** | Finding'leri gruplayan, eslesme ipuclari ureten katman. Kesin karar vermez |
| **Policy** | Uc bagimsiz katman: File Policy, Provider Policy, Permission Policy |
| **Cache** | SQLite response cache, TTL bazli, key = hash(endpoint+template+context) |
| **History** | SQLite run history, her tool calistirmasi kaydedilir |
| **Worktree** | Git worktree isolation, patch test icin gecici calisma dizini |
| **SARIF** | Static Analysis Results Interchange Format, GitHub Code Scanning entegrasyonu |
| **Registry** | Merkezi provider kayit sistemi. Adapter, alias, env map, known providers tek yerde |
| **Sandbox** | Docker container izolasyonu, worktree test calistirma icin. read-only mount, no-network |

## Tech Stack

```
Python 3.12+
uv (paket yonetimi, hatchling build backend)
Pydantic v2 (en guncel stable)
FastMCP (MCP Python SDK, high-level API)
httpx (SDK'siz provider'lar icin)
openai (AsyncOpenAI — OpenAI adapter)
google-genai (Gemini adapter)
PyYAML
pathspec
python-dotenv
Jinja2
subprocess git (GitPython kullanilmaz)
sqlite3 (stdlib — cache + history)
typer (CLI)
pytest
ruff
pyright
```

## Monorepo Yapisi

```
mindmesh/
├── pyproject.toml
├── .env.example
├── .mindmesh.example.yml
├── CONTEXT.md                       ← Domain glossary
├── AGENT.md                         ← Bu dosya
├── docs/projects.md                 ← Proje dokumani
├── plugin/                          ← Claude Code plugin
│   ├── .claude-plugin/plugin.json
│   ├── skills/                      ← SKILL.md dosyalari (komut tanimlari burada)
│   ├── agents/                      ← Faz 3'te aktif olacak
│   └── hooks/                       ← Faz 3'te aktif olacak
├── src/mindmesh/
│   ├── server.py                    ← FastMCP instance + tool registration (ince tutulan)
│   ├── config.py                    ← Pydantic config model'leri
│   ├── errors.py                    ← Custom exception hiyerarsisi (MindMeshError base)
│   ├── schemas.py                   ← Katmanlar arasi paylasilan model'ler (Finding, Message)
│   ├── providers/
│   │   ├── base.py                  ← ProviderAdapter ABC
│   │   ├── openai.py                ← OpenAI SDK adapter
│   │   ├── gemini.py                ← Gemini SDK adapter
│   │   ├── zai.py                   ← httpx adapter
│   │   └── ollama.py                ← httpx adapter
│   ├── context/
│   │   ├── collector.py             ← Aday dosyalari toplar
│   │   ├── git.py                   ← subprocess git cagrilari
│   │   ├── filters.py              ← Adaylari suzer (policy + teknik limitler)
│   │   ├── redactor.py              ← Secret/token maskeleme
│   │   ├── tokenizer.py             ← KB bazli boyut olcumu
│   │   ├── compressor.py            ← AST-based skeleton extraction (Python ast + generic regex)
│   │   └── summarizer.py            ← LLM summarizer + fallback to compressor
│   ├── policy/
│   │   ├── file_policy.py           ← Hangi dosya/dizin context'e dahil edilebilir?
│   │   ├── provider_policy.py       ← Hangi provider kullanilabilir? (fail-closed)
│   │   └── permission_policy.py     ← Hangi islem yapilabilir, hangisi onay ister?
│   ├── registry.py                  ← Merkezi ProviderRegistry (adapter, alias, env map)
│   ├── cache.py                     ← SQLite response cache
│   ├── history.py                   ← SQLite run history
│   ├── worktree.py                  ← Git worktree isolation (Docker sandbox destekli)
│   ├── cli.py                       ← Typer CLI (16 komut, human-readable default)
│   ├── scanners/
│   │   ├── base.py                  ← Scanner ABC + otomatik tespit
│   │   ├── bandit.py                ← Bandit JSON → Finding normalize
│   │   └── semgrep.py               ← Semgrep JSON → Finding normalize
│   ├── prompts/
│   │   ├── review.md                ← Jinja2 template
│   │   ├── security.md
│   │   ├── bug_investigate.md
│   │   ├── ask.md
│   │   ├── plan.md
│   │   ├── compare.md
│   │   ├── delegate.md
│   │   ├── commit.md
│   │   └── pr.md
│   ├── tools/
│   │   ├── ask.py                   ← Her tool kendi dosyasinda, register(mcp) pattern'i
│   │   ├── review.py
│   │   ├── security.py
│   │   ├── bugfix.py
│   │   ├── compare.py
│   │   ├── delegate.py
│   │   ├── list_endpoints.py
│   │   ├── preview.py
│   │   ├── validate.py
│   │   ├── test_patch.py
│   │   └── scan.py                  ← Yerel scanner (LLM-free, bandit/semgrep)
│   └── output/
│       ├── normalizer.py            ← Ham string → list[Finding]
│       ├── merger.py                ← Finding gruplama + eslesme ipuclari
│       ├── report.py                ← Final JSON rapor uretimi
│       └── sarif.py                 ← SARIF v2.1.0 formatter
├── .github/
│   └── workflows/
│       └── mindmesh-review.yml      ← CI/CD workflow
└── tests/
    ├── test_cache.py
    ├── test_prompt_loader.py
    ├── test_delegate_tool.py
    ├── test_sarif.py
    ├── test_registry.py
    ├── test_test_patch_tool.py
    ├── test_ask_tool.py
    ├── test_compare_tool.py
    ├── test_list_endpoints.py
    ├── test_reporter.py
    ├── test_merger.py
    ├── test_filters.py
    └── test_scan_tool.py
```

## Mimari Katmanlar ve Veri Akisi

```
Tool katmani
  → prompt template yukle (Jinja2) + degiskenleri doldur
  → Message listesi olustur (system + user rolleri)
  → Router'a gonder

Router (Provider Router Core)
  → Endpoint resolver: config'den adapter + model cozumle
  → Adapter lazy init (ilk kullanimda olusturulur)
  → asyncio.gather ile paralel cagri + bagimsiz timeout
  → Rate limit: exponential backoff, max 2 retry
  → Partial success: hatali endpoint digerlerini engellemez

Adapter
  → send(messages: list[Message], model: str, config: dict) -> str
  → Tek sorumluluk: mesajlari provider API formatina cevir, ham string don
  → Task-spesifik metot YOK

Normalizer
  → Ham string'den JSON parse (code fence soyma + 1 retry)
  → list[Finding] uret
  → Parse basarisizsa parse_error finding don

Merger
  → Finding'leri endpoint bazli grupla
  → Basit eslesme ipuclari uret (dosya + satir ±5 + category)
  → Kesin karar VERME — Claude karar verir

Reporter
  → Gruplanan findings + endpoint hatalari + metadata → final JSON
```

## Komut Isletme Sirasi (Kritik)

Her MCP tool cagrisi su siraya uyar:

```
1. Provider alias resolve (chatgpt → openai)
2. Provider policy kontrol (disabled? allowed? adapter kayitli mi?)
   → Basarisizsa DURUR, adim 3-12 calismaz
3. Permission policy kontrol (bu islem serbest mi?)
   → Basarisizsa DURUR, adim 4-12 calismaz
4. Scope belirlenir (git_diff, staged, branch, path)
5. File policy uygulanir (block_files, block_dirs)
6. Context pipeline calisir:
   collector → filters → redactor → tokenizer
7. KB limiti kontrol edilir
8. Endpoint'lere paralel istek gonderilir
8.5. Cache kontrol: response cache'te ayni endpoint+template+context hash varsa
     ve TTL dolmamissa → cache'ten dondur, provider'a istek gonderilmez
9. Sonuclar normalize edilir
10. Merger bulgulari gruplar
11. Reporter final JSON uretir
12. Claude kullaniciya sunar
```

## Kritik Tasarim Kararlari

### Provider Policy: Fail-Closed

- `disabled` listesi `allowed` listesinden gucludur
- Disabled provider'a KESINLIKLE istek gonderilmez
- Context toplanmis olsa bile disari cikmaz
- Validation sirasi: alias → disabled → allowed → adapter → OK
- Explicit provider disabled → block, fallback YOK
- Default provider disabled → config hatasi, otomatik fallback YOK
- Coklu endpoint'te: gecemeyen bloklanir, gecen calisir (partial)

### Erken Redaction

- Secret redaction context toplama aninda yapilir
- Redact edilmemis icerik bellekte ASLA tutulmaz
- Secret degeri hicbir yerde saklanmaz
- Tespit edilen secret'lar findings listesine kaydedilir (dosya, satir, pattern tipi)

### Adapter Saf Kalir

- Iki metot: `send(messages, model, config) -> str` ve `send_stream(...) -> AsyncIterator[str]`
- `send_stream` varsayilan olarak `send`'e fallback yapar. OpenAI ve Ollama native streaming destekler
- Task-spesifik mantik (review, security, bugfix) tool katmaninda yasir
- Rate limit, timeout, retry router'da yonetilir
- Config validation startup'ta, adapter init lazy (ilk kullanimda)
- ProviderRegistry: adapter'lar merkezi registry'de kayitli. Yeni provider eklemek tek satir

### JSON Parse Stratejisi

- Provider'dan strict JSON beklenir
- Code fence (`\`\`\`json`) otomatik soyulur
- Parse basarisizsa 1 kez retry: "Your response was not valid JSON. Return only JSON."
- Ikinci deneme de basarisizsa parse_error finding dondurilur, sessizce yutulmaz

### Partial Success

- Hatali endpoint digerleri engellemez
- Timeout, rate limit, policy violation → error finding olarak rapora eklenir
- Tek endpoint seciliyse ve cokers → dogrudan hata doner

### Confidence Alani

- Provider tarafindan hesaplanir (prompt'ta 0-1 arasi istenir)
- Model confidence kalibrasyonlari guvenilir DEGIL
- Claude kendi degerlendirmesini yapmalidir

## Context Pipeline

```
1. collector.py → scope'a gore aday dosyalari toplar
2. filters.py → suzer:
   - block_dirs, block_files kontrolu
   - binary dosya tespiti → atla
   - generated/minified → atla
   - dosya boyutu limiti (max_file_size_kb)
   - toplam context limiti (max_total_context_kb)
   - desteklenen text dosyasi mi?
   - symlink guvenli mi?
3. redactor.py → kalan dosyalarda secret/token maskeler
   - Regex pattern'ler (API key, PEM, SSH, password, connection string)
   - Findings listesi olusturulur (deger saklanmaz)
4. tokenizer.py → toplam KB hesaplanir
```

filters.py ile file_policy.py ayrimi:
- file_policy.py = kurallar (hangi path/pattern yasak?)
- filters.py = kurallari uygulayan suzgec

### Git Diff Cozumleme

```
--scope git_diff → akilli varsayilan:
  1. git diff HEAD (staged + unstaged)
  2. Boşsa → git diff <base_branch>...HEAD
  3. O da bossa → hata

--scope staged → git diff --staged
--scope branch → git diff <base_branch>...HEAD
--scope <path> → dosyanin tam icerigi (diff degil)
```

Base branch tespit: config > git remote show origin > "main" > "master"

### Context Sunum Formati

Provider'a structured metadata ile gonderilir:

```
## File: src/auth/session.py (modified)
Language: python
Lines: 42-88

def rotate_token(user):
    ...
```

## Config Sistemi

`.mindmesh.yml` opsiyoneldir. Yoksa sensible defaults uygulanir.

Yukleme sirasi:
1. `.mindmesh.yml` varsa yukle, yoksa varsayilanlar
2. Varsayilanlar: scope=git_diff, redact_secrets=true, siki block listeleri
3. Provider/endpoint config yoksa → env'deki API key'lerden otomatik endpoint olustur
4. Hicbir API key yoksa → acik hata

API key cozumleme:
1. Sistem environment variable
2. `.env` dosyasi (python-dotenv)
3. Yoksa hata

Cache config (`.mindmesh.yml` icinde opsiyonel):
```yaml
cache:
  enabled: true                # Varsayilan: true
  ttl_seconds: 3600            # Varsayilan: 1 saat
  max_entries: 1000            # Varsayilan: 1000
  db_path: .mindmesh/cache.db  # Varsayilan: proje kokunde
```

Prompts config (`.mindmesh.yml` icinde opsiyonel):
```yaml
prompts:
  custom_dir: .mindmesh/prompts       # Kullanici override'lari (oncelikli, fallback built-in)
```

Sandbox config (`.mindmesh.yml` icinde opsiyonel):
```yaml
sandbox:
  enabled: true                # Docker sandbox varsayilan acik
  image: python:3.12-slim     # Container image
  network: false               # Network izolasyonu
  memory_limit: 512m           # Bellek limiti
  cpu_limit: 1.0               # CPU limiti
```

Permissions config icinde test komutu whitelist:
```yaml
permissions:
  allowed_test_commands:
    - "uv run pytest"
    - "npm test"
    - "make test"
```

## Pydantic Model Dagitimi

- `schemas.py` → katmanlar arasi paylasilan (Finding, Message, ErrorFinding)
- `config.py` → config model'leri (MindMeshConfig, ProviderConfig, EndpointConfig)
- Her tool → kendi request/response model'leri (ReviewRequest, vb.)

Circular import onlemek icin: paylasilan model'ler schemas.py'da, katman-ozel model'ler kendi dosyasinda.

## Error Handling

Custom exception hiyerarsisi:

```
MindMeshError (base)
├── ProviderTimeoutError
├── RateLimitError
├── PolicyViolationError
│   ├── ProviderDisabledError
│   ├── DefaultProviderDisabledError
│   └── PermissionDeniedError
├── ParseError
├── ContextTooLargeError
├── SecretDetectedError
├── UnsupportedProviderError
├── InvalidApiKeyError
└── ModelUnavailableError
```

Her exception `to_finding()` metodu ile error Finding'e donusturulebilir.

## MCP Tool Return Formati

Tum tool'lar Claude'a structured JSON doner:

```json
{
  "summary": "...",
  "findings": [...],
  "endpoint_errors": [...],
  "match_hints": [{"finding_indices": [0, 3], "reason": "same file + line range + category"}],
  "metadata": {
    "endpoints_called": 3,
    "endpoints_succeeded": 2,
    "total_findings": 8,
    "context_size_kb": 45,
    "redacted_secrets": 2
  }
}
```

Claude bu JSON'i kullaniciya uygun formatta sunar.

## Prompt Template'ler

`src/mindmesh/prompts/` dizininde Jinja2 template'leri olarak yasir.
Tool katmani template'i yukler, degiskenleri doldurur, Message listesi olusturur.
System prompt (rol, kurallar, output format) ve user content (diff, dosyalar, soru) ayri Message nesneleri olarak hazirlanir.

## Provider Alias (ProviderRegistry)

Alias'lar `registry.py`'daki `ProviderRegistry`'de tanimlidir:

```
chatgpt → openai
local   → ollama
```

Registry ayrica adapter map, env auto-discovery ve known providers bilgisini merkezi tutar.
Yeni provider eklemek: `get_registry().register(ProviderInfo(name=..., ...))`

## Gelistirme Fazlari

### Faz 1a — Walking Skeleton (tek endpoint, tek tool)

```
MCP server (FastMCP + stdio), config (Pydantic), API key cozumleme,
provider adapter base + OpenAI adapter, endpoint resolver,
git diff context collector, secret redactor, file policy,
KB bazli limit, review_code tool + prompt, normalizer, hata yonetimi
```

### Faz 1b — Multi-endpoint, ikinci tool

```
Gemini adapter, paralel endpoint cagrilari, rate limit yonetimi,
partial success, merger, security_audit tool + prompt, list_endpoints tool
```

### Faz 2 — Ek tool'lar ✅ Tamamlandi

```
bug_investigate, compare_providers, ask_provider tool'lari,
endpoint bazli config override, daha fazla secret pattern, dry-run,
delegate_task, validate_policy, test_patch tool'lari,
SQLite response cache, run history, SARIF output,
plan.md / compare.md / delegate.md prompt template'leri
```

### Faz 3 — Plugin paketleme ✅ Tamamlandi

```
Skill dokumanlari (mindmesh:plan dahil), hook config, README,
Claude Code plugin packaging, .claude-plugin/plugin.json
```

### Faz 4 — Uretim hazirlik ✅ Tamamlandi

```
CLI (Typer), CI/CD (.github/workflows/mindmesh-review.yml),
git worktree isolation, guvenlik sertlestirme
```

### Faz 5+ — Gelecege donuk

```
Dashboard, metrik toplama, multi-repo destek,
provider benchmark suite, custom prompt template marketplace
```

## Test Stratejisi

MVP'de unit testler + mock adapter yeterlidir.

```
Unit testler       → FakeProviderAdapter ile. Provider API'sine dokunmaz.
Integration testler → Response fixture'lar ile. (Faz 2)
E2E testler        → Gercek API cagrisi, CI disi. (Faz 3+)
```

Test edilecek alanlar:
- Secret redaction, file/dir policy, endpoint resolver
- Normalization (JSON parse, code fence, retry)
- Merger (gruplama, eslesme ipuclari)
- Error handling (timeout, rate limit → error finding donusumu)
- Git diff collection, prompt template rendering
- Config yukleme (varsayilanlar, override, env var)
- KB bazli context limiti, provider policy (fail-closed)

## Kodlama Kurallari

- Immutable data structures tercih et
- Fonksiyonlar < 50 satir, dosyalar < 800 satir
- Type hint her yerde zorunlu (pyright strict)
- Hatalari sessizce yutma — explicit handle et veya error finding don
- Secret ASLA loglanmaz, saklanmaz, debug output'a yazilmaz
- Adapter'a task-spesifik metot EKLEME — tek `send` metodu yeterli
- Tool'a output formatlama mantigi KOYMA — reporter'in isi
- Provider'a fallback YAPMA (explicit secimdeyse) — fail-closed policy'ye uy
- `server.py` ince tutulur — sadece FastMCP instance + register cagilari
- Her tool kendi dosyasinda, `register(mcp)` pattern'i ile

## Referans Dokumanlar

- `CONTEXT.md` — Domain glossary (Provider, Model, Endpoint, Finding, Merger, Policy)
- `docs/projects.md` — Detayli proje dokumani (50+ karar, config ornekleri, prompt sablonlari)

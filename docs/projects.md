# MindMesh Proje Dokümanı

## 1. Proje Tanımı

**MindMesh**, Claude Code/Claude CLI içinde çalışan ve gerektiğinde farklı AI provider’lara danışabilen bir **AI provider orchestration** sistemidir.

Amaç; Claude’un tek başına karar vermesi yerine, gerektiğinde Gemini, ChatGPT/OpenAI, Z.ai, Ollama veya başka modellerden destek almasını sağlamaktır. Bu destek; code review, security check, bug investigation, bugfix önerisi, mimari analiz, test önerisi ve task delegation gibi görevlerde kullanılacaktır.

MindMesh doğrudan Claude’un yerine geçmez. Claude ana karar verici olarak kalır. Diğer provider’lar ise danışman, reviewer veya uzman alt sistem gibi çalışır.

---

## 2. Temel Fikir

MindMesh’in temel fikri şudur:

```text
Claude Code
  ↓
MindMesh Plugin
  ↓
MindMesh MCP Server
  ↓
Provider Router
  ↓
OpenAI / Gemini / Z.ai / Ollama / diğer provider’lar
```

Claude Code içinden kullanıcı doğal dil ile şunu diyebilir:

```text
Bu diff’i Gemini ve ChatGPT’ye review ettir.
```

Veya:

```text
Bu authentication modülünü security açısından farklı modellerle kontrol et.
```

Claude bu isteği MindMesh MCP tool’larına yönlendirir. MindMesh ilgili dosyaları/diff’i toplar, güvenlik filtresinden geçirir, seçilen provider’lara gönderir, cevapları normalize eder ve Claude’a anlamlı bir rapor olarak döndürür.

---

## 3. Projenin Ana Hedefleri

MindMesh’in ana hedefleri:

1. Claude Code içinden farklı AI provider’lara danışmak.
2. Codebase review, security audit ve bug investigation süreçlerini güçlendirmek.
3. Provider cevaplarını tek ve tutarlı bir formatta normalize etmek.
4. Secret, token, private key ve hassas dosyaların dış provider’lara gönderilmesini engellemek.
5. Claude’u ana karar verici olarak tutmak.
6. Dış provider’ları doğrudan repo üzerinde işlem yapan aktörler yerine danışman/reviewer olarak konumlandırmak.
7. İleride CI/CD, IDE, dashboard ve otomatik review sistemlerine genişleyebilecek bir çekirdek mimari oluşturmak.

---

## 4. Kapsam

### 4.1 MVP Kapsamı

İlk MVP şu özellikleri içermelidir:

```text
1. Claude Code plugin yapısı
2. Python tabanlı MCP server
3. Provider adapter mimarisi
4. OpenAI provider desteği
5. Gemini provider desteği
6. Z.ai veya başka provider için genişletilebilir yapı
7. Ollama/local model desteği için temel adapter alanı
8. Git diff/context toplama
9. Secret redaction
10. File allow/block policy
11. Code review tool’u
12. Security audit tool’u
13. Bug investigation tool’u
14. Multi-provider compare tool’u
15. Structured JSON response schema
```

### 4.2 MVP Dışında Bırakılacaklar

İlk sürümde şunlar yapılmamalıdır:

```text
1. Provider’ın doğrudan dosya değiştirmesi
2. Otomatik patch apply
3. Tam otonom agent execution
4. Dashboard
5. CI/CD entegrasyonu
6. Web panel
7. Kullanıcı yönetimi
8. Kalıcı veritabanı zorunluluğu
9. Full codebase gönderimini varsayılan yapmak
```

Bunlar sonraki fazlarda değerlendirilebilir.

---

## 5. Temel Mimari

MindMesh üç ana katmandan oluşur:

```text
MindMesh Plugin
MindMesh MCP Server
Provider Router Core
```

### 5.1 MindMesh Plugin

Claude Code tarafındaki entegrasyon katmanıdır.

Görevleri:

```text
- Claude Code’a komut/skill/agent/hook tanıtmak
- MCP server bağlantısını paketlemek
- Kullanıcıya doğal Claude Code deneyimi sunmak
- Review, security, bug investigation gibi workflow’ları tanımlamak
```

Plugin tek başına provider çağrısı yapmaz. Provider çağrıları MCP server üzerinden yürütülür.

### 5.2 MindMesh MCP Server

Claude’un çağıracağı tool’ları sağlar. MVP’de stdio transport kullanılır — Claude Code, MCP server’ı subprocess olarak başlatır ve stdin/stdout üzerinden iletişim kurar.

Plugin config örneği:

```json
{
  "mcpServers": {
    "mindmesh": {
      "command": "uv",
      "args": ["run", "mindmesh-mcp"],
      "env": {}
    }
  }
}
```

HTTP transport (Streamable HTTP / SSE) sonraki fazda CI/CD, dashboard ve uzaktan erişim ihtiyaçları için eklenebilir. İç mimari transport’a bağımlı olmayacak şekilde yazılmalıdır.

`server.py` sadece FastMCP instance oluşturur ve tool modüllerini register eder. Tool iş mantığı `tools/` dizinindeki modüllerde yaşar:

```python
# server.py
from mcp.server.fastmcp import FastMCP
from mindmesh.tools import review, security, ask, bugfix, compare

mcp = FastMCP("mindmesh")

review.register(mcp)
security.register(mcp)
ask.register(mcp)
bugfix.register(mcp)
compare.register(mcp)
```

Örnek MCP tool’ları:

```text
mindmesh.ask_provider
mindmesh.review_code
mindmesh.security_audit
mindmesh.bug_investigate
mindmesh.compare_providers
mindmesh.delegate_task
mindmesh.list_endpoints
mindmesh.preview_context
mindmesh.validate_policy
```

MCP server’ın görevleri:

```text
- Claude’dan gelen tool çağrılarını almak
- İstekleri validate etmek
- Context toplamak
- Policy uygulamak
- Redaction yapmak
- Provider router core’u çağırmak
- Sonucu normalize edip Claude’a döndürmek
```

### 5.3 Provider Router Core

Asıl orkestrasyon motorudur.

Görevleri:

```text
- Endpoint resolver ile endpoint tanımlarını çözümlemek
- Provider adapter’larını çağırmak
- Çoklu endpoint çağrılarını paralel yürütmek (asyncio.gather)
- Her endpoint için bağımsız timeout uygulamak (varsayılan: 30s)
- Rate limit yönetimi (exponential backoff, max 2 retry)
- Timeout veya rate limit aşımında ilgili endpoint için error finding döndürmek
- Diğer endpoint sonuçlarını hatalardan bağımsız döndürmek
- Normalizer ile ham cevapları Finding listesine çevirmek
- Merger ile bulguları gruplamak
- Claude’a temiz sonuç döndürmek
```

Rate limit, timeout ve adapter hataları router tarafından yönetilir. Adapter saf kalır — sadece mesaj gönderir, cevap döner. Fallback (alternatif endpoint’e yönlendirme) sonraki fazda eklenebilir.

---

## 6. Neden Ekstra CLI Zorunlu Değil?

MindMesh’in ana kullanım yolu Claude Code üzerinden olacaktır.

Bu nedenle ilk MVP için ayrı bir CLI zorunlu değildir.

Ana akış:

```text
Claude Code → MindMesh Plugin → MCP Server → Provider Router → AI Provider
```

CLI ancak ileride şu amaçlarla eklenebilir:

```text
- Debug
- Lokal test
- CI/CD entegrasyonu
- Claude dışı kullanım
- GitHub Actions otomasyonu
- Bağımsız ürünleştirme
```

MVP’de CLI yapılmayabilir. Ama iç fonksiyonlar daha sonra CLI eklenebilecek şekilde ayrıştırılmalıdır.

Örneğin:

```python
async def review_code(request: ReviewRequest) -> ReviewResult:
    ...
```

Bu fonksiyon bugün MCP tool tarafından çağrılır. İleride CLI da aynı fonksiyonu çağırabilir.

---

## 7. Dil ve Teknoloji Tercihi

### 7.1 MCP Server Dili

MCP server için önerilen dil: **Python**.

Neden Python?

```text
- AI provider SDK’larıyla uyumlu
- Hızlı MVP geliştirme imkanı
- FastAPI, Pydantic, httpx, Typer gibi güçlü ekosistem
- Context processing için uygun
- Dosya/diff/redaction işlemleri kolay
- Kullanıcının mevcut Python/FastAPI deneyimine uygun
```

### 7.2 Önerilen Backend Stack

```text
Python 3.12+
uv
Pydantic v2 (en güncel stable sürüm)
httpx
PyYAML / ruamel.yaml
pathspec
python-dotenv
Jinja2
openai (AsyncOpenAI — OpenAI adapter için)
google-genai (Gemini adapter için)
httpx (Ollama, Z.ai gibi SDK'sız provider'lar için)
subprocess git (GitPython kullanılmaz — MindMesh sadece okuma yapıyor, ağır bağımlılık gereksiz)
MCP Python SDK (FastMCP high-level API)
pytest
ruff
pyright
```

API key çözümleme önceliği:

```text
1. Sistem environment variable (CI/CD, production)
2. .env dosyası (lokal geliştirme, python-dotenv ile yüklenir)
3. Yoksa açık hata: "OPENAI_API_KEY not found in environment or .env"
```

`.env` dosyası `.gitignore`'da olmalıdır.

### 7.3 Opsiyonel Gelecek Bileşenler

```text
FastAPI → HTTP API veya dashboard için
Typer → CLI için
SQLite → lokal history/cache için
Redis → provider response cache/rate limit için
Docker → izole çalışma için
```

---

## 8. Monorepo Yapısı

Plugin ve MCP server aynı repo'da yaşar. Tek versiyon, tek release döngüsü. Plugin'in skill tanımları MCP tool isimlerine doğrudan referans verdiği için sıkı bağlıdırlar.

Önerilen monorepo yapısı:

```text
mindmesh/
├── pyproject.toml
├── README.md
├── .env.example
├── .mindmesh.example.yml
├── CONTEXT.md
├── docs/
│   └── projects.md
├── plugin/
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── skills/
│   │   ├── ask-provider/
│   │   │   └── SKILL.md
│   │   ├── multi-review/
│   │   │   └── SKILL.md
│   │   ├── security-audit/
│   │   │   └── SKILL.md
│   │   └── bug-investigate/
│   │       └── SKILL.md
│   ├── agents/
│   │   ├── external-consultant.md
│   │   ├── security-reviewer.md
│   │   ├── codebase-analyst.md
│   │   └── bug-hunter.md
│   └── hooks/
│       └── hooks.json
├── src/
│   └── mindmesh/
│       ├── __init__.py
│       ├── server.py
│       ├── config.py             ← Config model'leri (MindMeshConfig, ProviderConfig, EndpointConfig)
│       ├── errors.py              ← Custom exception hiyerarşisi (MindMeshError base, to_finding() metodu)
│       ├── schemas.py            ← Katmanlar arası paylaşılan model'ler (Finding, Message, ErrorFinding)
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── openai.py
│       │   ├── gemini.py
│       │   ├── zai.py
│       │   └── ollama.py
│       ├── context/
│       │   ├── __init__.py
│       │   ├── collector.py         ← Aday dosyaları toplar (scope'a göre)
│       │   ├── git.py               ← subprocess git çağrıları (diff, status, log)
│       │   ├── filters.py           ← Adayları süzer (policy + teknik limitler uygular)
│       │   ├── redactor.py          ← Kalan içerikteki secret/token değerlerini maskeler
│       │   └── tokenizer.py         ← KB bazlı context boyutu ölçer
│       ├── policy/
│       │   ├── __init__.py
│       │   ├── file_policy.py         ← Hangi dosya/dizin context'e dahil edilebilir?
│       │   ├── provider_policy.py     ← Hangi provider kullanılabilir?
│       │   └── permission_policy.py   ← Hangi işlem yapılabilir, hangisi onay ister?
│       ├── prompts/
│       │   ├── review.md
│       │   ├── security.md
│       │   ├── bug_investigate.md
│       │   └── ask.md
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── ask.py
│       │   ├── review.py
│       │   ├── security.py
│       │   ├── bugfix.py
│       │   └── compare.py
│       ├── output/
│       │   ├── __init__.py
│       │   ├── normalizer.py
│       │   ├── merger.py
│       │   └── report.py
│       └── tests/
│           ├── test_redactor.py
│           ├── test_file_policy.py
│           ├── test_provider_router.py
│           └── test_review_tool.py
└── tests/
```

### 8.1 Plugin Manifest

```json
{
  "name": "mindmesh",
  "displayName": "MindMesh",
  "description": "Multi-provider AI consultation and code review orchestration for Claude Code.",
  "version": "0.1.0"
}
```

---

## 9. Konfigürasyon Dosyası

`.mindmesh.yml` dosyası opsiyoneldir. Yoksa sensible defaults uygulanır.

Config yükleme akışı:

```text
1. .mindmesh.yml varsa yükle, yoksa varsayılanları uygula
2. Varsayılanlar: scope=git_diff, redact_secrets=true, sıkı block listeleri
3. Provider/endpoint tanımları config'de yoksa → environment'taki API key'lerden otomatik endpoint oluştur
4. Hiçbir provider'ın API key'i environment'da yoksa → açık hata mesajı
```

Kullanıcı sadece varsayılanları override etmek istediğinde config oluşturur.

Örnek:

```yaml
project:
  name: my-project
  default_scope: git_diff

providers:
  openai:
    api_key_env: OPENAI_API_KEY
  gemini:
    api_key_env: GEMINI_API_KEY
  zai:
    api_key_env: ZAI_API_KEY
  ollama:
    base_url: http://localhost:11434
  disabled: []

endpoints:
  openai-review:
    provider: openai
    model: gpt-5.1
    timeout_seconds: 30
  openai-security:
    provider: openai
    model: o3
    timeout_seconds: 45
  gemini-default:
    provider: gemini
    model: gemini-2.5-pro
    timeout_seconds: 30
  zai-default:
    provider: zai
    model: glm-4.6
    timeout_seconds: 30
  ollama-local:
    provider: ollama
    model: qwen2.5-coder
    timeout_seconds: 60

privacy:
  redact_secrets: true
  block_files:
    - ".env"
    - ".env.*"
    - "*.pem"
    - "*.key"
    - "id_rsa"
    - "id_ed25519"
    - "secrets/**"
    - "config/production.*"
  block_dirs:
    - "node_modules"
    - "vendor"
    - "dist"
    - "build"
    - ".git"
    - ".next"
    - "coverage"

limits:
  max_files: 50
  max_file_size_kb: 120
  max_total_context_kb: 1024
  prefer_git_diff: true

permissions:
  allow_full_codebase_context: false        # Full codebase gönderimi serbest mi?
  allow_external_patch: false               # Provider patch önerebilir mi?
  allow_auto_apply_patch: false             # Patch otomatik uygulanabilir mi?
  require_confirmation_for_large_context: true   # Büyük context için onay iste
  require_confirmation_for_external_provider: false  # Dış provider kullanımı için onay iste

review:
  default_endpoints:
    - openai-review
    - gemini-default
  output_format: structured_findings
```

---

## 11. Komut Arayüzü ve MCP Tool Mapping

MindMesh kullanıcıya Claude Code içinde slash command mantığıyla görünmelidir.

Canonical komut seti aşağıdaki gibi kabul edilir:

```text
/mindmesh:ask gemini "Bu mimari mantıklı mı?"
/mindmesh:review --provider chatgpt --scope src/
/mindmesh:security --providers gemini,chatgpt,zai
/mindmesh:bughunt --issue "login bazen 500 dönüyor"
/mindmesh:delegate --provider gemini --task "large context codebase summary"
/mindmesh:compare --task "bu PR güvenli mi?"
```

Bu komutlar doğrudan provider API çağırmaz. Slash command önce Claude Code skill/command katmanında yorumlanır, sonra uygun MindMesh MCP tool’una çevrilir.

Genel akış:

```text
Slash Command
  ↓
MindMesh Skill / Command Definition
  ↓
Claude Code
  ↓
MindMesh MCP Tool
  ↓
Provider Router Core
  ↓
External Provider
```

### 11.1 Komut ve MCP Tool Eşleşmesi

```text
/mindmesh:ask
  → mindmesh.ask_provider

/mindmesh:review
  → mindmesh.review_code

/mindmesh:security
  → mindmesh.security_audit

/mindmesh:bughunt
  → mindmesh.bug_investigate

/mindmesh:delegate
  → mindmesh.delegate_task

/mindmesh:plan
  → mindmesh.delegate_task (mode="planning")

/mindmesh:compare
  → mindmesh.compare_providers
```

Yani kullanıcı tarafında sade ve akılda kalıcı komutlar olur. MCP tarafında ise daha açık ve makine dostu tool isimleri kullanılır.

---

## 11.2 `/mindmesh:ask`

Amaç: Tek bir provider’a genel soru sormak.

Kullanım:

```text
/mindmesh:ask gemini "Bu mimari mantıklı mı?"
```

Alternatif:

```text
/mindmesh:ask chatgpt "Bu çözümde kaçırdığım risk var mı?"
```

MCP mapping:

```text
mindmesh.ask_provider
```

Parsed input:

```json
{
  "provider": "gemini",
  "question": "Bu mimari mantıklı mı?",
  "context_mode": "none"
}
```

MCP output:

```json
{
  "provider": "gemini",
  "answer": "...",
  "summary": "...",
  "warnings": []
}
```

Notlar:

```text
- Varsayılan olarak codebase context gönderilmez.
- Kullanıcı açıkça isterse diff/path context eklenebilir.
- Genel mimari, fikir doğrulama ve alternatif yaklaşım sormak için kullanılır.
```

---

## 11.3 `/mindmesh:review`

Amaç: Kod review yaptırmak.

Kullanım:

```text
/mindmesh:review --provider chatgpt --scope src/
```

Çoklu provider kullanımı:

```text
/mindmesh:review --providers gemini,chatgpt --scope git_diff
```

MCP mapping:

```text
mindmesh.review_code
```

Parsed input:

```json
{
  "providers": ["chatgpt"],
  "scope": "src/",
  "focus": ["bugs", "architecture", "performance", "maintainability"],
  "include_patch_suggestions": true
}
```

Scope değerleri:

```text
git_diff
staged_diff
current_file
src/
src/auth
specific file path
```

Notlar:

```text
- `--provider` tek provider içindir.
- `--providers` çoklu provider içindir.
- `--scope` verilmezse varsayılan `git_diff` olmalıdır.
- Review çıktısı doğrudan patch apply etmez.
```

---

## 11.4 `/mindmesh:security`

Amaç: Security odaklı analiz yaptırmak.

Kullanım:

```text
/mindmesh:security --providers gemini,chatgpt,zai
```

Opsiyonel scope ile:

```text
/mindmesh:security --providers gemini,chatgpt --scope src/auth
```

MCP mapping:

```text
mindmesh.security_audit
```

Parsed input:

```json
{
  "providers": ["gemini", "chatgpt", "zai"],
  "scope": "git_diff",
  "focus": ["auth", "authorization", "secrets", "injection", "ssrf", "path_traversal"]
}
```

Notlar:

```text
- Scope verilmezse güvenlik analizi git diff üzerinden yapılır.
- Secret redaction zorunludur.
- Kritik dosya tespit edilirse kullanıcıdan onay istenebilir.
- Sonuç severity bazlı gruplanır.
```

---

## 11.5 `/mindmesh:bughunt`

Amaç: Bir bug/hata davranışı için farklı provider’lardan sebep ve çözüm önerisi almak.

Kullanım:

```text
/mindmesh:bughunt --issue "login bazen 500 dönüyor"
```

Daha detaylı kullanım:

```text
/mindmesh:bughunt --issue "login bazen 500 dönüyor" --scope src/auth --providers gemini,chatgpt
```

MCP mapping:

```text
mindmesh.bug_investigate
```

Parsed input:

```json
{
  "providers": ["openai", "gemini"],
  "issue": "login bazen 500 dönüyor",
  "scope": "git_diff",
  "logs": null,
  "paths": []
}
```

Notlar:

```text
- Provider belirtilmezse config içindeki default bughunt provider listesi kullanılır.
- Log verilirse prompt’a eklenir.
- İlgili dosyalar scope veya Claude’un mevcut context’inden çıkarılır.
- Çıktı probable causes, evidence, fix plan ve test suggestions içermelidir.
```

---

## 11.6 `/mindmesh:delegate`

Amaç: Belirli bir görevi seçilen provider’a danışman/subagent gibi devretmek.

Kullanım:

```text
/mindmesh:delegate --provider gemini --task "large context codebase summary"
```

MCP mapping:

```text
mindmesh.delegate_task
```

Parsed input:

```json
{
  "provider": "gemini",
  "task": "large context codebase summary",
  "scope": "auto",
  "mode": "advisory",
  "allow_patch": false
}
```

Delegation mode değerleri:

```text
advisory
analysis
review
planning
patch_suggestion
```

MVP için varsayılan:

```text
mode: advisory
allow_patch: false
```

Notlar:

```text
- Delegate komutu provider’a doğrudan repo değiştirme yetkisi vermez.
- Provider sadece analiz, özet, plan veya patch önerisi üretir.
- Claude nihai karar verici olarak kalır.
- Large context işlemlerinde context limiti ve redaction zorunludur.
```

---

## 11.7 `/mindmesh:compare`

Amaç: Bir task hakkında birden fazla provider görüşünü karşılaştırmak.

Kullanım:

```text
/mindmesh:compare --task "bu PR güvenli mi?"
```

Provider seçerek:

```text
/mindmesh:compare --task "bu PR güvenli mi?" --providers gemini,chatgpt,zai
```

MCP mapping:

```text
mindmesh.compare_providers
```

Parsed input:

```json
{
  "task": "bu PR güvenli mi?",
  "providers": ["openai", "gemini"],
  "scope": "git_diff",
  "comparison_mode": "agreement_conflict"
}
```

Output şunları içermelidir:

```text
- Ortak bulgular
- Çelişen bulgular
- Tek provider’ın fark ettiği bulgular
- Provider güven seviyesi
- Claude için önerilen karar
- Aksiyon planı
```

---

## 11.8 Komut Parametre Standardı

MindMesh komutlarında ortak parametreler şöyle olmalıdır:

```text
--endpoint <name>       Tek endpoint seçer (config'deki endpoint adı)
--endpoints <a,b,c>     Çoklu endpoint seçer
--provider <name>       Kısayol: provider'ın varsayılan endpoint'ini seçer
--providers <a,b,c>     Kısayol: her provider'ın varsayılan endpoint'ini seçer
--scope <path|mode>     Context kapsamını belirler
--focus <a,b,c>         Analiz odağını belirler
--issue <text>          Bug/hata açıklaması
--task <text>           Delegation veya compare task metni
--no-patch              Patch önerisi istemez
--json                  Makine okunabilir JSON çıktı ister
--dry-run               Endpoint çağrısı yapmadan context/policy preview gösterir (Faz 2)
```

`--provider` ve `--providers` parametreleri kullanıcı kolaylığı içindir. Dahili olarak endpoint'lere çözümlenir.

Provider alias standardı:

```text
chatgpt → openai
openai  → openai
gemini  → gemini
zai     → zai
ollama  → ollama
local   → ollama
```

Bu alias mapping config üzerinden değiştirilebilir olmalıdır. Alias çözümleme sırası: alias → provider → varsayılan endpoint.

---

## 11.9 Komut Dosyası Yapısı

Ayrı `commands/` dizini yoktur. Komut tanımları `plugin/skills/` içindeki SKILL.md dosyalarında yaşar. Her SKILL.md şunları tanımlar:

```text
- Komut amacı
- Parametreler
- Varsayılan değerler
- Hangi MCP tool’un çağrılacağı
- Hangi context’in toplanacağı
- Hangi güvenlik policy’lerinin uygulanacağı
- Claude’un kullanıcıya nasıl rapor döneceği
```

Tek kaynak, tek doğru. Tekrar yok.

---

## 11.10 Komutların İç Davranış Kuralları

Tüm MindMesh komutları şu kurallara uymalıdır:

```text
1. Provider alias resolve edilir (chatgpt → openai)
2. Provider policy kontrol edilir (disabled? allowed? adapter kayıtlı mı?)
3. Permission policy kontrol edilir (bu işlem serbest mi? onay gerekiyor mu?)
4. Scope belirlenir (git_diff, staged, branch, path)
5. File policy uygulanır (block_files, block_dirs)
6. Secret redaction yapılır (context toplama anında, erken redaction)
7. KB limiti kontrol edilir (max_file_size_kb, max_total_context_kb)
8. Endpoint'lere paralel istek gönderilir (asyncio.gather + bağımsız timeout)
9. Sonuçlar normalize edilir (JSON parse + retry)
10. Merger bulguları gruplar, eşleşme ipuçları üretir
11. Reporter final JSON rapor üretir
12. Claude kullanıcıya rapor sunar
```

Provider policy başarısızsa adım 3-12 çalışmaz. Permission policy başarısızsa adım 4-12 çalışmaz. Gereksiz iş yapılmaz.

---

## 11.11 Güncellenmiş MCP Tool Listesi

MindMesh MCP server şu tool’ları expose etmelidir:

```text
mindmesh.ask_provider
mindmesh.review_code
mindmesh.security_audit
mindmesh.bug_investigate
mindmesh.delegate_task
mindmesh.compare_providers
mindmesh.list_endpoints
mindmesh.preview_context
mindmesh.validate_policy
```

`list_endpoints` çıktısı config bazlıdır, gerçek bağlantı testi yapmaz:

```json
{
  "endpoints": [
    {"name": "openai-review", "provider": "openai", "model": "gpt-5.1", "status": "ready"},
    {"name": "gemini-default", "provider": "gemini", "model": "gemini-2.5-pro", "status": "no_api_key"},
    {"name": "ollama-local", "provider": "ollama", "model": "qwen2.5-coder", "status": "disabled"}
  ]
}
```

Status değerleri: `ready` (API key var), `no_api_key` (key bulunamadı), `disabled` (config’de kapalı).

Tüm tool’lar implement edilmiştir:

```text
mindmesh.ask_provider
mindmesh.review_code
mindmesh.security_audit
mindmesh.bug_investigate
mindmesh.compare_providers
mindmesh.delegate_task
mindmesh.list_endpoints
mindmesh.preview_context
mindmesh.validate_policy
```

---

## 12. Provider, Endpoint ve Adapter Mimarisi

MindMesh üç katmanlı bir soyutlama kullanır:

```text
Provider  = Dış AI servisi (OpenAI, Gemini, Ollama, Z.ai). Auth, API formatı, rate limit.
Model     = Provider içindeki spesifik model (gpt-5.1, o3, gemini-2.5-pro).
Endpoint  = Provider + Model + opsiyonel config. Tool’ların çağırdığı birim.
```

Bir Provider birden fazla Endpoint’e sahip olabilir (farklı modeller veya farklı ayarlar için).

### 12.1 Adapter Lifecycle

```text
Startup   → Config validation (API key’ler, endpoint tanımları doğru mu?)
Runtime   → Adapter lazy init (ilk send() çağrısında oluşturulur)
```

Config validation startup’ta yapılır — yanlış config erken yakalanır. Adapter nesneleri ve SDK import’ları ilk kullanımda gerçekleşir — kullanılmayan provider’ların SDK’sı yüklenmez.

### 12.2 Provider Adapter Interface

Her provider aynı interface’i uygulamalıdır. Adapter, provider’a özgü API farklarını gizler.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Message:
    role: str   # "system" | "user"
    content: str

class ProviderAdapter(ABC):
    name: str

    @abstractmethod
    async def send(self, messages: list[Message], model: str, config: dict) -> str:
        pass
```

Adapter’lar task-spesifik metotlar (review_code, security_audit vb.) içermez. Tek sorumluluğu: mesaj listesini ilgili provider API formatına çevirip göndermek ve ham cevabı döndürmek.

Tool katmanı system prompt (rol tanımı, kurallar, output format) ve user content’i (diff, dosyalar, soru) ayrı Message nesneleri olarak hazırlar. Her adapter bu listeyi kendi API’sine uygun formata dönüştürür.

MVP’de sadece system + user rolleri yeterlidir. Multi-turn conversation desteği sonraki fazda eklenebilir.

### 12.2 Endpoint Resolver

Endpoint resolver, config’deki endpoint tanımlarını çözümler:

```text
"openai-review" → OpenAI adapter + gpt-5.1 model + varsayılan config
"openai-security" → OpenAI adapter + o3 model + varsayılan config
"gemini-default" → Gemini adapter + gemini-2.5-pro model + varsayılan config
```

### 12.3 Adapter Örnekleri

```text
OpenAI adapter → OpenAI API formatını bilir
Gemini adapter → Gemini API formatını bilir
Z.ai adapter → Z.ai API formatını bilir
Ollama adapter → lokal HTTP endpoint formatını bilir
```

MindMesh core tüm provider’larla aynı soyut interface üzerinden konuşur.

---

## 13. Response Normalization

Response normalization ayrı bir katman olarak çalışır. Adapter ham string döner, normalizer bu string’i structured `Finding` listesine çevirir.

Veri akışı:

```text
Tool katmanı
  → prompt hazırla
  → Adapter.send(messages, model, config) → ham string
  → Normalizer.parse(ham_string, task_type) → list[Finding]
  → Merger.merge(findings_per_endpoint) → final rapor
```

Sorumluluk ayrımı:

```text
Adapter     → sadece API iletişimi, ham string döner
Normalizer  → ham string’i Finding listesine çevirir
Merger      → birden fazla endpoint’ten gelen Finding’leri gruplar, eşleşme ipuçları üretir
Reporter    → gruplanmış findings’i final JSON rapora çevirir (summary, severity sıralaması, metadata)
Tool        → prompt hazırlar, akışı koordine eder
Claude      → nihai karar verici: eşleşme, çakışma ve aksiyon kararlarını verir
```

### 13.2 Merger Stratejisi

Merger karmaşık eşleşme algoritması uygulamaz. Temel işi temiz sunum:

```text
1. Basit eşleşme ipuçları üretir (dosya + satır aralığı ±5 + category)
2. Finding’leri endpoint bazlı gruplar
3. Eşleşme ipuçlarını annotasyon olarak ekler
4. Tüm bulguları Claude’a organize şekilde sunar
5. Claude semantik analiz, çakışma tespiti ve nihai kararı verir
```

Bu yaklaşım MindMesh’in temel felsefesiyle tutarlıdır: MindMesh danışır, Claude karar verir. Merger’ın görevi kesin eşleşme kararı vermek değil, Claude’un karar vermesini kolaylaştırmaktır.

Provider cevap formatı değişirse sadece normalizer güncellenir. Yeni task tipi eklenirse sadece tool katmanı güncellenir.

Örnek bulgu schema’sı:

```json
{
  "endpoint": "openai-review",
  "provider": "openai",
  "model": "gpt-5.1",
  "severity": "high",
  "category": "security",
  "file": "src/auth/session.py",
  "line": 42,
  "title": "Session token is not rotated after login",
  "explanation": "This may allow session fixation.",
  "recommendation": "Rotate the session token after successful authentication.",
  "confidence": 0.82
}
```

`confidence` alanı provider tarafından hesaplanır (prompt'ta 0-1 arası değer istenir). Ancak model confidence kalibrasyonları güvenilir değildir. Claude'a dönen raporda bu uyarı eklenir — Claude kendi değerlendirmesini yapmalıdır.

Severity değerleri:

```text
critical
high
medium
low
info
```

Category değerleri:

```text
bug
security
performance
architecture
maintainability
testing
documentation
style
```

### 13.1 JSON Parse Stratejisi

Provider'lardan strict JSON beklenir. Prompt'ta JSON schema açıkça verilir.

Parse akışı:

```text
1. Ham cevaptaki markdown code fence'leri (```json ... ```) otomatik soyulur
2. JSON parse denenir
3. Başarısızsa bir kez retry yapılır: "Your response was not valid JSON. Return only JSON."
4. İkinci deneme de başarısızsa parse_error finding'i döndürülür, cevap sessizce yutulmaz
```

Parse error finding örneği:

```json
{
  "endpoint": "ollama-local",
  "provider": "ollama",
  "model": "qwen2.5-coder",
  "severity": "info",
  "category": "system",
  "title": "Provider response could not be parsed",
  "explanation": "Response was not valid JSON after retry.",
  "confidence": 1.0
}
```

---

## 14. Context Toplama Stratejisi

MindMesh full codebase’i varsayılan olarak göndermemelidir.

### 14.0 Context Pipeline

```text
1. collector.py → scope’a göre aday dosyaları toplar
   Örnek: src/ altında 120 dosya bulundu

2. filters.py → adayları süzer
   - block_dirs kontrolü (node_modules, vendor, dist, .git)
   - block_files kontrolü (.env, *.pem, *.key)
   - binary dosya tespiti (.png, .jpg, .woff → atla)
   - generated/minified dosya tespiti → atla
   - dosya boyutu limiti (max_file_size_kb)
   - toplam context boyutu limiti (max_total_context_kb)
   - desteklenen text dosyası mı?
   - symlink güvenli mi?
   - scope dışına çıkıyor mu?
   Örnek: 120 → 34 dosya kaldı

3. redactor.py → kalan dosyalarda secret/token değerlerini maskeler
   - Redaction findings listesi oluşturulur
   - İçerik [REDACTED_SECRET] ile değiştirilir
   Örnek: 34 dosya temizlendi

4. tokenizer.py → toplam KB hesaplanır, limit kontrolü yapılır

5. Provider’a güvenli context gönderilir
```

filters.py ile file_policy.py ayrımı:

```text
file_policy.py = kurallar (hangi path/pattern yasak?)
filters.py     = kuralları uygulayan süzgeç (bu aday dosya context’e girecek mi?)
```

filters.py şunları YAPMAZ: secret değiştirme, provider API çağrısı, rapor üretme, git diff toplama.

Öncelik sırası:

```text
1. Git diff
2. Kullanıcının verdiği dosyalar
3. İlgili klasörler
4. Sınırlı dependency context
5. Full codebase sadece açık izinle
```

### 14.1 Context Boyut Limiti

Context boyutu KB bazlı ölçülür. `tokenizer.py` dosya boyutlarını toplar ve KB'a çevirir.

```text
- max_file_size_kb: Tek dosya limiti (varsayılan: 120 KB)
- max_total_context_kb: Toplam context limiti (varsayılan: 1024 KB)
- Limit aşılırsa kullanıcıdan onay istenir (require_confirmation_for_large_context: true)
```

Gerçek token sayımı (tiktoken vb.) MVP kapsamında değildir. KB bazlı limit "çok büyük context gönderme" koruması için yeterlidir. Token bazlı maliyet optimizasyonu sonraki fazda eklenebilir.

### 14.2 Git Diff Çözümleme

Varsayılan scope `git_diff` akıllı varsayılan kullanır:

```text
1. git diff HEAD çalıştır (staged + unstaged)
2. Boşsa → git diff <base_branch>...HEAD dene (branch diff)
3. O da boşsa → "Değişiklik bulunamadı" hata mesajı
```

Base branch tespit sırası:

```text
1. Config'de project.base_branch tanımlıysa onu kullan
2. git remote show origin → HEAD branch
3. Yoksa "main" dene, yoksa "master" dene
```

Kullanıcı scope parametresiyle override edebilir:

```text
--scope git_diff    → yukarıdaki akıllı varsayılan
--scope staged      → git diff --staged
--scope branch      → git diff main...HEAD
--scope <path>      → belirtilen dosya/dizinin tam içeriği (diff değil, dosya okuma)
```

Path scope'u dosyaların tam içeriğini gönderir. Kullanıcı path verdiğinde amaç "bu kodu analiz et"tir, sadece diff değil. KB limiti büyük context'e karşı koruma sağlar.

Git diff odaklı review avantajları:

```text
- Daha az token kullanır
- Daha az gizli bilgi riski taşır
- Review daha odaklı olur
- CI/CD ile daha uyumludur
```

### 14.2 İlgili Dosyaları Bulma

İleride şu kaynaklardan ilgili dosyalar bulunabilir:

```text
- import graph
- dependency graph
- grep/ripgrep
- LSP referansları
- test coverage ilişkileri
- framework route map
```

MVP’de basit yaklaşım yeterlidir:

```text
- Git diff dosyaları
- Kullanıcının verdiği path’ler
- Aynı klasördeki yakın dosyalar
```

### 14.4 Context Sunum Formatı

Provider’a gönderilen context structured metadata ile işaretlenir. Her dosya başlığı, dili ve satır aralığı belirtilir:

```text
## File: src/auth/session.py (modified)
Language: python
Lines: 42-88

def rotate_token(user):
    ...

## File: src/auth/middleware.py (modified)
Language: python
Lines: 1-35

from auth.session import rotate_token
...
```

Diff scope’unda unified diff formatı korunur, dosya sınırları aynı şekilde işaretlenir.

Bu format provider’ın doğru dosya adı ve satır numarası raporlamasını sağlar. Normalization kalitesi buna bağlıdır.

---

## 15. Güvenlik ve Gizlilik Kuralları

MindMesh’in en kritik kısmı güvenliktir.

### 15.1 Asla Gönderilmemesi Gerekenler

```text
.env
.env.local
.env.production
*.pem
*.key
id_rsa
id_ed25519
secrets/**
private_keys/**
credentials.json
service-account.json
production config dosyaları
```

### 15.2 Varsayılan Block Directory Listesi

```text
.git
node_modules
vendor
dist
build
.next
.nuxt
coverage
.cache
.idea
.vscode
```

### 15.3 Secret Redaction

MindMesh, context toplama aşamasında — dosyalar okunduktan hemen sonra — redaction uygulamalıdır. Redact edilmemiş içerik bellekte asla tutulmaz.

Redaction sırası:

```text
1. Dosya okunur
2. Secret pattern taraması yapılır
3. Bulunan secret’lar findings listesine kaydedilir (dosya, satır, pattern tipi — secret değeri değil)
4. İçerik redact edilir
5. Redact edilmiş içerik context’e eklenir
```

Örnek dönüşüm:

```text
OPENAI_API_KEY=sk-xxxxx
```

şuna çevrilir:

```text
OPENAI_API_KEY=[REDACTED_SECRET]
```

Findings kaydı örneği:

```json
{
  "file": ".env",
  "line": 3,
  "pattern": "api_key",
  "action": "redacted"
}
```

Bu findings listesi Claude’a dönen raporda "bu dosyada secret tespit edildi" bilgisi vermek için kullanılır. Secret değerinin kendisi hiçbir yerde tutulmaz.

### 15.4 Secret Detection Yöntemi

MVP’de elle yazılmış regex pattern’ler kullanılır. Temel pattern kategorileri:

```text
- API key formatları (sk-*, AKIA*, ghp_*, gho_*, glpat-* vb.)
- PEM/SSH header’ları (-----BEGIN PRIVATE KEY-----, ssh-rsa vb.)
- Password/secret assignment (password=, secret=, token= vb.)
- Connection string’ler (postgresql://, mongodb://, redis:// vb.)
- Yüksek entropi string’ler (opsiyonel, sonraki faz)
```

Pattern listesi config üzerinden genişletilebilir olmalıdır. `detect-secrets` gibi kütüphaneler güvenlik sertleştirme fazında eklenebilir.

### 15.4 Provider Policy (`provider_policy.py`)

Provider policy fail-closed çalışır. Disabled provider’a kesinlikle istek gönderilmez. Context toplanmış olsa bile dışarı çıkmaz.

`disabled` listesi `allowed` listesinden daha güçlüdür:

```yaml
providers:
  allowed:
    - openai
    - gemini
  disabled:
    - openai
```

Bu durumda bile openai kullanılamaz.

#### Provider Validation Sırası

```text
1. Provider alias resolve edilir (chatgpt → openai)
2. Provider disabled listesinde mi? → Evetse direkt block
3. Provider allowed listesinde mi? → Hayırsa block
4. Provider adapter kayıtlı mı? → Hayırsa block
5. Provider kullanılabilir kabul edilir
```

#### Policy Violation Hatası

```json
{
  "error": {
    "code": "PROVIDER_DISABLED",
    "message": "Provider ‘openai’ is disabled by project policy.",
    "provider": "openai",
    "requested_as": "chatgpt",
    "retryable": false,
    "suggested_providers": ["gemini", "zai"]
  }
}
```

Alias örneği: kullanıcı `--provider chatgpt` derse, alias `openai`’a çözülür. `openai` disabled ise:

```text
Provider ‘chatgpt’ alias olarak ‘openai’ provider’ına çözüldü,
ancak ‘openai’ disabled listesinde olduğu için istek gönderilmedi.
```

#### Fallback Kuralları

**Kullanıcı explicit provider verdiyse:**

```text
/mindmesh:review --provider openai --scope src/
→ Block. Fallback yok. Policy violation hatası döner.
```

**Kullanıcı provider vermedi, default provider disabled ise:**

```yaml
providers:
  default: openai
  disabled:
    - openai
```

```text
→ DEFAULT_PROVIDER_DISABLED hatası döner. Otomatik fallback yapılmaz.
```

Provider seçimi güvenlik/policy konusudur. Sistem kullanıcının haberi olmadan farklı provider’a yönlendirmemelidir.

#### Çoklu Endpoint Senaryosu

Birden fazla endpoint seçildiğinde her endpoint bağımsız policy kontrolünden geçer:

```text
/mindmesh:review --endpoints openai-review,gemini-default --scope src/

Config: disabled: [openai]

openai-review  → PROVIDER_DISABLED → policy violation error finding
gemini-default → policy OK → normal çalışır
```

Geçemeyen endpoint bloklanır, geçen çalışır. Raporda hem policy violation hem sonuçlar birlikte döner. Partial success yaklaşımıyla tutarlıdır.

Tüm endpoint’ler bloklanırsa raporda sadece policy violation hataları döner.

### 15.5 Permission Policy (`permission_policy.py`)

Hangi işlemin yapılabileceğini, hangisinin onay gerektirdiğini kontrol eder.

Kontrol ettiği sorular:

```text
- Dış provider’a context gönderilebilir mi?
- Full codebase gönderimi serbest mi?
- Large context için kullanıcı onayı gerekiyor mu?
- Provider patch önerebilir mi?
- Patch otomatik apply edilebilir mi?
- Delegate komutu hangi modlarda çalışabilir?
- Hassas dosya tespit edildiğinde işlem bloklanmalı mı?
- Komut sadece dry-run mı çalıştırılmalı?
```

Örnek akış:

```text
Kullanıcı: /mindmesh:delegate --provider gemini --task "tüm codebase’i özetle"

permission_policy kontrol eder:
  allow_full_codebase_context: false

Sonuç:
  İşlem bloklanır → MCP tool cevabında uyarı döner → Claude kullanıcıya bildirir
```

Permission policy config’den okunur. MCP server kullanıcıyla doğrudan iletişim kuramaz — blok veya uyarı kararını JSON cevabına ekler, Claude kullanıcıya iletir.

---

## 16. Patch ve Dosya Değiştirme Politikası

MVP’de external provider doğrudan patch uygulamamalıdır.

Doğru akış:

```text
Provider öneri üretir
  ↓
MindMesh öneriyi normalize eder
  ↓
Claude öneriyi değerlendirir
  ↓
Claude gerekirse patch yazar
  ↓
Kullanıcı onayı veya Claude Code akışıyla uygulanır
```

Provider diff üretebilir ama bu diff otomatik uygulanmaz.

Önerilen policy:

```yaml
permissions:
  allow_external_patch: false
  allow_auto_apply_patch: false
```

İleri seviye modda izole worktree/container üzerinde patch denenebilir.

---

## 17. Subagent Yaklaşımı

Subagent’lar MVP kapsamında değildir. MCP tool’ları Claude’un doğrudan çağırabileceği arayüzler sağlar, skill dosyaları (SKILL.md) kullanıcı deneyimini paketler. Subagent tanımları Faz 3 (Plugin Paketleme) kapsamında eklenecektir.

Planlanan subagent’lar (Faz 3):

```text
external-consultant  → Dış provider’dan görüş al, özetle
security-reviewer    → Auth, injection, secret leak analizi
codebase-analyst     → Codebase yapısı ve mimari özeti
bug-hunter           → Bug sebep analizi, fix planı, test önerisi
test-planner         → Test senaryoları üretimi
```

---

## 18. Hook Kullanımı

Hook’lar MVP kapsamında değildir. Güvenlik (redaction, policy) ve normalization MCP server’ın kendi iç akışında yapılır. Hook’lar Faz 3 (Plugin Paketleme) kapsamında eklenecektir.

Planlanan hook’lar (Faz 3):

```text
PreToolUse    → Provider’a gönderilecek context’i kontrol et
PostToolUse   → Provider cevabını kontrol et, riskli patch uyarısı ver
UserPromptSubmit → Review/security/bugfix isteklerinde ilgili skill’i öner
```

---

## 19. Örnek Kullanıcı Akışları

### 19.1 Multi Review

Kullanıcı:

```text
Bu diff’i Gemini ve ChatGPT’ye review ettir. Özellikle bug ve security açısından bakılsın.
```

Akış:

```text
Claude isteği anlar
MindMesh review_code tool çağrılır
Git diff toplanır
Redaction uygulanır
OpenAI ve Gemini çağrılır
Cevaplar normalize edilir
Ortak/çelişen bulgular çıkarılır
Claude kullanıcıya final rapor döner
```

### 19.2 Security Audit

Kullanıcı:

```text
src/auth klasörünü security açısından farklı modellerle kontrol et.
```

Akış:

```text
Path policy kontrol edilir
Dosyalar toplanır
Secret scan yapılır
Provider’lara security prompt gönderilir
Bulgular severity’ye göre gruplanır
Claude aksiyon planı üretir
```

### 19.3 Bug Investigation

Kullanıcı:

```text
Login bazen 500 dönüyor. Şu loglarla beraber Gemini’ye ve OpenAI’a analiz ettir.
```

Akış:

```text
Loglar alınır
İlgili dosyalar toplanır
Provider’lara bug investigation prompt’u gönderilir
Muhtemel sebepler karşılaştırılır
Fix planı çıkarılır
Test önerileri üretilir
```

---

## 20. Prompt Tasarımı

Provider’lara gönderilecek prompt’lar `src/mindmesh/prompts/` dizininde ayrı template dosyaları olarak yaşar. Template’ler Jinja2 ile render edilir. Tool katmanı template’i yükler, değişkenleri doldurur ve Message listesi oluşturur.

Template dosyaları:

```text
src/mindmesh/prompts/
├── review.md          → review_code tool’u tarafından kullanılır
├── security.md        → security_audit tool’u tarafından kullanılır
├── bug_investigate.md → bug_investigate tool’u tarafından kullanılır
└── ask.md             → ask_provider tool’u tarafından kullanılır
```

Aşağıdaki örnekler bu template dosyalarının içeriğini gösterir.

### 20.1 Code Review Prompt Şablonu

```text
You are reviewing a code change.

Focus areas:
- correctness
- bugs
- security
- performance
- maintainability
- test coverage

Rules:
- Do not invent files that are not provided.
- Do not assume hidden context.
- If evidence is weak, mark confidence as low.
- Return structured JSON only.
- Prefer actionable findings.
- Avoid style-only comments unless they hide a real problem.
```

### 20.2 Security Audit Prompt Şablonu

```text
You are performing a security audit.

Focus areas:
- authentication
- authorization
- injection
- secrets
- SSRF
- path traversal
- insecure deserialization
- unsafe file operations
- insecure defaults

Rules:
- Classify severity as critical/high/medium/low/info.
- Explain exploitability.
- Provide a concrete recommendation.
- Avoid false certainty.
- Return structured JSON only.
```

### 20.3 Bug Investigation Prompt Şablonu

```text
You are investigating a bug.

Input may include:
- bug description
- logs
- stack trace
- git diff
- relevant files

Return:
- probable causes
- evidence
- confidence
- fix plan
- test suggestions
- unknowns
```

---

## 21. Output Format

### 21.1 MCP Tool Dönüş Formatı

MCP tool’ları Claude’a structured JSON döner. Claude bu JSON’ı kullanıcıya uygun formatta sunar.

```json
{
  "summary": "2 endpoint çağrıldı, 8 finding bulundu, 1 endpoint timeout oldu.",
  "findings": [
    {
      "endpoint": "openai-review",
      "provider": "openai",
      "model": "gpt-5.1",
      "severity": "high",
      "category": "security",
      "file": "src/auth/session.py",
      "line": 42,
      "title": "Session token is not rotated after login",
      "explanation": "This may allow session fixation.",
      "recommendation": "Rotate the session token after successful authentication.",
      "confidence": 0.82
    }
  ],
  "endpoint_errors": [
    {
      "endpoint": "ollama-local",
      "error_code": "PROVIDER_TIMEOUT",
      "message": "Did not respond within 60 seconds.",
      "retryable": true
    }
  ],
  "match_hints": [
    {
      "finding_indices": [0, 3],
      "reason": "same file + line range + category"
    }
  ],
  "metadata": {
    "endpoints_called": 3,
    "endpoints_succeeded": 2,
    "total_findings": 8,
    "context_size_kb": 45,
    "redacted_secrets": 2
  }
}
```

### 21.2 Claude’un Kullanıcıya Sunumu

Claude JSON’ı alır ve kullanıcıya şu yapıda sunar:

```text
Summary
Critical findings
High findings
Medium findings
Low/info findings
Eşleşme ipuçları (hangi endpoint’ler aynı bulguyu gördü)
Endpoint hataları
Önerilen sonraki adımlar
```

Bu sunum formatı Claude’un sorumluluğundadır — MCP tool buna karışmaz.

---

## 22. Hata Yönetimi

MindMesh endpoint hatalarını düzgün yönetmelidir.

### 22.1 Partial Success Yaklaşımı

Çoklu endpoint senaryosunda bir endpoint'in hatası diğerlerini engellemez:

```text
openai-review  → başarılı → 3 finding
gemini-default → başarılı → 5 finding
ollama-local   → TIMEOUT  → 1 error finding

Toplam: 8 finding + 1 error finding → Claude'a sunulur
```

Tek endpoint seçiliyse ve hata olursa, doğrudan hata döner.

### 22.2 Olası Hatalar

```text
Provider timeout
Rate limit (max 2 retry with exponential backoff sonrası)
Invalid API key
Model unavailable
Response parse error (max 1 retry sonrası)
Context too large
Policy violation
Secret detected
Unsupported provider
```

### 22.3 Error Finding Formatı

Endpoint hataları normal Finding formatında döner:

```json
{
  "endpoint": "gemini-default",
  "provider": "gemini",
  "model": "gemini-2.5-pro",
  "severity": "info",
  "category": "system",
  "title": "Endpoint did not respond",
  "explanation": "Gemini did not respond within 30 seconds.",
  "error_code": "PROVIDER_TIMEOUT",
  "retryable": true,
  "confidence": 1.0
}
```

---

## 23. Test Stratejisi

### 23.1 Test Katmanları

```text
Unit testler       → Mock adapter ile. Provider API’sine dokunmaz. Hızlı, izole.
                     İş mantığını test eder: prompt, normalization, merge, policy, redaction.

Integration testler → Response fixture’lar ile. Gerçek API cevapları JSON dosyası olarak
                     kaydedilir, httpx mock ile HTTP katmanında yakalanır.
                     Gerçek API formatının doğru parse edildiğini doğrular. (Faz 2)

E2E testler        → Gerçek API çağrısı. CI dışı, opsiyonel. (Faz 3+)
```

MVP’de (Faz 1a/1b) sadece unit testler + mock adapter yeterlidir.

### 23.2 Mock Adapter

Test altyapısında `FakeProviderAdapter` kullanılır. Sabit JSON döner, provider API’sine istek atmaz:

```python
class FakeProviderAdapter(ProviderAdapter):
    name = "fake"

    async def send(self, messages, model, config):
        return self._fixture_response
```

### 23.3 Test Edilecek Alanlar

```text
1. Secret redaction (pattern eşleşme, redact edilmiş çıktı)
2. Block file policy (izin verilen/engellenen dosyalar)
3. Block dir policy (izin verilen/engellenen dizinler)
4. Endpoint resolver (config → adapter + model çözümleme)
5. Response normalization (JSON parse, code fence soyma, retry)
6. Merger (gruplama, eşleşme ipuçları)
7. Error handling (timeout, rate limit → error finding dönüşümü)
8. Git diff collection (subprocess çıktı parse)
9. MCP tool input validation
10. Prompt template rendering (değişken doldurma)
11. Config yükleme (varsayılanlar, .mindmesh.yml override, env var)
12. KB bazlı context boyut limiti
```

Örnek test dosyaları:

```text
test_redactor.py
test_file_policy.py
test_endpoint_resolver.py
test_context_collector.py
test_normalizer.py
test_merger.py
test_review_tool.py
test_security_tool.py
test_config.py
test_errors.py
```

---

## 24. Geliştirme Fazları

### Faz 1a: Walking Skeleton (tek endpoint, tek tool)

```text
- MCP server kurulumu (FastMCP + stdio)
- Config sistemi (Pydantic, .mindmesh.yml opsiyonel, sensible defaults)
- API key çözümleme (env var + .env)
- Provider adapter base interface (send with messages)
- OpenAI adapter
- Endpoint resolver
- Git diff context collector (subprocess git)
- Secret redactor (regex pattern'ler)
- File policy (pathspec)
- KB bazlı context boyut limiti
- review_code tool + prompt template
- Normalizer (JSON parse + code fence soyma + 1 retry)
- Basit hata yönetimi (error finding formatı)
```

Faz 1a sonunda: Claude Code → MindMesh → tek OpenAI endpoint → code review çalışır.

### Faz 1b: Multi-endpoint, ikinci tool

```text
- Gemini adapter
- Paralel endpoint çağrıları (asyncio.gather + bağımsız timeout)
- Rate limit yönetimi (exponential backoff, max 2 retry)
- Partial success (hatalı endpoint diğerlerini engellemez)
- Merger (basit gruplama + eşleşme ipuçları, karar Claude'da)
- security_audit tool + prompt template
- list_endpoints tool
```

Faz 1b sonunda: çoklu endpoint'e paralel review/security, partial success çalışır.

### Faz 2: Ek Tool'lar ve Orchestration

```text
- bug_investigate tool + prompt template
- compare_providers tool
- ask_provider tool
- Endpoint bazlı config override (temperature, max_tokens)
- Daha fazla secret detection pattern'i
```

### Faz 3: Claude Plugin Paketleme

```text
- Plugin manifest
- Skill dokümanları
- Subagent tanımları
- Hook config
- README ve kurulum akışı
```

### Faz 4: Güvenlik Sertleştirme

```text
- Daha gelişmiş secret detection
- Policy violation raporları
- Provider allow/deny enforcement
- Context preview
- Large context confirmation
- Audit log
```

### Faz 5: Opsiyonel CLI ve CI/CD

```text
- Typer CLI
- GitHub Actions entegrasyonu
- Pull request review mode
- JSON/SARIF output
- Lokal cache
```

### Faz 6: Gelişmiş Agent/Worktree Modu

```text
- İzole git worktree
- Provider patch suggestion
- Test run integration
- Claude review sonrası patch apply
- Rollback desteği
```

---

## 25. Riskler

### 25.1 Gizli Bilgi Sızıntısı

En büyük risk codebase içindeki gizli bilgilerin dış provider’lara gönderilmesidir.

Önlem:

```text
- Redaction zorunlu
- Block file list
- Block dir list
- Context preview
- Full codebase gönderimini default kapalı tutma
```

### 25.2 Yanlış Provider Cevapları

Provider’lar hallucination yapabilir.

Önlem:

```text
- Evidence zorunlu
- Confidence alanı
- Dosya/satır referansı isteme
- Claude’un final karar verici olması
```

### 25.3 Gereksiz Gürültü

Farklı modeller çok fazla öneri döndürebilir.

Önlem:

```text
- Severity filtreleme
- Ortak bulguları öne çıkarma
- Style-only yorumları azaltma
- Actionable finding şartı
```

### 25.4 Maliyet

Çok provider çağrısı maliyet oluşturabilir.

Önlem:

```text
- Git diff önceliği
- Context limiti
- Provider sayısı limiti
- Lokal model desteği
- Cache
```

---

## 26. İlk MVP İçin Net Teknik Karar

MindMesh ilk MVP şöyle olmalıdır:

```text
Dil: Python
Ana entegrasyon: MCP Server
Claude entegrasyonu: Plugin
CLI: Yok, opsiyonel gelecek faz
Provider’lar: OpenAI + Gemini ile başla
Context: Git diff öncelikli
Security: Redaction + block policy zorunlu
Patch apply: Yok
Output: Structured JSON + Claude-readable summary
```

---

## 27. Başlangıç Komutları / Kullanım Fikri

Kullanıcı Claude Code içinde şunları kullanabilmelidir:

```text
MindMesh ile bu diff’i review ettir.
```

```text
Bu modülü security açısından OpenAI ve Gemini’ye kontrol ettir.
```

```text
Bu bug için farklı provider’lardan olası sebep ve fix planı al.
```

```text
Gemini ve ChatGPT’nin önerilerini karşılaştır, hangisi daha mantıklı söyle.
```

---

## 28. Nihai Ürün Tanımı

**MindMesh**, Claude Code için geliştirilen, farklı AI provider’ları güvenli ve kontrollü şekilde danışman/reviewer/subagent gibi kullanmayı sağlayan bir MCP tabanlı orkestrasyon sistemidir.

Claude ana karar verici olarak kalır. MindMesh, diğer modellerden yapılandırılmış görüş alır, bunları normalize eder, karşılaştırır ve Claude’un daha güvenilir karar vermesine yardımcı olur.

---

## 29. Kısa Özet

MindMesh’in özü:

```text
Claude karar verir.
MindMesh danışır.
Provider’lar görüş üretir.
Policy güvenliği sağlar.
MCP bağlantıyı sağlar.
Plugin Claude Code deneyimini paketler.
```

İlk hedef, küçük ama sağlam bir MVP çıkarmaktır:

```text
Claude Code Plugin + Python MCP Server + Provider Router + Safe Code Review
```

Bu temel oturduktan sonra CLI, CI/CD, dashboard, worktree isolation ve otomatik patch workflow’ları eklenebilir.

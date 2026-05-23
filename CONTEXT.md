# MindMesh Domain Glossary

## Provider

Bir dış AI servisini temsil eder. API kimlik dogrulama, istek formati, rate limit ve baglanti yonetiminden sorumludur. Ornek: OpenAI, Gemini, Ollama, Z.ai.

Provider tek basina hangi modelin kullanilacagini belirlemez.

## Model

Bir Provider icerisindeki spesifik AI modeli. Ornek: OpenAI icerisinde gpt-5.1 ve o3 farkli Model'lerdir.

## Endpoint

Provider + Model + opsiyonel konfigurasyondan (temperature, timeout vb.) olusan, cagrilabilir birim. Tool'lar ve komutlar dogrudan Endpoint'leri hedefler, Provider veya Model'i degil.

Bir Provider birden fazla Endpoint'e sahip olabilir (farkli modeller veya farkli ayarlar icin).

## Finding

Bir Endpoint'in urettigi tek bir bulgu. Dosya, satir, severity, category ve oneri icerir. Normalizer tarafindan ham provider cevabindan parse edilir.

## Merger

Birden fazla Endpoint'ten gelen Finding'leri gruplayan ve Claude'a sunum icin organize eden katman. Merger kesin eslesme karari vermez — basit ipuclari (dosya + satir araligi + category) uretir ve nihai karari Claude'a birakir.

## Policy

Uc bagimsiz policy katmani vardir:

- **File Policy**: Hangi dosya/dizin context'e dahil edilebilir? Block list bazli.
- **Provider Policy**: Hangi provider kullanilabilir? Fail-closed calisir. disabled > allowed onceligi vardir. Disabled provider'a kesinlikle istek gonderilmez.
- **Permission Policy**: Hangi islem yapilabilir, hangisi onay ister? Full codebase gonderimi, patch onerisi, auto-apply gibi aksiyonlari kontrol eder.

## Cache

SQLite tabanli response cache. Ayni endpoint, template ve context kombinasyonu icin tekrar provider'a istek gondermez. Key = hash(endpoint + template + context), TTL bazli gecerlilik suresi. Cache hit durumunda provider cagrisi atlanir, maliyet ve latency duser. Config ile disable edilebilir.

## History

SQLite tabanli run history. Her MCP tool calistirmasi kaydedilir: zaman damgasi, kullanilan endpoint'ler, context boyutu, finding sayisi, sure, cache hit/miss durumu. Debugging, maliyet takibi ve performans analizi icin kullanilir.

## Worktree

Git worktree isolation mekanizmasi. test_patch tool'u tarafindan kullanilir. Patch test edilirken ana calisma dizini etkilenmez — gecici bir worktree olusturulur, patch uygulanir, testler calistirilir, sonuc raporlanir ve worktree temizlenir.

## SARIF

Static Analysis Results Interchange Format (v2.1.0). Finding'lerin GitHub Code Scanning ile uyumlu formatta export edilmesini saglar. CI/CD pipeline'inda `.github/workflows/mindmesh-review.yml` uzerinden otomatik olarak GitHub'a yuklenir. SARIF dosyasi Finding'leri standart severity, location ve rule tanimlariyla icerir.

## Registry

Merkezi provider kayit sistemi (`registry.py`). Adapter class mapping, alias cozumleme, env auto-discovery ve known providers bilgisini tek yerde tutar. Onceki dagitik yapilar (`_PROVIDER_ADAPTER_MAP`, `_KNOWN_PROVIDERS`, `PROVIDER_ALIASES`) kaldirildi, hepsi Registry'ye tasindi. Yeni provider eklemek tek satir: `get_registry().register(ProviderInfo(...))`.

## Sandbox

Docker container izolasyonu. Worktree'de test komutu calistirilirken host OS korunur. Container: read-only mount, no-network, memory/cpu limiti, non-root user. Docker yoksa veya sandbox kapaliysa local execution'a fallback yapar. Config: `sandbox.enabled`, `sandbox.image`, `sandbox.network`, `sandbox.memory_limit`, `sandbox.cpu_limit`.

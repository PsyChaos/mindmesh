# List Endpoints

Mevcut MindMesh konfigürasyonunuzda tüm etkin endpoint'leri listeleyin. Her endpoint'in sağlayıcısı, modelini, durumunu, ve yapılandırmasını görün.

## MCP Tool

`mindmesh.list_endpoints`

## Parametreler

Bu tool parametresiz çalışır.

## Kullanım Örnekleri

```
Kullanıcı şunu söyleyebilir:
- "Hangi endpoint'ler mevcut?"
- "MindMesh'te kurulu provider'ları listele"
- "Aktif modellerim neler?"
- "Endpoint konfigürasyonum nedir?"
```

## Çıktı

Claude, MindMesh'ten dönen yapılandırılmış JSON'ı kullanıcıya şu formatta sunar:

- **Endpoint Listesi**: 
  - Endpoint adı
  - Sağlayıcı (OpenAI, Gemini, Z.ai, Ollama)
  - Model adı
  - Durum (etkin/devre dışı)
  - Konfigürasyon özeti
- **API Key Durumu**: Hangi sağlayıcılar için credentials mevcut
- **Varsayılan Endpoint**: Belirtilmemişse hangi endpoint kullanılır

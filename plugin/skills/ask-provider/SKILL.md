# Ask Provider

Send a custom question to a specific AI provider endpoint and get insights or analysis with optional code context.

## MCP Tool

`mindmesh.ask_provider`

## Parametreler

| Parametre | Tip | Varsayılan | Açıklama |
|-----------|-----|------------|----------|
| `question` | `string` | *(gerekli)* | Sormak istediğiniz soru veya talep |
| `endpoint` | `string` | `None` | Hedef endpoint adı (ör. "openai-gpt4", "gemini-pro"). Belirtilmezse konfigüre edilmiş varsayılan endpoint kullanılır |
| `context_mode` | `string` | `"none"` | Bağlam şekli: `"none"` (hiç bağlam), `"git_diff"` (git diff), `"staged"` (sahnelenmiş), `"branch"` (branch farkları), veya dosya yolu |

## Kullanım Örnekleri

```
Kullanıcı şunu söyleyebilir:
- "OpenAI'ya git diff'ten bahsederek bu kod hakkında soru sor"
- "Gemini'ye bunu sor: Bu fonksiyonu nasıl optimize edebilirim?"
- "Gemini modelini kullanarak bağlam olmadan şu soruyu sor"
- "Bu dosya hakkında Z.ai'ya soru sor"
```

## Çıktı

Claude, MindMesh'ten dönen yapılandırılmış JSON'ı kullanıcıya şu formatta sunar:

- **Özet**: Provider'ın yanıtının kısa özeti
- **Bulgular**: Kategorize edilmiş sorunlar/öneriler (varsa)
- **Endpoint Hataları**: Timeout, rate limit, ya da politika ihlalleri
- **Meta bilgi**: Çağrı edilen endpoint sayısı, bağlam boyutu, maskelenen gizli dizeler

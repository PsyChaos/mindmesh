# Multi-Review (Kod İncelemesi)

Kod değişikliklerinizi birden fazla AI provider'a gönderin ve paralel gözlemler alın. Kod kalitesi, best practices, ve olası sorunları tespit eder.

## MCP Tool

`mindmesh.review_code`

## Parametreler

| Parametre | Tip | Varsayılan | Açıklama |
|-----------|-----|------------|----------|
| `scope` | `string` | `"git_diff"` | Hangi kodu inceleyeceğiniz: `"git_diff"` (staged + unstaged), `"staged"` (sahnelenmiş), `"branch"` (base branch'ten fark), veya `"<path>"` (belirli dosya) |
| `endpoints` | `list[string]` | `None` | Kullanılacak endpoint'lerin listesi (ör. `["openai-gpt4", "gemini-pro"]`). Belirtilmezse tüm etkin endpoint'ler |
| `focus` | `list[string]` | `None` | İnceleme alanları (ör. `["performance", "security", "maintainability"]`). Belirtilmezse genel inceleme |

## Kullanım Örnekleri

```
Kullanıcı şunu söyleyebilir:
- "Staging alanımı OpenAI ve Gemini ile gözden geçir"
- "Main'e kıyasla bu branch'i performans odağında incele"
- "Bu dosyayı tüm sağlayıcılara gönder"
- "Git diff'imi güvenlik ve bakım kolaylığı için incetle"
```

## Çıktı

Claude, MindMesh'ten dönen yapılandırılmış JSON'ı kullanıcıya şu formatta sunar:

- **Bulgular**: İnceleme sonuçları (kategori, dosya, satır, önem düzeyi, öneri)
- **Provider Eşleşme İpuçları**: Aynı sorunu birden fazla provider tespit ettiyse gruplandırma
- **Özet**: Kritik bulguların kısa özeti
- **Meta bilgi**: Çağrı edilen endpoint sayısı, başarılı yanıtlar, toplam bulgular, bağlam boyutu

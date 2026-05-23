# Compare Providers

Aynı kod tarama görevini birden fazla sağlayıcıya gönderin ve yanıtları karşılaştırın. Provider performansını, doğruluğunu, ve özgünlüğünü değerlendirin.

## MCP Tool

`mindmesh.compare_providers`

## Parametreler

| Parametre | Tip | Varsayılan | Açıklama |
|-----------|-----|------------|----------|
| `task` | `string` | *(gerekli)* | Tarama görevi açıklaması (ör. "Performans sorunlarını bul", "Güvenlik açıklarını tespit et") |
| `scope` | `string` | `"git_diff"` | Hangi kodu tarayacağınız: `"git_diff"`, `"staged"`, `"branch"`, veya `"<path>"` |
| `endpoints` | `list[string]` | `None` | Karşılaştırılacak endpoint'ler. Belirtilmezse tüm etkin endpoint'ler |

## Kullanım Örnekleri

```
Kullanıcı şunu söyleyebilir:
- "OpenAI ve Gemini'yi performans taraması için karşılaştır"
- "Tüm provider'larıma bu git diff'i 'kimlik doğrulama açıkları' için gönder ve sonuçları karşılaştır"
- "GPT-4 vs Gemini — hangisi daha iyi hata bulur?"
- "Security audit görevini paralel çalıştır ve sonuçları kıyasla"
```

## Çıktı

Claude, MindMesh'ten dönen yapılandırılmış JSON'ı kullanıcıya şu formatta sunar:

- **Provider Sonuçları**: Her endpoint'ten alınan bulgular ve önemli noktalar
- **Karşılaştırma**: Tespit edilen benzersiz/ortak bulgular
- **Güven Puanları**: Her provider'ın yanıtında güven düzeyi
- **Eşleşme Oranı**: Sağlayıcılar arasında ortak bulgular yüzdesi
- **Performans Metrikleri**: Yanıt süresi, bağlam kullanımı, endpoint hataları

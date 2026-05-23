# Bug Investigate

Bilinen bir hatayı tanımlayın ve MindMesh'e kodu ile hata günlüğünü gönderin. Paralel provider'lar nedeni tahlil eder ve düzeltme öneriler sunar.

## MCP Tool

`mindmesh.bug_investigate`

## Parametreler

| Parametre | Tip | Varsayılan | Açıklama |
|-----------|-----|------------|----------|
| `issue` | `string` | *(gerekli)* | Hata açıklaması (ör. "Kullanıcı kaydı başarısız oluyor", "Görüntü yükleme zaman aşımına uğruyor") |
| `scope` | `string` | `"git_diff"` | Hangi kodu inceleyeceğiniz: `"git_diff"`, `"staged"`, `"branch"`, veya `"<path>"` |
| `endpoints` | `list[string]` | `None` | Kullanılacak endpoint'lerin listesi. Belirtilmezse tüm etkin endpoint'ler |
| `logs` | `string` | `None` | Hata günlüğü metin bloğu veya yığın izlemesi |

## Kullanım Örnekleri

```
Kullanıcı şunu söyleyebilir:
- "Bu hata günlüğüyle birlikte: 'TypeError: Cannot read property of undefined' — nedenini araştır"
- "Kullanıcı kaydı POST isteği 500 döndürüyor. Git diff'imle bakar mısın?"
- "Bu stack trace'i çözümlemeye yardım et" ve günlüğü yapıştır
- "Veritabanı bağlantısı timeout oluyor — kodda ne yapıştığını bulunuz"
```

## Çıktı

Claude, MindMesh'ten dönen yapılandırılmış JSON'ı kullanıcıya şu formatta sunar:

- **Tanı**: Hataların muhtemel kökü
- **Bulgular**: Kodda bulunan ilgili sorunlar ve eşleşme derecesi
- **Adım Adım Çözüm**: Düzeltme adımları ve test planı
- **Günlük Analizi**: Error trace'inde tespit edilen kalıplar
- **Meta bilgi**: Çağrı edilen provider'lar, bağlam boyutu, başarılı yanıtlar

# Security Audit

Kod tabanınızı OWASP Top 10 tehditlerine karşı otomatik olarak tarayın. Güvenlik açıkları, gizli sızıntıları, ve yanlış yapılandırmaları tespit eder.

## MCP Tool

`mindmesh.security_audit`

## Parametreler

| Parametre | Tip | Varsayılan | Açıklama |
|-----------|-----|------------|----------|
| `scope` | `string` | `"git_diff"` | Hangi kodu tarayacağınız: `"git_diff"` (staged + unstaged), `"staged"` (sahnelenmiş), `"branch"` (base branch'ten fark), veya `"<path>"` (belirli dosya) |
| `endpoints` | `list[string]` | `None` | Kullanılacak endpoint'lerin listesi. Belirtilmezse tüm etkin endpoint'ler |
| `focus` | `list[string]` | Otomatik | Güvenlik alanları. Varsayılan: authentication, authorization, injection, secrets, SSRF, path traversal |

## Kullanım Örnekleri

```
Kullanıcı şunu söyleyebilir:
- "Bu branch'i güvenlik açıkları için tara"
- "Staging alanımdaki gizli dizeler ve kimlik doğrulama sorunlarını kontrol et"
- "Bu dosyada SQL injection ve XSS açıklarını ara"
- "Yeni commit'leri tüm sağlayıcılarla güvenlik taraması yap"
```

## Çıktı

Claude, MindMesh'ten dönen yapılandırılmış JSON'ı kullanıcıya şu formatta sunar:

- **Kritik Bulgular**: CVSS puanı yüksek güvenlik açıkları (hemen düzeltme gerekir)
- **Uyarılar**: Orta dereceli sorunlar (birleştirmeden önce düzeltmeyi düşün)
- **Kategori**: Kimlik doğrulama, SQL injection, XSS, path traversal, vb.
- **Öneriler**: Düzeltme adımları ve best practices
- **Meta bilgi**: Tespit edilen gizli dizi sayısı, tarama kapsamı, bağlam boyutu

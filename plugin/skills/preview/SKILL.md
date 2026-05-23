# Preview Context

Provider cagrisi yapmadan context pipeline'inin tam onizlemesini alin. Hangi dosyalarin dahil edilecegini, hangilerinin filtrelenecegini, ne kadar secret maskelenecegini ve baglam boyutunu goruntuleyin.

## MCP Tool

`mindmesh.preview_context`

## Parametreler

| Parametre | Tip | Varsayilan | Aciklama |
|-----------|-----|------------|----------|
| `scope` | `string` | `"git_diff"` | Baglam kapsamı: `"git_diff"` (staged + unstaged), `"staged"` (sahnelenmiş), `"branch"` (base branch fark), veya dosya yolu |
| `endpoints` | `list[string]` | `None` | Kontrol edilecek endpoint listesi. Belirtilmezse tum varsayilan endpoint'ler |

## Kullanim Ornekleri

```
Kullanici sunu soyleyebilir:
- "Review gondermeden once context'e ne dahil edilecek goster"
- "Git diff icin context onizlemesi yap"
- "Branch farklari icin hangi dosyalar toplanacak?"
- "Bu scope'ta kac KB context olusacak, limitler asiyor mu?"
- "Hangi dosyalar filtrelendi, neden?"
```

## Cikti

Claude, MindMesh'ten donen yapilandirilmis JSON'i kullaniciya su formatta sunar:

- **Kapsam**: Kullanilan scope bilgisi
- **Gecerli Endpoint'ler**: Basariyla dogrulanan endpoint listesi
- **Engellenen Endpoint'ler**: Politika veya yapilandirma sebebiyle engellenen endpoint'ler ve nedenleri
- **Context Dosyalari**: Dahil edilen dosyalarin yolu, boyutu (KB) ve dili
- **Filtrelenen Dosyalar**: Politika, binary tespit, boyut limiti, generated/minified veya toplam limit sebebiyle elenen dosya sayilari
- **Maskelenen Secret'lar**: Tespit edilen ve maskelenen gizli dizi sayisi
- **Toplam Baglam Boyutu**: KB cinsinden toplam context boyutu
- **Limit Uyarilari**: Asilmak uzere olan veya asilan limitler
- **Izin Uyarilari**: Buyuk baglam veya dis provider icin onay gerekliligi

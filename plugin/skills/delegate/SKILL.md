# Delegate Task

Belirli bir gorevi bir veya birden fazla endpoint'e devret. Mod secenekleri ile gorev turunu belirle: danisma, analiz, inceleme, planlama veya yama onerisi.

## MCP Tool

`mindmesh.delegate_task`

## Parametreler

| Parametre | Tip | Varsayilan | Aciklama |
|-----------|-----|------------|----------|
| `task` | `string` | *(gerekli)* | Devredilecek gorev aciklamasi |
| `endpoint` | `string` | `None` | Tek hedef endpoint adi (or. "openai-gpt4"). Belirtilmezse varsayilan endpoint kullanilir |
| `endpoints` | `list[string]` | `None` | Birden fazla endpoint'e paralel gonderim. `endpoint` parametresi yerine kullanilir |
| `scope` | `string` | `"git_diff"` | Baglam kapsamı: `"git_diff"`, `"staged"`, `"branch"`, veya dosya yolu |
| `mode` | `string` | `"advisory"` | Gorev modu: `"advisory"` (danisma), `"analysis"` (analiz), `"review"` (inceleme), `"planning"` (planlama), `"patch_suggestion"` (yama onerisi) |
| `allow_patch` | `bool` | `false` | Endpoint'in yama onerisi dondurmesine izin ver. Policy'de `allow_external_patch=true` olmasi gerekir |
| `min_severity` | `string` | `None` | Minimum bulgu siddeti filtresi (or. "medium", "high", "critical") |
| `dry_run` | `bool` | `false` | Provider'a cagri yapmadan pipeline onizlemesi yap |
| `no_cache` | `bool` | `false` | Onbellegi devre disi birak, taze yanit al |

## Kullanim Ornekleri

```
Kullanici sunu soyleyebilir:
- "Bu refactoring gorevini OpenAI'ya devret, analiz modunda calistir"
- "Gemini ve OpenAI'ya paralel olarak su planlama gorevini gonder"
- "Bu degisiklik icin yama onerisi iste, patch_suggestion modunda"
- "Su gorevi danisma modunda varsayilan endpoint'e gonder"
- "Bu kodu inceleme modunda uc farkli modelle degerlendir"
```

## Cikti

Claude, MindMesh'ten donen yapilandirilmis JSON'i kullaniciya su formatta sunar:

- **Ozet**: Gorev sonucunun kisa ozeti
- **Bulgular**: Mod'a gore kategorize edilmis sorunlar, oneriler veya planlama adimlari
- **Yama Onerisi**: `allow_patch=true` ise endpoint'in sundugu kod degisiklikleri
- **Endpoint Hatalari**: Timeout, rate limit veya politika ihlalleri
- **Meta bilgi**: Cagrilan endpoint sayisi, baglam boyutu, maskelenen gizli dizeler

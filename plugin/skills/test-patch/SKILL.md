# Test Patch

Bir yamayi izole bir git worktree icinde uygulayip testleri calistirin. Ana calisma dizininiz etkilenmez — yama guvenli bir sandbox ortaminda degerlendirilir.

## MCP Tool

`mindmesh.test_patch`

## Parametreler

| Parametre | Tip | Varsayilan | Aciklama |
|-----------|-----|------------|----------|
| `patch` | `string` | *(gerekli)* | Unified diff formatinda yama icerigi |
| `test_command` | `string` | `None` | Calistirilacak test komutu (or. "pytest tests/"). Belirtilmezse sadece yama uygulanir, test calistirilmaz |
| `timeout` | `float` | `120.0` | Test komutunun maksimum calisma suresi (saniye) |

## On Kosul

Policy yapilandirmasinda `allow_external_patch=true` olmalidir. Aksi halde tool politika ihlali hatasi dondurur.

## Kullanim Ornekleri

```
Kullanici sunu soyleyebilir:
- "Bu yamayi izole ortamda uygula ve testleri calistir"
- "Provider'in onerdigi patch'i guvenli ortamda dene"
- "Su diff'i worktree'de test et, pytest ile dogrula"
- "Yamayi uygula ama test calistirma, sadece uygulanabilir mi bak"
- "Bu degisikligi 60 saniye timeout ile test et"
```

## Cikti

Claude, MindMesh'ten donen yapilandirilmis JSON'i kullaniciya su formatta sunar:

- **Worktree Yolu**: Izole calisma dizininin yolu
- **Branch Adi**: Worktree icin olusturulan gecici branch
- **Yama Durumu**: Yamanin basariyla uygulanip uygulanmadigi
- **Test Cikis Kodu**: Test komutunun donus kodu (0 = basarili)
- **Test Ciktisi**: Test komutunun standart ciktisi
- **Hata**: Varsa hata mesaji (yama uygulanamadi, timeout, vb.)

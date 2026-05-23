# Validate Policy

Endpoint, dosya yolu ve izin yapilandirmasini provider cagrisi yapmadan dogrulayin. Konfigurasyonun dogru oldugunu, endpoint'lerin erisilebildigini ve dosya politikalarinin beklendigi gibi calistigini onaylayin.

## MCP Tool

`mindmesh.validate_policy`

## Parametreler

| Parametre | Tip | Varsayilan | Aciklama |
|-----------|-----|------------|----------|
| `endpoints` | `list[string]` | `None` | Dogrulanacak endpoint adlari listesi. Belirtilmezse tum yapilandirilmis endpoint'ler kontrol edilir |
| `paths` | `list[string]` | `None` | Dosya politikasina karsi kontrol edilecek dosya yollari listesi |

## Kullanim Ornekleri

```
Kullanici sunu soyleyebilir:
- "Endpoint yapilandirmami kontrol et, her sey dogru mu?"
- "openai-gpt4 ve gemini-pro endpoint'lerini dogrula"
- "src/auth/login.py ve .env dosyalari context'e dahil edilebilir mi?"
- "Hangi izinler aktif, ozetini goster"
- "Devre disi birakilmis provider'lar hangileri?"
```

## Cikti

Claude, MindMesh'ten donen yapilandirilmis JSON'i kullaniciya su formatta sunar:

- **Endpoint Durumu**: Her endpoint icin `valid`, `blocked` veya `error` durumu ve sorunlar
- **Dosya Politikasi**: Kontrol edilen dosya yollarinin engellenip engellenmedigini gosterir
- **Izin Ozeti**: Tam kod tabani erisimi, dis yama izni, otomatik yama, buyuk baglam onayi, dis provider onayi
- **Devre Disi Provider'lar**: Yapilandirmada devre disi birakilmis provider listesi
- **Gizlilik Ayarlari**: Secret maskeleme durumu, engellenen dosya/dizin sayisi
- **Limitler**: Maksimum dosya sayisi, dosya boyutu ve toplam baglam boyutu limitleri

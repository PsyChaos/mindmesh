# Plan (Implementation Planlama)

Bir task veya feature icin bir ya da birden fazla AI provider'dan implementation plan alin. Her provider bagimsiz plan uretir, MindMesh bulgulari gruplar, Claude karsilastirir ve nihai karari verir.

## MCP Tool

`mindmesh.delegate_task` (mode="planning")

## Parametreler

| Parametre | Tip | Varsayilan | Aciklama |
|-----------|-----|------------|----------|
| `task` | `string` | **zorunlu** | Planlanacak task veya feature aciklamasi |
| `endpoints` | `list[string]` | `None` | Kullanilacak endpoint'ler. Belirtilmezse tum etkin endpoint'ler |
| `endpoint` | `string` | `None` | Tek endpoint secimi (endpoints ile birlikte kullanilmaz) |
| `scope` | `string` | `"git_diff"` | Context kapsamı. Planlama icin genellikle belirli bir dizin veya `"git_diff"` |
| `mode` | `string` | `"planning"` | Sabit. Bu skill her zaman `"planning"` modunda calisir |

## Kullanim Ornekleri

```
Kullanici sunu soyleyebilir:
- "Authentication modulu icin bir plan olustur"
- "Bu feature'i Gemini ve OpenAI'a planlatir"
- "src/auth uzerinden bir refactoring plani cikar"
- "Ollama ile lokal olarak su task icin plan uret"
- "Bu PR icin implementation adimlarini tum provider'lardan al"
```

## Cikti

Plan Finding formatinda doner. Her adim bir Finding'dir:

- **severity**: Oncelik (critical=blocker, high=erken, medium=standart, low=opsiyonel, info=not)
- **category**: `architecture`
- **title**: Faz ve adim basligi
- **explanation**: Adimin detayi, bagimliliklar, riskler
- **recommendation**: Nasil implement edilecegi
- **confidence**: Provider'in adim hakkindaki guveni

Birden fazla endpoint kullanildiginda merger eslestirme ipuclari uretir. Claude karsilastirir ve nihai plani sunar.

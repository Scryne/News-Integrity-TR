# DURUM — News Integrity TR — X kanıt yakalama araç seti

> **Ne bu dosya:** sertifika değil **envanter**. 2026-08-27 denetiminde ölçülen gerçek durum.
> "Çalışmıyor" yazan satır kusur değil, kayıt. Kapanış standardı:
> `ScryneOS/🎯 100-Command-Center/Kapanis-Standardi.md`

**Ölçüm tarihi:** 2026-08-27
**Tek cümle:** **En erken aşamadaki proje.** Phase 0 spike'ları bitmemiş, sıfır test. Kod private `Scryne/News-Integrity-TR`'de (2026-08-29'dan beri).

## Ne çalışıyor

- Backend iskeleti duruyor: FastAPI · SQLAlchemy 2.0 · Alembic · SQLite.
  18 Python dosyası (`app/models`, `app/routers`, `app/schemas`, `app/services`).
- **Spike S1 tamamlandı, verdict GO** (ADR-026): X DOM'undan yazarın `rest_id`'si
  follow butonunun `data-testid` önekinden, zorunlu `@handle` çapraz kontrolüyle çıkarılıyor.
  Timeline/permalink/alıntı/yanıt/repost üzerinde denendi, 0 yanlış atıf.
- Doküman seti sağlam: `PLAN.md` · `ARCHITECTURE.md` · `DECISIONS.md` · `DESIGN.md`.

## Ne çalışmıyor / doğrulanmadı

- **Sıfır test dosyası** ve `.venv` içinde **pytest kurulu değil** — test altyapısı hiç yok.
- ~~GitHub reposu yok~~ → 2026-08-29'da private `Scryne/News-Integrity-TR` açıldı, `main` push'lu (2026-10-26 denetimi).
- Spike **S2** (archive.today gönderim davranışı) ve **S3** (captureVisibleTab kırpma
  geometrisi) açık. Kendi kuralı: "üç spike'ın da go/no-go kararı verilmeden üretim kodu yazılmaz."
- Chrome MV3 eklentisi tarafı başlamamış.

## Ne yarım

Phase 0'ın 1/3'ü bitmiş. Üretim kodu kendi kuralına göre henüz başlayamaz.

## Sonraki adım

Proje bırakıldı (Proje Envanteri). Dönülürse: S2 ve S3 spike'larının go/no-go kararı, sonra test altyapısı.

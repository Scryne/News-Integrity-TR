# DURUM — News Integrity TR — X kanıt yakalama araç seti

> **Ne bu dosya:** sertifika değil **envanter**. 2026-08-27 denetiminde ölçülen gerçek durum.
> "Çalışmıyor" yazan satır kusur değil, kayıt. Kapanış standardı:
> `ScryneOS/🎯 100-Command-Center/Kapanis-Standardi.md`

**Ölçüm tarihi:** 2026-08-27
**Tek cümle:** **En erken aşamadaki proje.** Phase 0 spike'ları bitmemiş, sıfır test, GitHub reposu yok.

## Ne çalışıyor

- Backend iskeleti duruyor: FastAPI · SQLAlchemy 2.0 · Alembic · SQLite.
  18 Python dosyası (`app/models`, `app/routers`, `app/schemas`, `app/services`).
- **Spike S1 tamamlandı, verdict GO** (ADR-026): X DOM'undan yazarın `rest_id`'si
  follow butonunun `data-testid` önekinden, zorunlu `@handle` çapraz kontrolüyle çıkarılıyor.
  Timeline/permalink/alıntı/yanıt/repost üzerinde denendi, 0 yanlış atıf.
- Doküman seti sağlam: `PLAN.md` · `ARCHITECTURE.md` · `DECISIONS.md` · `DESIGN.md`.

## Ne çalışmıyor / doğrulanmadı

- **Sıfır test dosyası** ve `.venv` içinde **pytest kurulu değil** — test altyapısı hiç yok.
- **GitHub reposu YOK.** `git remote` boş; kod yalnız bu makinede.
- Spike **S2** (archive.today gönderim davranışı) ve **S3** (captureVisibleTab kırpma
  geometrisi) açık. Kendi kuralı: "üç spike'ın da go/no-go kararı verilmeden üretim kodu yazılmaz."
- Chrome MV3 eklentisi tarafı başlamamış.

## Ne yarım

Phase 0'ın 1/3'ü bitmiş. Üretim kodu kendi kuralına göre henüz başlayamaz.

## Sonraki adım

**Önce GitHub reposu aç ve push et** — bu proje şu an tek kopyada duruyor.

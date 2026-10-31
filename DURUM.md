# DURUM — News Integrity TR — X kanıt yakalama araç seti

> **Ne bu dosya:** sertifika değil **envanter**. Ölçülen gerçek durum; "doğrulanmadı" yazan satır kusur değil, kayıt.
> Kapanış standardı: `ScryneOS/🎯 100-Command-Center/Kapanis-Standardi.md`

**Ölçüm tarihi:** 2026-10-31
**Tek cümle:** MVP yazıldı (PLAN Faz 0–5): backend yazma yolu, arşiv kuyruğu, CLI, dışa aktarımlar ve
MV3 eklentisi; gerçek tarayıcıda fixture x.com sayfasıyla uçtan uca sınandı. Kalan tek şey canlı x.com'da
oturum açık bir ilk yakalama ve Gün 7 saha turu.

## Ne çalışıyor (kanıtıyla)

- **Faz 0 kapalı:** S1 GO (ADR-026), S2 manuel öncelik (ADR-024/025), S3 GO + 2026-10-31 eki: x.com host izni
  `captureVisibleTab`'a yetmiyor (ADR-028), kırpmada kenar yuvarlaması 1 px kaymayı kapattı (`docs/SPIKES.md`).
- **Backend** (`backend/`, FastAPI + SQLite + Alembic 0001–0003): yakalama, birleştirme, kenarlar, hesaplar,
  arşiv işçisi, CLI (`python -m app.cli`), edges.csv / case-file / manifest `?verify`.
  `pytest`: **55 geçti**. Mutasyon denemesi: 10 bilinçli hatanın 10'u yakalandı.
- **Eklenti** (`extension/`, TypeScript strict + esbuild): x-dom çıkarıcıları (ADR-026 merdiveni, öz-denetim),
  Shadow DOM kanıt paneli (Türkçe, `DESIGN.md`), servis çalışanında yakalama + kırpma + gönderim.
  `npm run check`: tip denetimi + **26 birim testi** + derleme.
- **Uçtan uca** (`extension/scripts/e2e.mjs`, Edge 156, gerçek backend, x.com fixture'dan sunulur, ağ yok):
  **15/15** — backend kapalıyken okunur hata ve "Yeniden dene", doğrulama, kayıt mührü, alıntı kenarı,
  elle rest_id, kenar paneli, manifest doğrulaması, kırpma boyutu = gönderi × dpr, kırpmada panel/düğme
  pikseli 0.

## Doğrulanmadı / bilinen sınırlar

- **Canlı x.com:** çıkarıcı fixture'ları sentetik (S1 çıktısındaki işaretlemeye göre kuruldu). İlk gerçek
  yakalama Scryne'ın oturum açık tarayıcısında yapılmalı; X işaretlemesi değiştiyse yalnız `x-dom.ts` değişir.
- **Arşiv:** X bağlantıları için iki servis de elle (SPN2 x.com'u engelliyor, archive.today CAPTCHA). Otomatik
  yol X dışı bağlantılar ve engelin kalktığı gün için hazır; archive.org'a istisna talebi gönderilmedi
  (dışarı giden mesaj, Scryne'ın işi).
- **Takipçi sayısı** yalnız yazarın profil sayfasında ve kısaltılmamış gösterimde okunur ("48,2 B" reddedilir).
- **Gün 7 saha turu** (~20 yakalama, ≥3 hesap, bir toplu arşiv + tamamlama) yapılmadı.

## Sonraki adım

1. `backend/` → `python -m app.main`, `extension/` → `npm run build`, `dist/` klasörünü yükle, kimliği `.env`'e yaz.
2. Bir hesabın profilinden canlı bir yakalama; `export manifest --verify`.
3. PLAN Gün 7.

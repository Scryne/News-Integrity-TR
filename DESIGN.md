---
version: alpha
name: News Integrity TR — kanıt yakalama katmanı
description: X'in üstünde açılan, araştırmacının bir gönderiyi saniyeler içinde kodlayıp doğrulanabilir kanıt olarak kaydettiği koyu, sakin bir ölçüm paneli; tek vurgu mühür kırmızısı.
colors:
  surface: "#14161B"
  raised: "#1C1F26"
  sunken: "#0F1115"
  border: "#2A2E37"
  border-strong: "#3A3F4B"
  text-primary: "#ECEEF2"
  text-secondary: "#A9AFBC"
  text-tertiary: "#858C9B"
  accent: "#E0694F"
  accent-hover: "#EB7D64"
  accent-ink: "#1B0E0A"
  accent-soft: "#3A211B"
  success: "#3FB37F"
  warning: "#E3A63A"
  danger: "#F0645A"
typography:
  ui:
    fontFamily: system-ui, "Segoe UI", Roboto, sans-serif
    fontSize: 13px
  title:
    fontFamily: system-ui, "Segoe UI", Roboto, sans-serif
    fontSize: 15px
    fontWeight: 600
  mono:
    fontFamily: ui-monospace, "Cascadia Mono", Consolas, monospace
    fontSize: 12px
rounded:
  control: 6px
  panel: 12px
spacing:
  unit: 4px
  panel-padding: 16px
  panel-width: 400px
---

## Overview

Ürün, Türk haber görünümlü X hesaplarının manipülasyon örüntülerini belgeleyen yerel bir araştırma aracıdır.
Arayüz yalnız iki yüzeyden oluşur: her gönderiye eklenen küçük **Yakala / Kenar** düğmeleri ve tıklayınca
sağda açılan **kanıt paneli** (Shadow DOM). Persona, X'te gezinirken kod atayan araştırmacıdır; panelin tek
işi bir gönderiyi kaybetmeden, 15 saniyenin altında kodlayıp kaydetmektir. Panel X'in üstünde durduğu için
kendi sakin yüzeyini taşır ve X'in açık, loş ya da koyu temasından bağımsız okunur.

## Colors

- Panel `surface`, içteki gruplar `raised`, giriş alanları `sunken`. Yapı 1 px `border` ile kurulur; gölge
  yalnız panelin sayfadan ayrılması içindir.
- Tek vurgu `accent` (mühür kırmızısı): birincil "Kanıtı kaydet" düğmesi, seçili kod çipi, odak halkası.
  X'in mavisiyle karışmaması için seçildi; ikinci bir marka rengi eklenmez.
- `success` / `warning` / `danger` yalnız durum içindir: kayıt tamam, eksik kimlik, backend kapalı.
- Metin üç tondadır: `text-primary` başlık ve değer, `text-secondary` etiket ve gövde, `text-tertiary`
  açıklama ve zaman damgası. `text-tertiary` `surface` üstünde 5,4:1, `raised` üstünde 4,9:1; daha soluk gri kullanılmaz.
- Seçili çipte metin `text-primary` kalır (`accent-soft` üstünde 12,8:1); `accent` yalnız kenar ve işarettir,
  çünkü `accent-soft` üstünde küçük metin için 4,46:1 ile sınırın altında kalır.

## Typography

- `ui` her şey için; panel başlığı `title`. Düğme ve etiket cümle düzeninde, büyük harf yok.
- `mono` kimlikler içindir: rest_id, gönderi kimliği, kanıt adı (`{account_id}-{seq}`) ve SHA-256 öneki,
  `tabular-nums` ile.
- Arayüz Türkçedir; kod etiketleri ve tanımlar `taxonomy.json`'dan gelir, panel hiçbir kelimeyi sabit yazmaz.

## Layout

- Panel sağ kenarda sabit, 400 px genişlik, ekran yüksekliği kadar; içerik kayar, başlık ve alt eylem çubuğu
  sabit kalır. 480 px altında tam genişlik alt sayfa olur.
- Sıra: gönderi özeti (yazar, kimlik durumu, zaman, metnin ilk satırları) → kimlik uyarısı (gerekirse elle
  rest_id) → kategori → dört eksen halinde kod çipleri → not → etkileşim kutusu (algılandıysa) → eylemler.
- Gönderi düğmeleri gönderinin sağ üstünde küçük, yarı saydam bir şerittir; X'in kendi eylemlerini örtmez.

## Elevation & Depth

- Yalnız panelin kendisi gölgelidir (`0 12px 32px rgba(0,0,0,.45)`); içerideki hiçbir kart gölge taşımaz.
- Panel açıkken sayfa karartılmaz: araştırmacı gönderiyi görmeye devam etmelidir.

## Shapes

- Panel `panel` (12 px), düğme, giriş ve çip `control` (6 px). Çipler dikdörtgendir, hap değil.

## Components

- **Kod çipi:** solda mono kod (`H2`), sağda etiket; seçilince `accent-soft` zemin + `accent` kenar ve işaret.
  Tanım ve uluslararası karşılık `title` ile görünür.
- **Kimlik rozeti:** `dom-anchor`/`profile-header` ise yeşil nokta + mono rest_id; yoksa sarı uyarı ve elle
  giriş alanı ("Profil sayfasındaki takip düğmesinden ya da elle"). Kimlik tahmin edilmez.
- **Kaydet düğmesi:** `accent` zemin, `accent-ink` metin; kayıtta "Kaydediliyor…" ve devre dışı (çift gönderim yok).
- **Durumlar:** yükleniyor (iskelet), backend kapalı (ne olduğu, neden, nasıl başlatılır + Yeniden dene),
  reddedildi (backend'in gerekçesi), kaydedildi.

## Do's and Don'ts

- Yap: hata metnini ne oldu → neden → ne yapmalı sırasıyla yaz.
- Yap: her etkileşimli öğede görünür odak halkası; Esc paneli kapatır, Ctrl+Enter kaydeder, odak panelde kalır.
- Yapma: X'in sayfasına stil sızdırma; tüm CSS gölge kökünün içindedir.
- Yapma: eksik kimliği, takipçi sayısını ya da hedef hesabı tahminle doldurma.

## Signature

**Kanıt mührü.** Kayıt tamamlanınca panelin altında mono yazıyla kanıt adı ve SHA-256'nın ilk 12 hanesi,
ince `accent` çerçeveli bir damga gibi görünür (`1234567890123456789-0007 · sha256 3f9a1c…`). Araştırmacının
her kaydın diske doğrulanarak yazıldığını gördüğü tek yer burasıdır; başka süs yoktur.

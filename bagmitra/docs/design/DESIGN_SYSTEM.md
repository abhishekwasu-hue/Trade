# BagMitra Design System (v0 — M0)

Direction: a warm orchard brand, not Material defaults — deep leaf green, santra orange accent,
soil browns, sky blue for weather, cream background. Reference: `reference/home_mockup.html`.
All tokens live in `app/lib/theme/tokens.dart`; raw colours anywhere else fail
`test/architecture/no_inline_colors_test.dart`. The full component inventory is rendered in the
in-app gallery (`--dart-define=DEV_GALLERY=true`, route `/dev/gallery`) and snapshotted by
`test/goldens/home_golden_test.dart`.

| Home (mr, light) | Home (mr, dark) | Component gallery |
|---|---|---|
| ![](screenshots/home_mr_light.png) | ![](screenshots/home_mr_dark.png) | ![](screenshots/gallery_en_light.png) |

## Tokens

**Colour (semantic, `BmColors` light / dark)**

| Token | Light | Dark | Use |
|---|---|---|---|
| background | cream `#F3F7EE` | `#0F1A12` | page |
| card | `#FFFFFF` | `#18271B` | cards, tiles |
| ink / inkMuted | `#1B2A1E` / `#4E6153` | `#E8F0E3` / `#A9BCA9` | text |
| brand / brandStrong / brandSoft | leaf `#1F4D2B` / `#2E6B3C` / `#9BC79A` | leaf-light inverted | headings, done states |
| accent / accentSoft | santra `#F28C28` / `#FFB15C` | same | current stage, camera, hero numbers |
| sun, soil, sky | `#FFC857`, `#6B4A2B`, `#CFE8F3` | same | weather, earth, water |
| warn* | warm orange gradient | deep amber | risk alerts |
| headerGradient | leaf → leaf2 → `#3F8A4F` | night → leaf → leaf2 | home header |

**Type:** Baloo 2 for display (hero 44, big number 34, money 30, title 26, card title 24,
section 20), Mukta for body (16 minimum; meta 14 and label 13 only for secondary metadata).

**Spacing:** 4 · 8 · 12 · 16 · 18 · 24 · 32. Tap target ≥ 48 dp.
**Radius:** chip 12 · tile 18 · card 22 · hero 24 · header 40 · pill.
**Elevation:** `card` (soft, leaf-tinted), `tile` (subtle), `fab` (santra glow).
**Motion:** quick 180 ms, gentle 320 ms, pulse 1.4 s; all disabled when the OS asks for reduced
motion (`MediaQuery.disableAnimations`).

## Components (`app/lib/design_system/`)

| Component | File | Notes |
|---|---|---|
| `BmCard`, `SectionHeader` | cards.dart | one hero element per card; header action is a 48 dp text button |
| `WeatherHeader` | weather_header.dart | curved gradient, greeting, avatar, temperature hero, soil pill |
| `StageCard`, `StageTimeline` | stage_timeline.dart | illustrated bahar timeline, animated progress, done/now/upcoming states |
| `AlertBanner` | alert_banner.dart | warm gradient, pulsing icon, live region for screen readers |
| `TaskTile` | task_tile.dart | animated tick, strike-through when done, pictogram |
| `PriceHeroCard` | price_card.dart | big rupee number with Indian grouping, weekly change chip |
| `BmBottomBar`, `CameraButton`, `VoiceButton` | navigation.dart | raised centre camera; mic affordance for voice entry |
| `SyncBanner` | sync_banner.dart | offline / pending / failed states |
| `GlyphIcon` | glyphs.dart | painted illustration set (ADR 0007) |

Inputs and filled buttons are themed in `theme/app_theme.dart` (56 dp buttons, 18 dp radius).

## Rules for every UI PR
Tokens only · Marathi strings fit without overflow · works offline · works in dark mode ·
golden added/updated · screenshots (light + dark, Marathi) in the PR · honest answer to
"would a grower show this to a neighbour?".

## Next (before M1 UI work)
Empty/success-state illustrations, chips, input components with voice, photo tiles, a 2 GB
device performance profile, and a golden that asserts Home fits a 5.5" screen (OPEN_QUESTIONS Q7).

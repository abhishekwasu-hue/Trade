# ADR 0007 — Typography and illustration

Status: Accepted · 2026-10-12

**Fonts:** Baloo 2 (display; Devanagari + Latin, variable weight) and Mukta (body; Devanagari +
Latin, 400–700), both SIL OFL, bundled (~2.3 MB). They match the owner's reference mockup, read
well at large sizes, and Devanagari conjuncts render correctly. Body text ≥ 16 sp. Other scripts
(wave 2) use Noto Sans families downloaded on demand.

**Illustrations:** a small painted glyph set (`design_system/glyphs.dart`) drawn from theme
colours with `CustomPainter`: stage (drop, flower, fruit set, orange), task (spray, camera),
weather, alert and navigation glyphs. They tint for dark mode, cost no asset bytes and avoid
emoji (which render inconsistently on low-end Android). Richer SVG illustrations for empty and
success states are planned with the M1 design-system document.

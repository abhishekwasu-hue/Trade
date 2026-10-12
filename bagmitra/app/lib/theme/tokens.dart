// The only place in the app where raw colour values may appear.
// See docs/design/DESIGN_SYSTEM.md. Enforced by test/architecture/no_inline_colors_test.dart.
import 'package:flutter/material.dart';

/// Raw brand palette, taken from docs/design/reference/home_mockup.html.
abstract final class BmPalette {
  static const leaf = Color(0xFF1F4D2B);
  static const leaf2 = Color(0xFF2E6B3C);
  static const leaf3 = Color(0xFF9BC79A);
  static const leafGlow = Color(0xFF3F8A4F);
  static const santra = Color(0xFFF28C28);
  static const santra2 = Color(0xFFFFB15C);
  static const sun = Color(0xFFFFC857);
  static const soil = Color(0xFF6B4A2B);
  static const sky = Color(0xFFCFE8F3);
  static const cream = Color(0xFFF3F7EE);
  static const white = Color(0xFFFFFFFF);
  static const ink = Color(0xFF1B2A1E);
  static const ink2 = Color(0xFF4E6153);
  static const line = Color(0xFFE3EAD9);
  static const alert = Color(0xFFD64545);
  static const alertWarmBg1 = Color(0xFFFFF3E6);
  static const alertWarmBg2 = Color(0xFFFFE7CC);
  static const alertWarmBorder = Color(0xFFF7C98F);
  static const alertWarmTitle = Color(0xFF8A4B06);
  static const alertWarmBody = Color(0xFF5E4225);
  static const doneTint = Color(0xFFEEF6EC);
  static const nowTint = Color(0xFFFFF1E2);

  // Dark mode: deep night-orchard greens; accents stay recognisably santra.
  static const night = Color(0xFF0F1A12);
  static const nightCard = Color(0xFF18271B);
  static const nightLine = Color(0xFF2A3D2E);
  static const nightInk = Color(0xFFE8F0E3);
  static const nightInk2 = Color(0xFFA9BCA9);
  static const nightAlertBg1 = Color(0xFF3A2610);
  static const nightAlertBg2 = Color(0xFF2E1E0D);
  static const nightAlertBorder = Color(0xFF7A4B16);
  static const nightAlertTitle = Color(0xFFFFC27A);
  static const nightAlertBody = Color(0xFFE9D3B8);
  static const nightDoneTint = Color(0xFF213826);
  static const nightNowTint = Color(0xFF3A2610);
  static const shadow = Color(0xFF1F4D2B);
}

/// Semantic colours. Widgets use these, never [BmPalette] directly.
@immutable
class BmColors extends ThemeExtension<BmColors> {
  const BmColors({
    required this.background,
    required this.card,
    required this.ink,
    required this.inkMuted,
    required this.line,
    required this.brand,
    required this.brandStrong,
    required this.brandSoft,
    required this.accent,
    required this.accentSoft,
    required this.sun,
    required this.soil,
    required this.sky,
    required this.danger,
    required this.onBrand,
    required this.headerGradient,
    required this.warnBg,
    required this.warnBorder,
    required this.warnTitle,
    required this.warnBody,
    required this.doneTint,
    required this.nowTint,
    required this.shadow,
  });

  final Color background;
  final Color card;
  final Color ink;
  final Color inkMuted;
  final Color line;
  final Color brand;
  final Color brandStrong;
  final Color brandSoft;
  final Color accent;
  final Color accentSoft;
  final Color sun;
  final Color soil;
  final Color sky;
  final Color danger;
  final Color onBrand;
  final List<Color> headerGradient;
  final List<Color> warnBg;
  final Color warnBorder;
  final Color warnTitle;
  final Color warnBody;
  final Color doneTint;
  final Color nowTint;
  final Color shadow;

  static const light = BmColors(
    background: BmPalette.cream,
    card: BmPalette.white,
    ink: BmPalette.ink,
    inkMuted: BmPalette.ink2,
    line: BmPalette.line,
    brand: BmPalette.leaf,
    brandStrong: BmPalette.leaf2,
    brandSoft: BmPalette.leaf3,
    accent: BmPalette.santra,
    accentSoft: BmPalette.santra2,
    sun: BmPalette.sun,
    soil: BmPalette.soil,
    sky: BmPalette.sky,
    danger: BmPalette.alert,
    onBrand: BmPalette.white,
    headerGradient: [BmPalette.leaf, BmPalette.leaf2, BmPalette.leafGlow],
    warnBg: [BmPalette.alertWarmBg1, BmPalette.alertWarmBg2],
    warnBorder: BmPalette.alertWarmBorder,
    warnTitle: BmPalette.alertWarmTitle,
    warnBody: BmPalette.alertWarmBody,
    doneTint: BmPalette.doneTint,
    nowTint: BmPalette.nowTint,
    shadow: BmPalette.shadow,
  );

  static const dark = BmColors(
    background: BmPalette.night,
    card: BmPalette.nightCard,
    ink: BmPalette.nightInk,
    inkMuted: BmPalette.nightInk2,
    line: BmPalette.nightLine,
    brand: BmPalette.leaf3,
    brandStrong: BmPalette.leaf3,
    brandSoft: BmPalette.leaf2,
    accent: BmPalette.santra,
    accentSoft: BmPalette.santra2,
    sun: BmPalette.sun,
    soil: BmPalette.soil,
    sky: BmPalette.sky,
    danger: BmPalette.alert,
    onBrand: BmPalette.white,
    headerGradient: [BmPalette.night, BmPalette.leaf, BmPalette.leaf2],
    warnBg: [BmPalette.nightAlertBg1, BmPalette.nightAlertBg2],
    warnBorder: BmPalette.nightAlertBorder,
    warnTitle: BmPalette.nightAlertTitle,
    warnBody: BmPalette.nightAlertBody,
    doneTint: BmPalette.nightDoneTint,
    nowTint: BmPalette.nightNowTint,
    shadow: BmPalette.night,
  );

  /// Market hero card stays deep green in both modes (one hero colour per card).
  Color get heroCard => BmPalette.leaf;

  @override
  BmColors copyWith() => this;

  @override
  BmColors lerp(BmColors? other, double t) =>
      t < 0.5 || other == null ? this : other;
}

abstract final class BmSpace {
  static const double xxs = 4;
  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 18;
  static const double xl = 24;
  static const double xxl = 32;

  /// Minimum tap target (spec §4A: 48 dp).
  static const double tapTarget = 48;
}

abstract final class BmRadius {
  static const double chip = 12;
  static const double tile = 18;
  static const double card = 22;
  static const double hero = 24;
  static const double header = 40;
  static const double pill = 999;
}

abstract final class BmFonts {
  static const display = 'Baloo2';
  static const body = 'Mukta';
}

/// Type scale. Body never goes below 16 sp (spec §4A); small labels are reserved for
/// secondary metadata and are never the only carrier of meaning.
abstract final class BmType {
  static const _display = TextStyle(fontFamily: BmFonts.display, height: 1.1);
  static const _body = TextStyle(fontFamily: BmFonts.body, height: 1.35);

  static final heroNumber = _display.copyWith(
    fontSize: 44,
    fontWeight: FontWeight.w800,
    height: 1,
  );
  static final bigNumber = _display.copyWith(
    fontSize: 34,
    fontWeight: FontWeight.w800,
    height: 1,
  );
  static final money = _display.copyWith(
    fontSize: 30,
    fontWeight: FontWeight.w800,
    height: 1,
  );
  static final title = _display.copyWith(
    fontSize: 26,
    fontWeight: FontWeight.w800,
  );
  static final cardTitle = _display.copyWith(
    fontSize: 24,
    fontWeight: FontWeight.w700,
  );
  static final section = _display.copyWith(
    fontSize: 20,
    fontWeight: FontWeight.w700,
  );
  static final alertTitle = _display.copyWith(
    fontSize: 17,
    fontWeight: FontWeight.w700,
  );
  static final bodyStrong = _body.copyWith(
    fontSize: 16.5,
    fontWeight: FontWeight.w600,
  );
  static final body = _body.copyWith(fontSize: 16, fontWeight: FontWeight.w400);
  static final meta = _body.copyWith(fontSize: 14, fontWeight: FontWeight.w500);
  static final label = _body.copyWith(
    fontSize: 13,
    fontWeight: FontWeight.w600,
  );
}

abstract final class BmElevation {
  static List<BoxShadow> card(BmColors c) => [
    BoxShadow(
      color: c.shadow.withValues(alpha: 0.10),
      blurRadius: 28,
      offset: const Offset(0, 10),
    ),
  ];

  static List<BoxShadow> tile(BmColors c) => [
    BoxShadow(
      color: c.shadow.withValues(alpha: 0.06),
      blurRadius: 14,
      offset: const Offset(0, 4),
    ),
  ];

  static List<BoxShadow> fab(BmColors c) => [
    BoxShadow(
      color: c.accent.withValues(alpha: 0.45),
      blurRadius: 28,
      offset: const Offset(0, 12),
    ),
  ];
}

abstract final class BmMotion {
  static const quick = Duration(milliseconds: 180);
  static const gentle = Duration(milliseconds: 320);
  static const pulse = Duration(milliseconds: 1400);
}

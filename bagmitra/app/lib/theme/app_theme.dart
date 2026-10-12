import 'package:flutter/material.dart';

import 'tokens.dart';

export 'tokens.dart';

abstract final class BmTheme {
  static ThemeData light() => _build(BmColors.light, Brightness.light);
  static ThemeData dark() => _build(BmColors.dark, Brightness.dark);

  static ThemeData _build(BmColors c, Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: c.brand,
      brightness: brightness,
      primary: c.brand,
      secondary: c.accent,
      surface: c.card,
      error: c.danger,
    );
    final text = TextTheme(
      displayLarge: BmType.heroNumber,
      headlineMedium: BmType.title,
      titleLarge: BmType.cardTitle,
      titleMedium: BmType.section,
      bodyLarge: BmType.body,
      bodyMedium: BmType.body,
      labelLarge: BmType.bodyStrong,
      labelMedium: BmType.label,
      bodySmall: BmType.meta,
    ).apply(bodyColor: c.ink, displayColor: c.ink);
    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: c.background,
      fontFamily: BmFonts.body,
      textTheme: text,
      extensions: [c],
      materialTapTargetSize: MaterialTapTargetSize.padded,
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.card,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(BmRadius.tile),
          borderSide: BorderSide(color: c.line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(BmRadius.tile),
          borderSide: BorderSide(color: c.line, width: 1.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(BmRadius.tile),
          borderSide: BorderSide(color: c.brandStrong, width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: BmSpace.md,
          vertical: BmSpace.md,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: c.accent,
          foregroundColor: c.onBrand,
          minimumSize: const Size.fromHeight(56),
          textStyle: BmType.alertTitle,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(BmRadius.tile),
          ),
        ),
      ),
    );
  }
}

extension BmThemeContext on BuildContext {
  BmColors get bm => Theme.of(this).extension<BmColors>()!;
}

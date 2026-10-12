// Visual regression suite for Home (spec §4A). Regenerate with:
//   flutter test --update-goldens test/goldens
@Tags(['golden'])
library;

import 'package:bagmitra/sync/sync_engine.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/pump_app.dart';

void main() {
  final cases = <String, (Locale, ThemeMode)>{
    'home_mr_light': (const Locale('mr'), ThemeMode.light),
    'home_mr_dark': (const Locale('mr'), ThemeMode.dark),
    'home_hi_light': (const Locale('hi'), ThemeMode.light),
    'home_en_light': (const Locale('en'), ThemeMode.light),
  };
  for (final MapEntry(key: name, value: (locale, mode)) in cases.entries) {
    testWidgets(name, (tester) async {
      await pumpApp(tester, locale: locale, themeMode: mode);
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('$name.png'),
      );
    });
  }

  testWidgets('home_mr_offline', (tester) async {
    await pumpApp(
      tester,
      syncStatus: const SyncStatus(
        connectivity: Connectivity.offline,
        pending: 2,
      ),
    );
    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('home_mr_offline.png'),
    );
  });

  testWidgets('login_mr_light', (tester) async {
    await pumpApp(tester, session: null);
    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('login_mr_light.png'),
    );
  });

  testWidgets('gallery_en_light', (tester) async {
    await pumpApp(
      tester,
      locale: const Locale('en'),
      initialLocation: '/dev/gallery',
    );
    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('gallery_en_light.png'),
    );
  });
}

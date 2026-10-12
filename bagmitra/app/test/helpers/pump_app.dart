import 'dart:io';

import 'package:bagmitra/app/app.dart';
import 'package:bagmitra/app/providers.dart';
import 'package:bagmitra/core/config.dart';
import 'package:bagmitra/data/local/database.dart';
import 'package:bagmitra/features/auth/data/demo_auth_repository.dart';
import 'package:bagmitra/features/auth/domain/auth.dart';
import 'package:bagmitra/features/home/data/demo_home_repository.dart';
import 'package:bagmitra/sync/sync_engine.dart';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'test_db.dart';

const testConfig = AppConfig(
  productName: 'BagMitra',
  apiBaseUrl: 'http://localhost:8000',
  supabaseUrl: '',
  supabaseAnonKey: '',
  devGallery: true,
);

/// Serves assets straight from disk, synchronously, so screens render in one pump.
class FileAssetBundle extends CachingAssetBundle {
  @override
  Future<ByteData> load(String key) =>
      SynchronousFuture(ByteData.sublistView(File(key).readAsBytesSync()));

  @override
  Future<String> loadString(String key, {bool cache = true}) =>
      SynchronousFuture(File(key).readAsStringSync());
}

const signedIn = AuthSession(
  userId: 'u1',
  phone: '+919800000000',
  accessToken: 't',
);

/// A Pixel-5-ish phone: 393 x 851 logical px.
const phoneSize = Size(393, 851);

Future<AppDatabase> pumpApp(
  WidgetTester tester, {
  Locale locale = const Locale('mr'),
  ThemeMode themeMode = ThemeMode.light,
  AuthSession? session = signedIn,
  String? initialLocation,
  SyncStatus? syncStatus,
}) async {
  tester.view.physicalSize = phoneSize * 3;
  tester.view.devicePixelRatio = 3;
  tester.view.padding = const FakeViewPadding(top: 24 * 3);
  addTearDown(tester.view.reset);
  final db = memoryDb();
  addTearDown(db.close);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(testConfig),
        databaseProvider.overrideWithValue(db),
        authRepositoryProvider.overrideWithValue(
          DemoAuthRepository(initial: session),
        ),
        homeRepositoryProvider.overrideWithValue(
          DemoHomeRepository(bundle: FileAssetBundle()),
        ),
        if (syncStatus != null)
          syncStatusProvider.overrideWithValue(AsyncData(syncStatus)),
      ],
      child: BagMitraApp(
        locale: locale,
        themeMode: themeMode,
        initialLocation: initialLocation,
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 400));
  expect(
    find.byType(CircularProgressIndicator),
    findsNothing,
    reason: 'screen must be fully loaded before assertions/goldens',
  );
  return db;
}

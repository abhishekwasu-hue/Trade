import 'dart:convert';

import 'package:flutter/services.dart';

import '../domain/home_snapshot.dart';

/// Reads the M0 sample "today's orchard" from a language-keyed asset. This is demo content,
/// not business configuration: it is replaced by real plot/bahar/weather data in M1–M5.
class DemoHomeRepository {
  DemoHomeRepository({AssetBundle? bundle}) : _bundle = bundle ?? rootBundle;

  static const asset = 'assets/demo/home_demo.json';
  static const fallbackLanguage = 'en';

  final AssetBundle _bundle;

  Future<HomeSnapshot> load(String languageCode) async {
    final all =
        jsonDecode(await _bundle.loadString(asset)) as Map<String, dynamic>;
    final data = all[languageCode] ?? all[fallbackLanguage];
    return HomeSnapshot.fromJson(
      (data as Map<String, dynamic>).cast(),
      isDemo: true,
    );
  }
}

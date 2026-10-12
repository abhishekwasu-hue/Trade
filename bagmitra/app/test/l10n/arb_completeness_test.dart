import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Launch languages must be complete. Later-wave languages may be partial: gen-l10n falls
/// back to English for missing keys, so no string is ever blank.
const launchLocales = ['mr', 'hi'];

Map<String, dynamic> _arb(String locale) =>
    jsonDecode(File('lib/l10n/app_$locale.arb').readAsStringSync())
        as Map<String, dynamic>;

Set<String> _keys(Map<String, dynamic> arb) =>
    arb.keys.where((k) => !k.startsWith('@')).toSet();

final _placeholder = RegExp(r'\{(\w+)[,}]');

void main() {
  final en = _arb('en');
  for (final locale in launchLocales) {
    test('$locale has every key and no blank values', () {
      final arb = _arb(locale);
      expect(
        _keys(en).difference(_keys(arb)),
        isEmpty,
        reason: 'missing in $locale',
      );
      expect(
        _keys(arb).difference(_keys(en)),
        isEmpty,
        reason: 'unknown keys in $locale',
      );
      for (final k in _keys(arb)) {
        expect((arb[k] as String).trim(), isNotEmpty, reason: '$locale.$k');
      }
    });

    test('$locale keeps the same placeholders as English', () {
      final arb = _arb(locale);
      for (final k in _keys(en)) {
        Set<String> names(String s) =>
            _placeholder.allMatches(s).map((m) => m[1]!).toSet();
        expect(
          names(arb[k] as String),
          names(en[k] as String),
          reason: '$locale.$k',
        );
      }
    });
  }
}

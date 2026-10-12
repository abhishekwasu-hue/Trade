import 'dart:math';

import 'package:bagmitra/sync/backoff.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const backoff = Backoff(); // base 5 s, cap 30 min

  test('ceiling doubles per attempt', () {
    expect(backoff.ceilingFor(0), const Duration(seconds: 5));
    expect(backoff.ceilingFor(1), const Duration(seconds: 10));
    expect(backoff.ceilingFor(4), const Duration(seconds: 80));
  });

  test('ceiling is capped, even for absurd attempt counts', () {
    expect(backoff.ceilingFor(20), const Duration(minutes: 30));
    expect(backoff.ceilingFor(1000), const Duration(minutes: 30));
  });

  test('delay is jittered within [0, ceiling]', () {
    final random = Random(42);
    for (var attempt = 0; attempt < 12; attempt++) {
      final d = backoff.delayFor(attempt, random);
      expect(d, lessThanOrEqualTo(backoff.ceilingFor(attempt)));
      expect(d.isNegative, isFalse);
    }
  });
}

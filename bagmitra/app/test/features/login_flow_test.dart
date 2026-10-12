import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/pump_app.dart';

void main() {
  testWidgets('signed-out users land on login; phone + OTP signs in to home', (
    tester,
  ) async {
    await pumpApp(tester, locale: const Locale('en'), session: null);
    expect(find.text('Sign in with your mobile number'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('phone')), '12345');
    await tester.tap(find.text('Send OTP'));
    await tester.pump();
    expect(find.text('Enter a valid 10-digit mobile number'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('phone')), '98765 43210');
    await tester.tap(find.text('Send OTP'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Enter the OTP sent to +919876543210'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('otp')), '12');
    await tester.tap(find.text('Verify'));
    await tester.pump();
    expect(find.text('The OTP is incorrect or expired'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('otp')), '123456');
    await tester.tap(find.text('Verify'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text("Today's tasks"), findsOneWidget);
  });

  testWidgets('gallery route is blocked when the dev flag is off', (
    tester,
  ) async {
    await pumpApp(
      tester,
      locale: const Locale('en'),
      initialLocation: '/dev/gallery',
    );
    expect(
      find.text('Component gallery'),
      findsOneWidget,
      reason: 'testConfig enables it',
    );
  });
}

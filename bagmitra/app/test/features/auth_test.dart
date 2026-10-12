import 'package:bagmitra/features/auth/data/demo_auth_repository.dart';
import 'package:bagmitra/features/auth/domain/auth.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('normalizeIndianMobile', () {
    test('accepts common ways of writing a mobile number', () {
      for (final input in [
        '9876543210',
        '+91 98765 43210',
        '919876543210',
        '09876543210',
        '98765-43210',
      ]) {
        expect(normalizeIndianMobile(input), '+919876543210', reason: input);
      }
    });

    test('rejects landlines, short numbers and junk', () {
      for (final input in [
        '5876543210',
        '98765',
        '',
        'abcdefghij',
        '+1 9876543210',
      ]) {
        expect(normalizeIndianMobile(input), isNull, reason: input);
      }
    });
  });

  test('isValidOtp needs exactly six digits', () {
    expect(isValidOtp('123456'), isTrue);
    expect(isValidOtp('12345'), isFalse);
    expect(isValidOtp('12345a'), isFalse);
  });

  group('DemoAuthRepository', () {
    test('signs in with any 6-digit code and emits the session', () async {
      final repo = DemoAuthRepository();
      final emitted = expectLater(repo.sessions(), emits(isNotNull));
      await repo.sendOtp('+919876543210');
      final s = await repo.verifyOtp('+919876543210', '000000');
      await emitted;
      expect(repo.current, same(s));
      expect(s.userId, '00000000-0000-4000-8000-919876543210');
    });

    test('rejects a bad phone and a bad code', () async {
      final repo = DemoAuthRepository();
      await expectLater(repo.sendOtp('123'), throwsA(isA<AuthFailure>()));
      await expectLater(
        repo.verifyOtp('+919876543210', '12'),
        throwsA(
          predicate<AuthFailure>((f) => f.kind == AuthFailureKind.invalidOtp),
        ),
      );
    });

    test('sign out clears the session', () async {
      final repo = DemoAuthRepository(
        initial: const AuthSession(userId: 'u', phone: 'p', accessToken: 't'),
      );
      await repo.signOut();
      expect(repo.current, isNull);
    });
  });
}

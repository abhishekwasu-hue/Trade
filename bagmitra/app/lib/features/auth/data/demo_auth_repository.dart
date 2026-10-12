import 'dart:async';

import '../domain/auth.dart';

/// Local-only auth used when Supabase is not configured (dev, demos, golden tests).
/// Any 6-digit code signs in; the user id is derived from the phone number.
class DemoAuthRepository implements AuthRepository {
  DemoAuthRepository({AuthSession? initial}) : _current = initial;

  final _controller = StreamController<AuthSession?>.broadcast();
  AuthSession? _current;

  @override
  AuthSession? get current => _current;

  @override
  Stream<AuthSession?> sessions() => _controller.stream;

  @override
  Future<void> sendOtp(String phoneE164) async {
    if (normalizeIndianMobile(phoneE164) == null) {
      throw const AuthFailure(AuthFailureKind.invalidPhone);
    }
  }

  @override
  Future<AuthSession> verifyOtp(String phoneE164, String code) async {
    if (!isValidOtp(code)) throw const AuthFailure(AuthFailureKind.invalidOtp);
    final digits = phoneE164.replaceAll(RegExp(r'\D'), '');
    final session = AuthSession(
      userId:
          '00000000-0000-4000-8000-${digits.padLeft(12, '0').substring(0, 12)}',
      phone: phoneE164,
      accessToken: 'demo',
    );
    _set(session);
    return session;
  }

  @override
  Future<void> signOut() async => _set(null);

  void _set(AuthSession? s) {
    _current = s;
    _controller.add(s);
  }
}

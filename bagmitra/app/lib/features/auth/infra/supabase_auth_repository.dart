import 'package:supabase_flutter/supabase_flutter.dart' as sb;

import '../domain/auth.dart';

/// Phone-OTP auth via Supabase. Thin adapter; behaviour is covered by the
/// [AuthRepository] contract tests run against the demo implementation.
class SupabaseAuthRepository implements AuthRepository {
  SupabaseAuthRepository(this._client);

  final sb.SupabaseClient _client;

  static AuthSession? _map(sb.Session? s) => s == null
      ? null
      : AuthSession(
          userId: s.user.id,
          phone: s.user.phone ?? '',
          accessToken: s.accessToken,
        );

  @override
  AuthSession? get current => _map(_client.auth.currentSession);

  @override
  Stream<AuthSession?> sessions() =>
      _client.auth.onAuthStateChange.map((e) => _map(e.session));

  @override
  Future<void> sendOtp(String phoneE164) async {
    try {
      await _client.auth.signInWithOtp(phone: phoneE164);
    } on sb.AuthException {
      throw const AuthFailure(AuthFailureKind.invalidPhone);
    } on Exception {
      throw const AuthFailure(AuthFailureKind.network);
    }
  }

  @override
  Future<AuthSession> verifyOtp(String phoneE164, String code) async {
    try {
      final res = await _client.auth.verifyOTP(
        type: sb.OtpType.sms,
        phone: phoneE164,
        token: code,
      );
      return _map(res.session) ??
          (throw const AuthFailure(AuthFailureKind.invalidOtp));
    } on sb.AuthException {
      throw const AuthFailure(AuthFailureKind.invalidOtp);
    } on AuthFailure {
      rethrow;
    } on Exception {
      throw const AuthFailure(AuthFailureKind.network);
    }
  }

  @override
  Future<void> signOut() => _client.auth.signOut();
}

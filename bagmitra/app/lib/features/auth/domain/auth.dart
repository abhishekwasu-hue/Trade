class AuthSession {
  const AuthSession({
    required this.userId,
    required this.phone,
    required this.accessToken,
  });

  final String userId;
  final String phone;
  final String accessToken;
}

enum AuthFailureKind { invalidPhone, invalidOtp, network, unknown }

class AuthFailure implements Exception {
  const AuthFailure(this.kind);
  final AuthFailureKind kind;
}

abstract interface class AuthRepository {
  AuthSession? get current;
  Stream<AuthSession?> sessions();
  Future<void> sendOtp(String phoneE164);
  Future<AuthSession> verifyOtp(String phoneE164, String code);
  Future<void> signOut();
}

/// Normalises an Indian mobile number to E.164 (+91XXXXXXXXXX), or null if invalid.
/// Accepts spaces/dashes, a leading 0, 91 or +91. Indian mobiles start with 6–9.
String? normalizeIndianMobile(String input) {
  var digits = input.replaceAll(RegExp(r'[\s\-()]'), '');
  if (digits.startsWith('+91')) {
    digits = digits.substring(3);
  } else if (digits.length == 12 && digits.startsWith('91')) {
    digits = digits.substring(2);
  } else if (digits.length == 11 && digits.startsWith('0')) {
    digits = digits.substring(1);
  }
  return RegExp(r'^[6-9]\d{9}$').hasMatch(digits) ? '+91$digits' : null;
}

bool isValidOtp(String code) => RegExp(r'^\d{6}$').hasMatch(code);

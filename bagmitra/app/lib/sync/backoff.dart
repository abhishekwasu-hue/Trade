import 'dart:math';

/// Exponential backoff with full jitter: random in [0, min(cap, base * 2^attempt)].
class Backoff {
  const Backoff({
    this.base = const Duration(seconds: 5),
    this.cap = const Duration(minutes: 30),
  });

  final Duration base;
  final Duration cap;

  Duration ceilingFor(int attempt) {
    final exp = base.inMilliseconds * pow(2, attempt.clamp(0, 30));
    return Duration(milliseconds: min(exp.toInt(), cap.inMilliseconds));
  }

  Duration delayFor(int attempt, Random random) => Duration(
    milliseconds: random.nextInt(ceilingFor(attempt).inMilliseconds + 1),
  );
}

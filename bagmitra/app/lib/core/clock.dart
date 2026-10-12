/// Injectable time source so sync timing and backoff are testable.
typedef Clock = DateTime Function();

DateTime systemClock() => DateTime.now().toUtc();

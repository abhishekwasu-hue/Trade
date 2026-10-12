import '../data/local/database.dart';

enum PushStatus { applied, duplicate, stale, rejected }

class PushOutcome {
  const PushOutcome(this.id, this.status, [this.error]);

  final String id;
  final PushStatus status;
  final String? error;
}

class RemoteChange {
  const RemoteChange({
    required this.entity,
    required this.entityId,
    required this.data,
    required this.updatedAt,
  });

  final String entity;
  final String entityId;
  final Map<String, Object?> data;
  final DateTime updatedAt;
}

class PullPage {
  const PullPage(this.changes, this.cursor);

  final List<RemoteChange> changes;
  final int cursor;
}

/// No network, timeout, 5xx: retry later with backoff.
class SyncUnavailableException implements Exception {
  const SyncUnavailableException(this.reason);
  final String reason;
  @override
  String toString() => 'SyncUnavailableException($reason)';
}

/// Session expired or revoked: stop until the user signs in again.
class SyncUnauthorizedException implements Exception {
  const SyncUnauthorizedException();
}

abstract interface class SyncTransport {
  Future<List<PushOutcome>> push(List<OutboxEntry> batch);
  Future<PullPage> pull(int since);
}

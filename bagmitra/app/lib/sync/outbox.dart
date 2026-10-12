import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:uuid/uuid.dart';

import '../core/clock.dart';
import '../data/local/database.dart';

/// Queues a mutation. Call inside the same `db.transaction` as the local write.
class Outbox {
  Outbox(this._db, {this._clock = systemClock, this._uuid = const Uuid()});

  final AppDatabase _db;
  final Clock _clock;
  final Uuid _uuid;

  Future<String> enqueue({
    required String entity,
    required String entityId,
    required Map<String, Object?> payload,
    required DateTime clientUpdatedAt,
    String op = 'upsert',
  }) async {
    final id = _uuid.v4();
    await _db
        .into(_db.outboxEntries)
        .insert(
          OutboxEntriesCompanion.insert(
            id: id,
            entity: entity,
            entityId: entityId,
            op: op,
            payload: jsonEncode(payload),
            clientUpdatedAt: clientUpdatedAt.toUtc(),
            nextAttemptAt: _clock(),
            state: OutboxState.pending,
          ),
        );
    return id;
  }

  Stream<int> watchCount(OutboxState state) {
    final count = _db.outboxEntries.id.count();
    final query = _db.selectOnly(_db.outboxEntries)
      ..addColumns([count])
      ..where(_db.outboxEntries.state.equalsValue(state));
    return query.watchSingle().map((row) => row.read(count) ?? 0);
  }

  Future<bool> hasPending(String entity, String entityId) async {
    final row =
        await (_db.select(_db.outboxEntries)
              ..where(
                (t) =>
                    t.entity.equals(entity) &
                    t.entityId.equals(entityId) &
                    t.state.equalsValue(OutboxState.pending),
              )
              ..limit(1))
            .getSingleOrNull();
    return row != null;
  }
}

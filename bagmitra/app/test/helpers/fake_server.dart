import 'dart:convert';

import 'package:bagmitra/data/local/database.dart';
import 'package:bagmitra/sync/transport.dart';

/// In-memory stand-in for the API sync endpoints with the same rules: idempotent on
/// client mutation id, last-writer-wins on client_updated_at, monotonic pull cursor.
class FakeSyncServer implements SyncTransport {
  bool online = true;
  bool unauthorized = false;
  final Set<String> knownEntities = {'farmer_profile'};
  final Set<String> _seen = {};
  final Map<String, _Row> _rows = {};
  int _seq = 0;
  int pushCalls = 0;

  void _guard() {
    if (unauthorized) throw const SyncUnauthorizedException();
    if (!online) throw const SyncUnavailableException('network');
  }

  /// Simulates a write made on another device.
  void serverWrite(
    String entity,
    String id,
    Map<String, Object?> data,
    DateTime at,
  ) {
    _rows['$entity/$id'] = _Row(entity, id, data, at, ++_seq);
  }

  Map<String, Object?>? row(String entity, String id) =>
      _rows['$entity/$id']?.data;

  @override
  Future<List<PushOutcome>> push(List<OutboxEntry> batch) async {
    _guard();
    pushCalls++;
    return [
      for (final e in batch)
        if (!_seen.add(e.id))
          PushOutcome(e.id, PushStatus.duplicate)
        else if (!knownEntities.contains(e.entity))
          PushOutcome(e.id, PushStatus.rejected, 'unknown_entity')
        else
          _apply(e),
    ];
  }

  PushOutcome _apply(OutboxEntry e) {
    final key = '${e.entity}/${e.entityId}';
    final current = _rows[key];
    if (current != null && current.at.isAfter(e.clientUpdatedAt)) {
      return PushOutcome(e.id, PushStatus.stale);
    }
    final data = (jsonDecode(e.payload) as Map<String, dynamic>)
        .cast<String, Object?>();
    _rows[key] = _Row(e.entity, e.entityId, data, e.clientUpdatedAt, ++_seq);
    return PushOutcome(e.id, PushStatus.applied);
  }

  @override
  Future<PullPage> pull(int since) async {
    _guard();
    final changes = _rows.values.where((r) => r.seq > since).toList()
      ..sort((a, b) => a.seq.compareTo(b.seq));
    final cursor = changes.isEmpty ? since : changes.last.seq;
    return PullPage([
      for (final r in changes)
        RemoteChange(
          entity: r.entity,
          entityId: r.id,
          data: r.data,
          updatedAt: r.at,
        ),
    ], cursor);
  }
}

class _Row {
  _Row(this.entity, this.id, this.data, this.at, this.seq);
  final String entity;
  final String id;
  final Map<String, Object?> data;
  final DateTime at;
  final int seq;
}

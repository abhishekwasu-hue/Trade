import 'dart:async';
import 'dart:math';

import 'package:drift/drift.dart';

import '../core/clock.dart';
import '../data/local/database.dart';
import 'backoff.dart';
import 'outbox.dart';
import 'transport.dart';

/// Applies a server change to a local table. Returns normally if the change was applied
/// or intentionally skipped.
typedef ChangeApplier = Future<void> Function(RemoteChange change);

enum Connectivity { unknown, online, offline, signedOut }

class SyncStatus {
  const SyncStatus({
    this.connectivity = Connectivity.unknown,
    this.pending = 0,
    this.rejected = 0,
    this.lastSuccessAt,
  });

  final Connectivity connectivity;
  final int pending;
  final int rejected;
  final DateTime? lastSuccessAt;

  SyncStatus copyWith({
    Connectivity? connectivity,
    int? pending,
    int? rejected,
    DateTime? lastSuccessAt,
  }) => SyncStatus(
    connectivity: connectivity ?? this.connectivity,
    pending: pending ?? this.pending,
    rejected: rejected ?? this.rejected,
    lastSuccessAt: lastSuccessAt ?? this.lastSuccessAt,
  );
}

class SyncRunResult {
  const SyncRunResult({this.pushed = 0, this.pulled = 0, this.offline = false});
  final int pushed;
  final int pulled;
  final bool offline;
}

/// Drains the outbox (push) and then pulls server changes.
///
/// Conflict rules (spec §2): user data is last-writer-wins on `client_updated_at`, decided
/// by the server, with every write audited there. Locally, a pulled change never overwrites
/// an entity that still has a pending outbox entry; the pending write is pushed first and the
/// server's decision comes back on the next pull.
class SyncEngine {
  SyncEngine({
    required AppDatabase db,
    required this._transport,
    required this._appliers,
    Outbox? outbox,
    Clock clock = systemClock,
    this._backoff = const Backoff(),
    Random? random,
    this.batchSize = 50,
  }) : _db = db,
       _outbox = outbox ?? Outbox(db, clock: clock),
       _clock = clock,
       _random = random ?? Random();

  static const cursorKey = 'sync.pull.cursor';

  final AppDatabase _db;
  final SyncTransport _transport;
  final Map<String, ChangeApplier> _appliers;
  final Outbox _outbox;
  final Clock _clock;
  final Backoff _backoff;
  final Random _random;
  final int batchSize;

  final _status = StreamController<SyncStatus>.broadcast();
  SyncStatus _current = const SyncStatus();
  Future<SyncRunResult>? _running;
  StreamSubscription<int>? _pendingSub;
  StreamSubscription<int>? _rejectedSub;
  Timer? _timer;

  SyncStatus get status => _current;
  Stream<SyncStatus> get statusStream => _status.stream;

  void _emit(SyncStatus s) {
    _current = s;
    if (!_status.isClosed) _status.add(s);
  }

  /// Starts watching outbox counts and syncing periodically.
  void start({Duration interval = const Duration(minutes: 2)}) {
    _pendingSub ??= _outbox
        .watchCount(OutboxState.pending)
        .listen((n) => _emit(_current.copyWith(pending: n)));
    _rejectedSub ??= _outbox
        .watchCount(OutboxState.rejected)
        .listen((n) => _emit(_current.copyWith(rejected: n)));
    _timer ??= Timer.periodic(interval, (_) => unawaited(sync()));
    unawaited(sync());
  }

  Future<void> dispose() async {
    _timer?.cancel();
    await _pendingSub?.cancel();
    await _rejectedSub?.cancel();
    await _status.close();
  }

  /// Runs one sync cycle. Concurrent callers share the in-flight run.
  Future<SyncRunResult> sync() =>
      _running ??= _run().whenComplete(() => _running = null);

  Future<SyncRunResult> _run() async {
    try {
      final pushed = await _pushDue();
      final pulled = await _pull();
      _emit(
        _current.copyWith(
          connectivity: Connectivity.online,
          lastSuccessAt: _clock(),
        ),
      );
      return SyncRunResult(pushed: pushed, pulled: pulled);
    } on SyncUnavailableException {
      _emit(_current.copyWith(connectivity: Connectivity.offline));
      return const SyncRunResult(offline: true);
    } on SyncUnauthorizedException {
      _emit(_current.copyWith(connectivity: Connectivity.signedOut));
      return const SyncRunResult(offline: true);
    }
  }

  Future<List<OutboxEntry>> _dueBatch() {
    final now = _clock();
    return (_db.select(_db.outboxEntries)
          ..where(
            (t) =>
                t.state.equalsValue(OutboxState.pending) &
                t.nextAttemptAt.isSmallerOrEqualValue(now),
          )
          ..orderBy([(t) => OrderingTerm.asc(t.clientUpdatedAt)])
          ..limit(batchSize))
        .get();
  }

  Future<int> _pushDue() async {
    var pushed = 0;
    while (true) {
      final batch = await _dueBatch();
      if (batch.isEmpty) return pushed;
      final List<PushOutcome> outcomes;
      try {
        outcomes = await _transport.push(batch);
      } on SyncUnavailableException catch (e) {
        await _deferAll(batch, e.reason);
        rethrow;
      }
      await _settle(outcomes);
      pushed += outcomes.length;
      if (batch.length < batchSize) return pushed;
    }
  }

  Future<void> _deferAll(List<OutboxEntry> batch, String reason) async {
    final now = _clock();
    await _db.batch((b) {
      for (final e in batch) {
        b.update(
          _db.outboxEntries,
          OutboxEntriesCompanion(
            attempts: Value(e.attempts + 1),
            nextAttemptAt: Value(
              now.add(_backoff.delayFor(e.attempts, _random)),
            ),
            lastError: Value(reason),
          ),
          where: (t) => t.id.equals(e.id),
        );
      }
    });
  }

  Future<void> _settle(List<PushOutcome> outcomes) => _db.batch((b) {
    for (final o in outcomes) {
      if (o.status == PushStatus.rejected) {
        b.update(
          _db.outboxEntries,
          OutboxEntriesCompanion(
            state: const Value(OutboxState.rejected),
            lastError: Value(o.error),
          ),
          where: (t) => t.id.equals(o.id),
        );
      } else {
        // applied / duplicate: done. stale: the server kept a newer version, which the
        // following pull brings down.
        b.deleteWhere(_db.outboxEntries, (t) => t.id.equals(o.id));
      }
    }
  });

  Future<int> _pull() async {
    var since = int.tryParse(await _db.readMeta(cursorKey) ?? '') ?? 0;
    var applied = 0;
    while (true) {
      final page = await _transport.pull(since);
      for (final change in page.changes) {
        final applier = _appliers[change.entity];
        if (applier == null) continue;
        if (await _outbox.hasPending(change.entity, change.entityId)) continue;
        await applier(change);
        applied++;
      }
      await _db.writeMeta(cursorKey, '${page.cursor}');
      if (page.changes.isEmpty || page.cursor == since) return applied;
      since = page.cursor;
    }
  }
}

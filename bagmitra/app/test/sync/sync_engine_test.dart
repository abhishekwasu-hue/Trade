import 'dart:math';

import 'package:bagmitra/data/local/database.dart';
import 'package:bagmitra/sync/backoff.dart';
import 'package:bagmitra/sync/outbox.dart';
import 'package:bagmitra/sync/sync_engine.dart';
import 'package:bagmitra/sync/transport.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_server.dart';
import '../helpers/test_db.dart';

/// Always picks the top of the jitter range, making delays equal to the ceiling.
class _MaxRandom implements Random {
  @override
  int nextInt(int max) => max - 1;
  @override
  double nextDouble() => 1;
  @override
  bool nextBool() => true;
}

void main() {
  late AppDatabase db;
  late FakeSyncServer server;
  late TestClock clock;
  late Outbox outbox;
  late List<RemoteChange> applied;
  late SyncEngine engine;

  SyncEngine build({int batchSize = 50}) => SyncEngine(
    db: db,
    transport: server,
    appliers: {'farmer_profile': (c) async => applied.add(c)},
    outbox: outbox,
    clock: clock.call,
    backoff: const Backoff(
      base: Duration(seconds: 10),
      cap: Duration(minutes: 5),
    ),
    random: _MaxRandom(),
    batchSize: batchSize,
  );

  Future<String> enqueue({
    String entity = 'farmer_profile',
    String id = 'u1',
  }) => outbox.enqueue(
    entity: entity,
    entityId: id,
    payload: {'language': 'mr'},
    clientUpdatedAt: clock.now,
  );

  Future<List<OutboxEntry>> rows() => db.select(db.outboxEntries).get();

  setUp(() {
    db = memoryDb();
    server = FakeSyncServer();
    clock = TestClock();
    outbox = Outbox(db, clock: clock.call);
    applied = [];
    engine = build();
  });

  tearDown(() async {
    await engine.dispose();
    await db.close();
  });

  test('pushes pending entries and clears them on success', () async {
    await enqueue();
    final result = await engine.sync();
    expect(result.pushed, 1);
    expect(await rows(), isEmpty);
    expect(engine.status.connectivity, Connectivity.online);
    expect(engine.status.lastSuccessAt, clock.now);
  });

  test(
    'offline: keeps entries, schedules retry with backoff, reports offline',
    () async {
      await enqueue();
      server.online = false;
      final result = await engine.sync();
      expect(result.offline, isTrue);
      expect(engine.status.connectivity, Connectivity.offline);
      final [entry] = await rows();
      expect(entry.attempts, 1);
      expect(entry.lastError, 'network');
      expect(entry.nextAttemptAt, clock.now.add(const Duration(seconds: 10)));
    },
  );

  test('entries are not retried before their backoff expires', () async {
    await enqueue();
    server.online = false;
    await engine.sync();
    await engine.sync();
    expect(
      (await rows()).single.attempts,
      1,
      reason: 'still inside the 10 s backoff',
    );

    clock.advance(const Duration(seconds: 11));
    await engine.sync();
    final [entry] = await rows();
    expect(entry.attempts, 2);
    expect(
      entry.nextAttemptAt,
      clock.now.add(const Duration(seconds: 20)),
      reason: 'doubled',
    );

    server.online = true;
    clock.advance(const Duration(seconds: 5));
    expect((await engine.sync()).pushed, 0);
    clock.advance(const Duration(seconds: 16));
    expect((await engine.sync()).pushed, 1);
    expect(await rows(), isEmpty);
  });

  test(
    'rejected mutations stay visible with the error and are not retried',
    () async {
      await enqueue(entity: 'spaceship');
      await engine.sync();
      final [entry] = await rows();
      expect(entry.state, OutboxState.rejected);
      expect(entry.lastError, 'unknown_entity');
      final again = await engine.sync();
      expect(again.pushed, 0);
    },
  );

  test(
    're-pushing an already-received mutation is a no-op on the server',
    () async {
      final id = await enqueue();
      await engine.sync();
      final entry = OutboxEntry(
        id: id,
        entity: 'farmer_profile',
        entityId: 'u1',
        op: 'upsert',
        payload: '{"language":"mr"}',
        clientUpdatedAt: clock.now,
        attempts: 0,
        nextAttemptAt: clock.now,
        state: OutboxState.pending,
      );
      final [outcome] = await server.push([entry]);
      expect(outcome.status, PushStatus.duplicate);
    },
  );

  test('drains in batches', () async {
    engine = build(batchSize: 2);
    for (var i = 0; i < 5; i++) {
      await enqueue(id: 'u$i');
    }
    final result = await engine.sync();
    expect(result.pushed, 5);
    expect(server.pushCalls, 3);
  });

  test('pull applies remote changes and advances the cursor', () async {
    server.serverWrite('farmer_profile', 'u9', {'language': 'hi'}, clock.now);
    await engine.sync();
    expect(applied.single.entityId, 'u9');
    expect(await db.readMeta(SyncEngine.cursorKey), '1');
    await engine.sync();
    expect(applied, hasLength(1), reason: 'cursor prevents re-applying');
  });

  test('pull skips entities with unknown appliers and those with pending local writes', () async {
    server.serverWrite('unknown', 'x', {}, clock.now);
    server.serverWrite('farmer_profile', 'u1', {'language': 'hi'}, clock.now);
    await enqueue();
    server.online = false;
    await engine.sync();
    server.online = true;
    // Local write still pending (backoff not elapsed): server copy must not clobber it.
    clock.advance(const Duration(seconds: 1));
    await engine.sync();
    expect(applied, isEmpty);
    expect(await db.readMeta(SyncEngine.cursorKey), '2');
  });

  test('unauthorized stops the run and reports signed-out', () async {
    await enqueue();
    server.unauthorized = true;
    final result = await engine.sync();
    expect(result.offline, isTrue);
    expect(engine.status.connectivity, Connectivity.signedOut);
    expect(await rows(), hasLength(1));
  });

  test('concurrent sync calls share one run', () async {
    await enqueue();
    final results = await Future.wait([engine.sync(), engine.sync()]);
    expect(identical(results[0], results[1]), isTrue);
    expect(server.pushCalls, 1);
  });

  test(
    'status reports pending and rejected counts as the outbox changes',
    () async {
      final seen = <SyncStatus>[];
      final sub = engine.statusStream.listen(seen.add);
      server.online = false;
      engine.start(interval: const Duration(hours: 1));
      await enqueue();
      await enqueue(entity: 'spaceship', id: 'z');
      await pumpEventQueue();
      expect(engine.status.pending, 2);
      expect(engine.status.connectivity, Connectivity.offline);

      server.online = true;
      clock.advance(const Duration(hours: 1));
      await engine.sync();
      await pumpEventQueue();
      expect(engine.status.pending, 0);
      expect(engine.status.rejected, 1);
      expect(seen, isNotEmpty);
      await sub.cancel();
    },
  );
}

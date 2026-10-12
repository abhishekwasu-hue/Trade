// Spec §0.6: integration test covering offline -> online sync of a user write.
import 'dart:math';

import 'package:bagmitra/features/profile/data/profile_repository.dart';
import 'package:bagmitra/features/profile/domain/farmer_profile.dart';
import 'package:bagmitra/sync/outbox.dart';
import 'package:bagmitra/sync/sync_engine.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_server.dart';
import '../helpers/test_db.dart';

void main() {
  test(
    'profile edited offline reaches the server once the network returns',
    () async {
      final db = memoryDb();
      final clock = TestClock();
      final server = FakeSyncServer()..online = false;
      final outbox = Outbox(db, clock: clock.call);
      final repo = ProfileRepository(db, outbox: outbox, clock: clock.call);
      final engine = SyncEngine(
        db: db,
        transport: server,
        appliers: {ProfileRepository.entity: repo.applyRemote},
        outbox: outbox,
        clock: clock.call,
        random: Random(7),
      );

      const profile = FarmerProfile(
        id: 'u1',
        language: 'mr',
        displayName: 'Abhishek',
      );
      await repo.save(profile);
      expect(
        (await repo.watch('u1').first)!.displayName,
        'Abhishek',
        reason: 'saved locally',
      );

      expect((await engine.sync()).offline, isTrue);
      expect(server.row('farmer_profile', 'u1'), isNull);

      server.online = true;
      clock.advance(const Duration(minutes: 1));
      final result = await engine.sync();
      expect(result.pushed, 1);
      expect(server.row('farmer_profile', 'u1')!['display_name'], 'Abhishek');
      expect(await db.select(db.outboxEntries).get(), isEmpty);

      await engine.dispose();
      await db.close();
    },
  );

  test(
    'a newer write from another device wins over an older offline edit',
    () async {
      final db = memoryDb();
      final clock = TestClock();
      final server = FakeSyncServer()..online = false;
      final outbox = Outbox(db, clock: clock.call);
      final repo = ProfileRepository(db, outbox: outbox, clock: clock.call);
      final engine = SyncEngine(
        db: db,
        transport: server,
        appliers: {ProfileRepository.entity: repo.applyRemote},
        outbox: outbox,
        clock: clock.call,
        random: Random(3),
      );

      await repo.save(
        const FarmerProfile(id: 'u1', language: 'mr', village: 'Katol'),
      );
      await engine.sync();
      server.serverWrite('farmer_profile', 'u1', {
        'language': 'mr',
        'village': 'Warud',
      }, clock.now.add(const Duration(hours: 1)));

      server.online = true;
      clock.advance(const Duration(hours: 2));
      await engine.sync();

      expect((await repo.watch('u1').first)!.village, 'Warud');
      await engine.dispose();
      await db.close();
    },
  );
}

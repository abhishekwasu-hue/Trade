import 'package:drift/drift.dart';

import '../../../core/clock.dart';
import '../../../data/local/database.dart';
import '../../../sync/outbox.dart';
import '../../../sync/transport.dart';
import '../domain/farmer_profile.dart';

/// Offline-first: writes land locally and in the outbox atomically; sync pushes later.
class ProfileRepository {
  ProfileRepository(this._db, {Outbox? outbox, Clock clock = systemClock})
    : _outbox = outbox ?? Outbox(_db, clock: clock),
      _clock = clock;

  static const entity = 'farmer_profile';

  final AppDatabase _db;
  final Outbox _outbox;
  final Clock _clock;

  Stream<FarmerProfile?> watch(String id) =>
      (_db.select(_db.farmerProfiles)..where((t) => t.id.equals(id)))
          .watchSingleOrNull()
          .map((row) => row == null ? null : _toDomain(row));

  Future<void> save(FarmerProfile profile) {
    final now = _clock();
    return _db.transaction(() async {
      await _upsert(profile, now);
      await _outbox.enqueue(
        entity: entity,
        entityId: profile.id,
        payload: profile.toPayload(),
        clientUpdatedAt: now,
      );
    });
  }

  /// Sync applier for server changes.
  Future<void> applyRemote(RemoteChange change) => _upsert(
    FarmerProfile.fromPayload(change.entityId, change.data),
    change.updatedAt,
  );

  Future<void> _upsert(FarmerProfile p, DateTime updatedAt) => _db
      .into(_db.farmerProfiles)
      .insertOnConflictUpdate(
        FarmerProfilesCompanion.insert(
          id: p.id,
          language: p.language,
          displayName: Value(p.displayName),
          village: Value(p.village),
          taluka: Value(p.taluka),
          district: Value(p.district),
          consentDataProcessing: Value(p.consentDataProcessing),
          consentWhatsapp: Value(p.consentWhatsapp),
          clientUpdatedAt: updatedAt.toUtc(),
        ),
      );

  static FarmerProfile _toDomain(FarmerProfileRow r) => FarmerProfile(
    id: r.id,
    language: r.language,
    displayName: r.displayName,
    village: r.village,
    taluka: r.taluka,
    district: r.district,
    consentDataProcessing: r.consentDataProcessing,
    consentWhatsapp: r.consentWhatsapp,
  );
}

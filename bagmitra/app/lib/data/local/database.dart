import 'package:drift/drift.dart';
import 'package:drift_flutter/drift_flutter.dart';

part 'database.g.dart';

enum OutboxState { pending, rejected }

/// Every local user write is queued here in the same transaction as the write itself.
@DataClassName('OutboxEntry')
class OutboxEntries extends Table {
  /// Also the server-side idempotency key (client_mutation_id).
  TextColumn get id => text()();
  TextColumn get entity => text()();
  TextColumn get entityId => text()();
  TextColumn get op => text()();
  TextColumn get payload => text()();
  DateTimeColumn get clientUpdatedAt => dateTime()();
  IntColumn get attempts => integer().withDefault(const Constant(0))();
  DateTimeColumn get nextAttemptAt => dateTime()();
  TextColumn get state => textEnum<OutboxState>()();
  TextColumn get lastError => text().nullable()();

  @override
  Set<Column<Object>> get primaryKey => {id};
}

@DataClassName('FarmerProfileRow')
class FarmerProfiles extends Table {
  TextColumn get id => text()();
  TextColumn get displayName => text().nullable()();
  TextColumn get language => text()();
  TextColumn get village => text().nullable()();
  TextColumn get taluka => text().nullable()();
  TextColumn get district => text().nullable()();
  BoolColumn get consentDataProcessing =>
      boolean().withDefault(const Constant(false))();
  BoolColumn get consentWhatsapp =>
      boolean().withDefault(const Constant(false))();
  DateTimeColumn get clientUpdatedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {id};
}

/// Small key/value store for sync cursors and similar bookkeeping.
class SyncMeta extends Table {
  TextColumn get key => text()();
  TextColumn get value => text()();

  @override
  Set<Column<Object>> get primaryKey => {key};
}

@DriftDatabase(tables: [OutboxEntries, FarmerProfiles, SyncMeta])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.e);

  AppDatabase.open(String name) : super(driftDatabase(name: name));

  @override
  int get schemaVersion => 1;

  Future<String?> readMeta(String key) async {
    final row = await (select(
      syncMeta,
    )..where((t) => t.key.equals(key))).getSingleOrNull();
    return row?.value;
  }

  Future<void> writeMeta(String key, String value) =>
      into(syncMeta)
          .insertOnConflictUpdate(SyncMetaData(key: key, value: value));
}

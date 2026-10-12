import 'package:bagmitra/data/local/database.dart';
import 'package:drift/drift.dart';
import 'package:drift/native.dart';

AppDatabase memoryDb() {
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
  return AppDatabase(NativeDatabase.memory());
}

/// Manually advanced clock for deterministic backoff tests.
class TestClock {
  TestClock([DateTime? start]) : now = start ?? DateTime.utc(2026, 10, 12, 6);
  DateTime now;
  DateTime call() => now;
  void advance(Duration d) => now = now.add(d);
}

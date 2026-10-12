import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/generated/bagmitra.swagger.dart';
import '../core/config.dart';
import '../data/local/database.dart';
import '../features/auth/domain/auth.dart';
import '../features/home/data/demo_home_repository.dart';
import '../features/home/domain/home_snapshot.dart';
import '../features/profile/data/profile_repository.dart';
import '../sync/http_transport.dart';
import '../sync/sync_engine.dart';

/// Overridden in main() / tests.
final appConfigProvider = Provider<AppConfig>(
  (ref) => AppConfig.fromEnvironment(),
);

/// Overridden in main() / tests.
final databaseProvider = Provider<AppDatabase>((ref) {
  final db = AppDatabase.open('bagmitra');
  ref.onDispose(db.close);
  return db;
});

/// Overridden in main() with the Supabase or demo implementation.
final authRepositoryProvider = Provider<AuthRepository>(
  (ref) =>
      throw UnimplementedError('authRepositoryProvider must be overridden'),
);

final apiProvider = Provider<Bagmitra>((ref) {
  final config = ref.watch(appConfigProvider);
  final auth = ref.watch(authRepositoryProvider);
  return createApi(
    baseUrl: Uri.parse(config.apiBaseUrl),
    token: () => auth.current?.accessToken,
  );
});

final profileRepositoryProvider = Provider<ProfileRepository>(
  (ref) => ProfileRepository(ref.watch(databaseProvider)),
);

final syncEngineProvider = Provider<SyncEngine>((ref) {
  final engine = SyncEngine(
    db: ref.watch(databaseProvider),
    transport: HttpSyncTransport(ref.watch(apiProvider)),
    appliers: {
      ProfileRepository.entity: ref
          .watch(profileRepositoryProvider)
          .applyRemote,
    },
  );
  // Demo mode has no backend: writes stay queued locally, nothing is reported as failing.
  if (!ref.watch(appConfigProvider).demoMode) engine.start();
  ref.onDispose(engine.dispose);
  return engine;
});

final syncStatusProvider = StreamProvider<SyncStatus>((ref) {
  final engine = ref.watch(syncEngineProvider);
  return Stream.multi((controller) {
    controller.add(engine.status);
    final sub = engine.statusStream.listen(controller.add);
    controller.onCancel = sub.cancel;
  });
});

final homeRepositoryProvider = Provider<DemoHomeRepository>(
  (ref) => DemoHomeRepository(),
);

final homeSnapshotProvider = FutureProvider.family<HomeSnapshot, String>(
  (ref, languageCode) => ref.watch(homeRepositoryProvider).load(languageCode),
);

/// Task ticks made on the home screen. M1 replaces this with offline-synced task records.
class TaskTicks extends Notifier<Map<String, bool>> {
  @override
  Map<String, bool> build() => const {};

  void set(String taskId, bool done) => state = {...state, taskId: done};
}

final taskTicksProvider = NotifierProvider<TaskTicks, Map<String, bool>>(
  TaskTicks.new,
);

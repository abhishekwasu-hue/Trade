import 'package:bagmitra/features/home/data/demo_home_repository.dart';
import 'package:bagmitra/features/home/domain/home_snapshot.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/pump_app.dart';

void main() {
  final repo = DemoHomeRepository(bundle: FileAssetBundle());

  for (final lang in ['mr', 'hi', 'en']) {
    test('demo snapshot parses for $lang', () async {
      final s = await repo.load(lang);
      expect(s.isDemo, isTrue);
      expect(s.stage.milestones, hasLength(4));
      expect(s.stage.milestones[s.stage.currentIndex].kind, StageKind.fruitSet);
      expect(s.tasks.map((t) => t.kind), contains(TaskKind.spray));
      expect(s.alert, isNotNull);
      expect(s.initial, isNotEmpty);
    });
  }

  test('unknown language falls back to English, never blank', () async {
    final s = await repo.load('ta');
    expect(s.farmerName, 'Abhishek');
  });

  test('task copyWith and withTasks keep everything else', () async {
    final s = await repo.load('en');
    final ticked = s.withTasks([
      for (final t in s.tasks) t.copyWith(done: true),
    ]);
    expect(ticked.tasks.every((t) => t.done), isTrue);
    expect(ticked.market.pricePerQuintal, s.market.pricePerQuintal);
  });
}

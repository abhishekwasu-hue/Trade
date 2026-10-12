import 'package:bagmitra/design_system/navigation.dart';
import 'package:bagmitra/design_system/sync_banner.dart';
import 'package:bagmitra/design_system/task_tile.dart';
import 'package:bagmitra/sync/sync_engine.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/pump_app.dart';

void main() {
  testWidgets('shows the key home sections in Marathi', (tester) async {
    await pumpApp(tester);
    expect(find.text('आजची कामं'), findsOneWidget);
    expect(find.text('फळधारणा सुरू'), findsOneWidget);
    expect(find.text('६८'), findsOneWidget);
    expect(find.text('फोटो काढा'), findsWidgets);
  });

  testWidgets('ticking a task toggles it', (tester) async {
    await pumpApp(tester, locale: const Locale('en'));
    final spray = find.widgetWithText(TaskTile, 'Zinc + boron spray');
    expect(tester.widget<TaskTile>(spray).done, isFalse);
    await tester.tap(spray);
    await tester.pump(const Duration(milliseconds: 300));
    expect(tester.widget<TaskTile>(spray).done, isTrue);
  });

  testWidgets('offline status shows the offline banner', (tester) async {
    await pumpApp(
      tester,
      locale: const Locale('en'),
      syncStatus: const SyncStatus(connectivity: Connectivity.offline),
    );
    expect(find.byType(SyncBanner), findsOneWidget);
    expect(find.textContaining('You are offline'), findsOneWidget);
  });

  testWidgets('pending and rejected states show their banners', (tester) async {
    await pumpApp(
      tester,
      locale: const Locale('en'),
      syncStatus: const SyncStatus(
        connectivity: Connectivity.online,
        pending: 3,
      ),
    );
    expect(find.text('3 changes waiting to sync'), findsOneWidget);
  });

  testWidgets('rejected writes surface a failure banner', (tester) async {
    await pumpApp(
      tester,
      locale: const Locale('en'),
      syncStatus: const SyncStatus(
        connectivity: Connectivity.online,
        rejected: 1,
      ),
    );
    expect(find.textContaining('Sync failed'), findsOneWidget);
  });

  testWidgets('camera opens the dev gallery in dev builds', (tester) async {
    await pumpApp(tester, locale: const Locale('en'));
    await tester.tap(find.byType(CameraButton));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Component gallery'), findsOneWidget);
  });
}

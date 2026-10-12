import 'package:bagmitra/admin/admin_app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('admin shell lists config sections and switches between them', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(const AdminApp(productName: 'BagMitra'));
    await tester.pumpAndSettle();
    expect(find.text('BagMitra Admin'), findsOneWidget);
    expect(find.text('Editing arrives in Milestone 1.'), findsOneWidget);
    await tester.tap(find.text('Risk rules'));
    await tester.pumpAndSettle();
    expect(find.text('Editing arrives in Milestone 4.'), findsOneWidget);
  });
}

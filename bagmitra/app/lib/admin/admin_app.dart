import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';
import '../theme/app_theme.dart';

/// Admin web shell (ADR 0006). Sections map to the config tables that keep business
/// values out of code (spec §0.5); editors arrive with the milestones that own them.
class AdminApp extends StatelessWidget {
  const AdminApp({super.key, required this.productName});

  final String productName;

  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    theme: BmTheme.light(),
    darkTheme: BmTheme.dark(),
    supportedLocales: AppLocalizations.supportedLocales,
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    home: AdminShell(productName: productName),
  );
}

class AdminShell extends StatefulWidget {
  const AdminShell({super.key, required this.productName});

  final String productName;

  @override
  State<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends State<AdminShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.bm;
    final sections = [
      (t.adminCropTemplates, Icons.eco_rounded, 1),
      (t.adminRiskRules, Icons.thunderstorm_rounded, 4),
      (t.adminPrompts, Icons.auto_awesome_rounded, 3),
      (t.adminTranslations, Icons.translate_rounded, 1),
      (t.adminAiUsage, Icons.query_stats_rounded, 3),
    ];
    final (title, _, milestone) = sections[_index];
    return Scaffold(
      appBar: AppBar(
        backgroundColor: c.brand,
        foregroundColor: c.onBrand,
        title: Text(
          t.adminTitle(widget.productName),
          style: BmType.section.copyWith(color: c.onBrand),
        ),
      ),
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            labelType: NavigationRailLabelType.all,
            destinations: [
              for (final (label, icon, _) in sections)
                NavigationRailDestination(icon: Icon(icon), label: Text(label)),
            ],
          ),
          VerticalDivider(width: 1, color: c.line),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(BmSpace.xl),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: BmType.title.copyWith(color: c.brand)),
                  const SizedBox(height: BmSpace.sm),
                  Text(t.adminComingSoon(milestone), style: BmType.body),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

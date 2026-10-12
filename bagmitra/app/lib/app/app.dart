import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../l10n/app_localizations.dart';
import '../theme/app_theme.dart';
import 'providers.dart';
import 'router.dart';

class BagMitraApp extends ConsumerStatefulWidget {
  const BagMitraApp({
    super.key,
    this.locale,
    this.initialLocation,
    this.themeMode,
  });

  /// Forced locale (tests, user preference). Null follows the device, falling back to English.
  final Locale? locale;
  final String? initialLocation;
  final ThemeMode? themeMode;

  @override
  ConsumerState<BagMitraApp> createState() => _BagMitraAppState();
}

class _BagMitraAppState extends ConsumerState<BagMitraApp> {
  late final GoRouter _router = buildRouter(
    ref.read(authRepositoryProvider),
    ref.read(appConfigProvider),
    initialLocation: widget.initialLocation,
  );

  @override
  void dispose() {
    _router.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: ref.watch(appConfigProvider).productName,
      debugShowCheckedModeBanner: false,
      theme: BmTheme.light(),
      darkTheme: BmTheme.dark(),
      themeMode: widget.themeMode ?? ThemeMode.system,
      locale: widget.locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      localeResolutionCallback: (device, supported) {
        for (final l in supported) {
          if (l.languageCode == device?.languageCode) return l;
        }
        return const Locale('en');
      },
      routerConfig: _router,
    );
  }
}

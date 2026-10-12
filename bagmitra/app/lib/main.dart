import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'app/app.dart';
import 'app/providers.dart';
import 'core/config.dart';
import 'features/auth/data/demo_auth_repository.dart';
import 'features/auth/domain/auth.dart';
import 'features/auth/infra/supabase_auth_repository.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = AppConfig.fromEnvironment();
  final AuthRepository auth;
  if (config.demoMode) {
    auth = DemoAuthRepository();
  } else {
    await Supabase.initialize(
      url: config.supabaseUrl,
      publishableKey: config.supabaseAnonKey,
    );
    auth = SupabaseAuthRepository(Supabase.instance.client);
  }
  runApp(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(config),
        authRepositoryProvider.overrideWithValue(auth),
      ],
      child: const BagMitraApp(),
    ),
  );
}

import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../core/config.dart';
import '../features/auth/domain/auth.dart';
import '../features/auth/presentation/login_screens.dart';
import '../features/dev/component_gallery_screen.dart';
import '../features/home/presentation/home_screen.dart';

class _AuthListenable extends ChangeNotifier {
  _AuthListenable(Stream<AuthSession?> sessions) {
    _sub = sessions.listen((_) => notifyListeners());
  }
  late final StreamSubscription<AuthSession?> _sub;

  @override
  void dispose() {
    unawaited(_sub.cancel());
    super.dispose();
  }
}

abstract final class Routes {
  static const home = '/';
  static const login = '/login';
  static const otp = '/login/otp';
  static const gallery = '/dev/gallery';
}

GoRouter buildRouter(
  AuthRepository auth,
  AppConfig config, {
  String? initialLocation,
}) {
  final refresh = _AuthListenable(auth.sessions());
  return GoRouter(
    initialLocation: initialLocation ?? Routes.home,
    refreshListenable: refresh,
    redirect: (context, state) {
      final signedIn = auth.current != null;
      final loc = state.matchedLocation;
      final onLogin = loc.startsWith(Routes.login);
      if (loc == Routes.gallery) return config.devGallery ? null : Routes.home;
      if (!signedIn && !onLogin) return Routes.login;
      if (signedIn && onLogin) return Routes.home;
      return null;
    },
    routes: [
      GoRoute(path: Routes.home, builder: (_, _) => const HomeScreen()),
      GoRoute(path: Routes.login, builder: (_, _) => const PhoneLoginScreen()),
      GoRoute(
        path: Routes.otp,
        builder: (_, state) =>
            OtpScreen(phone: state.uri.queryParameters['phone'] ?? ''),
      ),
      GoRoute(
        path: Routes.gallery,
        builder: (_, _) => const ComponentGalleryScreen(),
      ),
    ],
  );
}

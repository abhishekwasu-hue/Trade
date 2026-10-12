import 'package:flutter/material.dart';

import 'admin/admin_app.dart';
import 'core/config.dart';

/// Admin web entrypoint: flutter run -d chrome -t lib/main_admin.dart
void main() =>
    runApp(AdminApp(productName: AppConfig.fromEnvironment().productName));

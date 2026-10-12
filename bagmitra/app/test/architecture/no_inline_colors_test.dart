import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Spec §4A: no inline colours anywhere. Raw colours may only appear in lib/theme/.
void main() {
  test('raw colour literals only appear in lib/theme', () {
    final forbidden = RegExp(
      r'Color\(0x|Color\.fromARGB|Color\.fromRGBO|\bColors\.',
    );
    final offenders = <String>[];
    for (final f in Directory(
      'lib',
    ).listSync(recursive: true).whereType<File>()) {
      final path = f.path.replaceAll(r'\', '/');
      if (!path.endsWith('.dart') ||
          path.startsWith('lib/theme/') ||
          path.contains('/generated/') ||
          path.endsWith('.g.dart')) {
        continue;
      }
      final lines = f.readAsLinesSync();
      for (var i = 0; i < lines.length; i++) {
        if (forbidden.hasMatch(lines[i])) {
          offenders.add('$path:${i + 1}: ${lines[i].trim()}');
        }
      }
    }
    expect(offenders, isEmpty, reason: offenders.join('\n'));
  });
}

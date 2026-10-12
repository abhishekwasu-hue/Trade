// Fails when line coverage of the app's logic layers drops below the gate (spec §0.1).
// Usage: flutter test --coverage && dart run tool/coverage_gate.dart [minPercent]
import 'dart:io';

final _logic = RegExp(r'^lib/(core|data|sync|features/[^/]+/(domain|data))/');

void main(List<String> args) {
  final min = args.isEmpty ? 80.0 : double.parse(args.first);
  final lcov = File('coverage/lcov.info');
  if (!lcov.existsSync()) {
    stderr.writeln('coverage/lcov.info missing: run flutter test --coverage');
    exit(2);
  }
  var found = 0;
  var hit = 0;
  String? file;
  final perFile = <String, (int, int)>{};
  for (final line in lcov.readAsLinesSync()) {
    if (line.startsWith('SF:')) {
      file = line.substring(3).replaceAll(r'\', '/');
      final i = file.indexOf('lib/');
      file = i < 0 ? file : file.substring(i);
    } else if (line.startsWith('DA:') && file != null) {
      if (!_logic.hasMatch(file) || file.endsWith('.g.dart')) continue;
      final count = int.parse(line.split(',')[1]);
      found++;
      if (count > 0) hit++;
      final (f, h) = perFile[file] ?? (0, 0);
      perFile[file] = (f + 1, h + (count > 0 ? 1 : 0));
    }
  }
  if (found == 0) {
    stderr.writeln('no logic-layer lines found in lcov');
    exit(2);
  }
  for (final MapEntry(key: f, value: (n, h)) in perFile.entries) {
    stdout.writeln('${(100 * h / n).toStringAsFixed(1).padLeft(6)}%  $f');
  }
  final pct = 100 * hit / found;
  stdout.writeln(
    'Logic coverage: ${pct.toStringAsFixed(2)}% ($hit/$found), gate ${min.toStringAsFixed(0)}%',
  );
  if (pct < min) exit(1);
}

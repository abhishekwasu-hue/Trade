import 'dart:convert';
import 'dart:io';

import 'package:bagmitra/api/api_client.dart';
import 'package:bagmitra/data/local/database.dart';
import 'package:bagmitra/sync/http_transport.dart';
import 'package:bagmitra/sync/transport.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

OutboxEntry _entry(String id) => OutboxEntry(
  id: id,
  entity: 'farmer_profile',
  entityId: 'u1',
  op: 'upsert',
  payload: '{"language":"mr"}',
  clientUpdatedAt: DateTime.utc(2026, 10, 12),
  attempts: 0,
  nextAttemptAt: DateTime.utc(2026, 10, 12),
  state: OutboxState.pending,
);

HttpSyncTransport _transport(MockClientHandler handler) => HttpSyncTransport(
  createApi(
    baseUrl: Uri.parse('https://api.example.test'),
    token: () => 'tok',
    httpClient: MockClient(handler),
  ),
  timeout: const Duration(milliseconds: 200),
);

http.Response _json(Object body, [int status = 200]) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json'},
);

void main() {
  test('push sends mutations with auth header and maps results', () async {
    late http.Request seen;
    final t = _transport((req) async {
      seen = req;
      return _json({
        'results': [
          {'client_mutation_id': 'a', 'status': 'applied'},
          {'client_mutation_id': 'b', 'status': 'duplicate'},
          {'client_mutation_id': 'c', 'status': 'stale'},
          {
            'client_mutation_id': 'd',
            'status': 'rejected',
            'error': 'invalid_payload',
          },
        ],
      });
    });
    final out = await t.push([
      _entry('a'),
      _entry('b'),
      _entry('c'),
      _entry('d'),
    ]);
    expect(seen.url.path, '/v1/sync/push');
    expect(seen.headers['Authorization'], 'Bearer tok');
    final sent = jsonDecode(seen.body) as Map<String, dynamic>;
    final first =
        (sent['mutations'] as List<dynamic>).first as Map<String, dynamic>;
    expect(first['entity'], 'farmer_profile');
    expect(first['op'], 'upsert');
    expect(first['payload'], {'language': 'mr'});
    expect(out.map((o) => o.status), [
      PushStatus.applied,
      PushStatus.duplicate,
      PushStatus.stale,
      PushStatus.rejected,
    ]);
    expect(out.last.error, 'invalid_payload');
  });

  test('pull maps changes and cursor', () async {
    final t = _transport((req) async {
      expect(req.url.queryParameters['since'], '5');
      return _json({
        'cursor': 9,
        'changes': [
          {
            'entity': 'farmer_profile',
            'entity_id': 'u1',
            'op': 'upsert',
            'data': {'language': 'hi'},
            'updated_at': '2026-10-12T06:00:00Z',
            'seq': 9,
          },
        ],
      });
    });
    final page = await t.pull(5);
    expect(page.cursor, 9);
    expect(page.changes.single.data['language'], 'hi');
    expect(page.changes.single.updatedAt, DateTime.utc(2026, 10, 12, 6));
  });

  test('401 means signed out', () async {
    final t = _transport(
      (_) async => _json(<String, Object>{'error': <String, Object>{}}, 401),
    );
    expect(() => t.pull(0), throwsA(isA<SyncUnauthorizedException>()));
  });

  test('5xx, socket errors and timeouts mean try later', () async {
    expect(
      () => _transport((_) async => _json({}, 503)).pull(0),
      throwsA(isA<SyncUnavailableException>()),
    );
    expect(
      () =>
          _transport((_) async => throw const SocketException('down')).pull(0),
      throwsA(isA<SyncUnavailableException>()),
    );
    expect(
      () => _transport((_) async => throw const HttpException('reset')).pull(0),
      throwsA(isA<SyncUnavailableException>()),
    );
    expect(
      () => _transport(
        (_) => Future.delayed(const Duration(seconds: 2), () => _json({})),
      ).pull(0),
      throwsA(isA<SyncUnavailableException>()),
    );
  });
}

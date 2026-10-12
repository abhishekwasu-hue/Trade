import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:chopper/chopper.dart';

import '../api/generated/bagmitra.enums.swagger.dart' as enums;
import '../api/generated/bagmitra.swagger.dart';
import '../data/local/database.dart';
import 'transport.dart';

/// [SyncTransport] over the client generated from docs/api/openapi.json.
class HttpSyncTransport implements SyncTransport {
  HttpSyncTransport(this._api, {this.timeout = const Duration(seconds: 20)});

  final Bagmitra _api;
  final Duration timeout;

  @override
  Future<List<PushOutcome>> push(List<OutboxEntry> batch) async {
    final body = PushRequest(
      mutations: [
        for (final e in batch)
          Mutation(
            clientMutationId: e.id,
            entity: e.entity,
            entityId: e.entityId,
            op: enums.MutationOp.values.byName(e.op),
            clientUpdatedAt: e.clientUpdatedAt.toUtc(),
            payload: jsonDecode(e.payload) as Map<String, dynamic>,
          ),
      ],
    );
    final resp = _check(await _guard(() => _api.v1SyncPushPost(body: body)));
    return [
      for (final r in resp.results)
        PushOutcome(r.clientMutationId, _status(r.status), r.error),
    ];
  }

  @override
  Future<PullPage> pull(int since) async {
    final resp = _check(await _guard(() => _api.v1SyncPullGet(since: since)));
    return PullPage([
      for (final c in resp.changes)
        RemoteChange(
          entity: c.entity,
          entityId: c.entityId,
          data: Map<String, Object?>.from(c.data),
          updatedAt: c.updatedAt.toUtc(),
        ),
    ], resp.cursor);
  }

  static PushStatus _status(enums.MutationResultStatus s) => switch (s) {
    enums.MutationResultStatus.applied => PushStatus.applied,
    enums.MutationResultStatus.duplicate => PushStatus.duplicate,
    enums.MutationResultStatus.stale => PushStatus.stale,
    _ => PushStatus.rejected,
  };

  Future<Response<T>> _guard<T>(Future<Response<T>> Function() call) async {
    try {
      return await call().timeout(timeout);
    } on TimeoutException {
      throw const SyncUnavailableException('timeout');
    } on SocketException {
      throw const SyncUnavailableException('network');
    } on HttpException {
      throw const SyncUnavailableException('network');
    }
  }

  static T _check<T>(Response<T> resp) {
    if (resp.statusCode == 401 || resp.statusCode == 403) {
      throw const SyncUnauthorizedException();
    }
    final body = resp.body;
    if (!resp.isSuccessful || body == null) {
      throw SyncUnavailableException('http ${resp.statusCode}');
    }
    return body;
  }
}

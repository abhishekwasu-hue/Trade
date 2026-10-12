// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element_parameter

import 'package:json_annotation/json_annotation.dart';
import 'package:json_annotation/json_annotation.dart' as json;
import 'package:collection/collection.dart';

import 'dart:convert';

import 'bagmitra.models.swagger.dart';

import 'package:chopper/chopper.dart';

import 'client_mapping.dart';

import 'dart:async';

import 'package:http/http.dart' as http;
import 'package:http/http.dart' show MultipartFile;
import 'package:chopper/chopper.dart' as chopper;

import 'bagmitra.enums.swagger.dart' as enums;
import 'bagmitra.metadata.swagger.dart';
export 'bagmitra.enums.swagger.dart';
export 'bagmitra.models.swagger.dart';

part 'bagmitra.swagger.chopper.dart';

// **************************************************************************
// SwaggerChopperGenerator
// **************************************************************************

@ChopperApi()
abstract class Bagmitra extends ChopperService {
  static Bagmitra create({
    ChopperClient? client,
    http.Client? httpClient,
    Authenticator? authenticator,
    ErrorConverter? errorConverter,
    Converter? converter,
    Uri? baseUrl,
    List<Interceptor>? interceptors,
  }) {
    if (client != null) {
      return _$Bagmitra(client);
    }

    final newClient = ChopperClient(
      services: [_$Bagmitra()],
      converter: converter ?? $JsonSerializableConverter(),
      interceptors: interceptors ?? [],
      client: httpClient,
      authenticator: authenticator,
      errorConverter: errorConverter,
      baseUrl: baseUrl ?? Uri.parse('http://'),
    );
    return _$Bagmitra(newClient);
  }

  ///Live
  Future<chopper.Response<LiveResponse>> healthLiveGet() {
    generatedMapping.putIfAbsent(
      LiveResponse,
      () => LiveResponse.fromJsonFactory,
    );

    return _healthLiveGet();
  }

  ///Live
  @GET(path: '/health/live')
  Future<chopper.Response<LiveResponse>> _healthLiveGet({
    @chopper.Tag()
    SwaggerMetaData swaggerMetaData = const SwaggerMetaData(
      description: '',
      summary: 'Live',
      operationId: 'health_live',
      consumes: [],
      produces: [],
      security: [],
      tags: ["health"],
      deprecated: false,
    ),
  });

  ///Ready
  Future<chopper.Response<ReadyResponse>> healthReadyGet() {
    generatedMapping.putIfAbsent(
      ReadyResponse,
      () => ReadyResponse.fromJsonFactory,
    );

    return _healthReadyGet();
  }

  ///Ready
  @GET(path: '/health/ready')
  Future<chopper.Response<ReadyResponse>> _healthReadyGet({
    @chopper.Tag()
    SwaggerMetaData swaggerMetaData = const SwaggerMetaData(
      description: '',
      summary: 'Ready',
      operationId: 'health_ready',
      consumes: [],
      produces: [],
      security: [],
      tags: ["health"],
      deprecated: false,
    ),
  });

  ///Get Me
  Future<chopper.Response<FarmerProfile>> v1MeGet() {
    generatedMapping.putIfAbsent(
      FarmerProfile,
      () => FarmerProfile.fromJsonFactory,
    );

    return _v1MeGet();
  }

  ///Get Me
  @GET(path: '/v1/me')
  Future<chopper.Response<FarmerProfile>> _v1MeGet({
    @chopper.Tag()
    SwaggerMetaData swaggerMetaData = const SwaggerMetaData(
      description: '',
      summary: 'Get Me',
      operationId: 'me_get',
      consumes: [],
      produces: [],
      security: ["HTTPBearer"],
      tags: ["profile"],
      deprecated: false,
    ),
  });

  ///Pull
  ///@param since
  Future<chopper.Response<PullResponse>> v1SyncPullGet({int? since}) {
    generatedMapping.putIfAbsent(
      PullResponse,
      () => PullResponse.fromJsonFactory,
    );

    return _v1SyncPullGet(since: since);
  }

  ///Pull
  ///@param since
  @GET(path: '/v1/sync/pull')
  Future<chopper.Response<PullResponse>> _v1SyncPullGet({
    @Query('since') int? since,
    @chopper.Tag()
    SwaggerMetaData swaggerMetaData = const SwaggerMetaData(
      description: '',
      summary: 'Pull',
      operationId: 'sync_pull',
      consumes: [],
      produces: [],
      security: ["HTTPBearer"],
      tags: ["sync"],
      deprecated: false,
    ),
  });

  ///Push
  Future<chopper.Response<PushResponse>> v1SyncPushPost({
    required PushRequest? body,
  }) {
    generatedMapping.putIfAbsent(
      PushResponse,
      () => PushResponse.fromJsonFactory,
    );

    return _v1SyncPushPost(body: body);
  }

  ///Push
  @POST(path: '/v1/sync/push', optionalBody: true)
  Future<chopper.Response<PushResponse>> _v1SyncPushPost({
    @Body() required PushRequest? body,
    @chopper.Tag()
    SwaggerMetaData swaggerMetaData = const SwaggerMetaData(
      description: '''Apply a batch of offline mutations. Each mutation gets its own result; the batch
never fails as a whole because of one bad mutation.''',
      summary: 'Push',
      operationId: 'sync_push',
      consumes: [],
      produces: [],
      security: ["HTTPBearer"],
      tags: ["sync"],
      deprecated: false,
    ),
  });
}

typedef $JsonFactory<T> = T Function(Map<String, dynamic> json);

class $CustomJsonDecoder {
  $CustomJsonDecoder(this.factories);

  final Map<Type, $JsonFactory> factories;

  dynamic decode<T>(dynamic entity) {
    if (entity is Iterable) {
      return _decodeList<T>(entity);
    }

    if (entity is T) {
      return entity;
    }

    if (isTypeOf<T, Map>()) {
      return entity;
    }

    if (isTypeOf<T, Iterable>()) {
      return entity;
    }

    if (entity is Map<String, dynamic>) {
      return _decodeMap<T>(entity);
    }

    return entity;
  }

  T _decodeMap<T>(Map<String, dynamic> values) {
    final jsonFactory = factories[T];
    if (jsonFactory == null || jsonFactory is! $JsonFactory<T>) {
      return throw "Could not find factory for type $T. Is '$T: $T.fromJsonFactory' included in the CustomJsonDecoder instance creation in bootstrapper.dart?";
    }

    return jsonFactory(values);
  }

  List<T> _decodeList<T>(Iterable values) =>
      values.where((v) => v != null).map<T>((v) => decode<T>(v) as T).toList();
}

class $JsonSerializableConverter extends chopper.JsonConverter {
  @override
  FutureOr<chopper.Response<ResultType>> convertResponse<ResultType, Item>(
    chopper.Response response,
  ) async {
    if (response.bodyString.isEmpty) {
      // In rare cases, when let's say 204 (no content) is returned -
      // we cannot decode the missing json with the result type specified
      return chopper.Response(response.base, null, error: response.error);
    }

    if (ResultType == String) {
      return response.copyWith();
    }

    if (ResultType == DateTime) {
      return response.copyWith(
        body: DateTime.parse(
          (response.body as String).replaceAll('"', ''),
        ) as ResultType,
      );
    }

    final jsonRes = await super.convertResponse(response);
    return jsonRes.copyWith<ResultType>(
      body: $jsonDecoder.decode<Item>(jsonRes.body) as ResultType,
    );
  }
}

final $jsonDecoder = $CustomJsonDecoder(generatedMapping);

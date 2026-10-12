// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'bagmitra.models.swagger.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Change _$ChangeFromJson(Map<String, dynamic> json) => Change(
  data: json['data'] as Map<String, dynamic>,
  entity: json['entity'] as String,
  entityId: json['entity_id'] as String,
  op: changeOpFromJson(json['op']),
  seq: (json['seq'] as num).toInt(),
  updatedAt: DateTime.parse(json['updated_at'] as String),
);

Map<String, dynamic> _$ChangeToJson(Change instance) => <String, dynamic>{
  'data': instance.data,
  'entity': instance.entity,
  'entity_id': instance.entityId,
  'op': ?changeOpToJson(instance.op),
  'seq': instance.seq,
  'updated_at': instance.updatedAt.toIso8601String(),
};

ErrorBody _$ErrorBodyFromJson(Map<String, dynamic> json) => ErrorBody(
  code: json['code'] as String,
  message: json['message'] as String,
  requestId: json['request_id'] as String,
);

Map<String, dynamic> _$ErrorBodyToJson(ErrorBody instance) => <String, dynamic>{
  'code': instance.code,
  'message': instance.message,
  'request_id': instance.requestId,
};

ErrorResponse _$ErrorResponseFromJson(Map<String, dynamic> json) =>
    ErrorResponse(
      error: ErrorBody.fromJson(json['error'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$ErrorResponseToJson(ErrorResponse instance) =>
    <String, dynamic>{'error': instance.error.toJson()};

FarmerProfile _$FarmerProfileFromJson(Map<String, dynamic> json) =>
    FarmerProfile(
      consentDataProcessing: json['consent_data_processing'] as bool,
      consentWhatsapp: json['consent_whatsapp'] as bool,
      displayName: json['display_name'] as String?,
      district: json['district'] as String?,
      id: json['id'] as String,
      language: json['language'] as String,
      phone: json['phone'] as String?,
      taluka: json['taluka'] as String?,
      village: json['village'] as String?,
    );

Map<String, dynamic> _$FarmerProfileToJson(FarmerProfile instance) =>
    <String, dynamic>{
      'consent_data_processing': instance.consentDataProcessing,
      'consent_whatsapp': instance.consentWhatsapp,
      'display_name': ?instance.displayName,
      'district': ?instance.district,
      'id': instance.id,
      'language': instance.language,
      'phone': ?instance.phone,
      'taluka': ?instance.taluka,
      'village': ?instance.village,
    };

LiveResponse _$LiveResponseFromJson(Map<String, dynamic> json) => LiveResponse(
  product: json['product'] as String,
  status: json['status'] as String,
);

Map<String, dynamic> _$LiveResponseToJson(LiveResponse instance) =>
    <String, dynamic>{'product': instance.product, 'status': instance.status};

Mutation _$MutationFromJson(Map<String, dynamic> json) => Mutation(
  clientMutationId: json['client_mutation_id'] as String,
  clientUpdatedAt: DateTime.parse(json['client_updated_at'] as String),
  entity: json['entity'] as String,
  entityId: json['entity_id'] as String,
  op: mutationOpFromJson(json['op']),
  payload: json['payload'] as Map<String, dynamic>,
);

Map<String, dynamic> _$MutationToJson(Mutation instance) => <String, dynamic>{
  'client_mutation_id': instance.clientMutationId,
  'client_updated_at': instance.clientUpdatedAt.toIso8601String(),
  'entity': instance.entity,
  'entity_id': instance.entityId,
  'op': ?mutationOpToJson(instance.op),
  'payload': instance.payload,
};

MutationResult _$MutationResultFromJson(Map<String, dynamic> json) =>
    MutationResult(
      clientMutationId: json['client_mutation_id'] as String,
      error: json['error'] as String?,
      status: mutationResultStatusFromJson(json['status']),
    );

Map<String, dynamic> _$MutationResultToJson(MutationResult instance) =>
    <String, dynamic>{
      'client_mutation_id': instance.clientMutationId,
      'error': ?instance.error,
      'status': ?mutationResultStatusToJson(instance.status),
    };

PullResponse _$PullResponseFromJson(Map<String, dynamic> json) => PullResponse(
  changes:
      (json['changes'] as List<dynamic>?)
          ?.map((e) => Change.fromJson(e as Map<String, dynamic>))
          .toList() ??
      [],
  cursor: (json['cursor'] as num).toInt(),
);

Map<String, dynamic> _$PullResponseToJson(PullResponse instance) =>
    <String, dynamic>{
      'changes': instance.changes.map((e) => e.toJson()).toList(),
      'cursor': instance.cursor,
    };

PushRequest _$PushRequestFromJson(Map<String, dynamic> json) => PushRequest(
  mutations:
      (json['mutations'] as List<dynamic>?)
          ?.map((e) => Mutation.fromJson(e as Map<String, dynamic>))
          .toList() ??
      [],
);

Map<String, dynamic> _$PushRequestToJson(PushRequest instance) =>
    <String, dynamic>{
      'mutations': instance.mutations.map((e) => e.toJson()).toList(),
    };

PushResponse _$PushResponseFromJson(Map<String, dynamic> json) => PushResponse(
  results:
      (json['results'] as List<dynamic>?)
          ?.map((e) => MutationResult.fromJson(e as Map<String, dynamic>))
          .toList() ??
      [],
);

Map<String, dynamic> _$PushResponseToJson(PushResponse instance) =>
    <String, dynamic>{
      'results': instance.results.map((e) => e.toJson()).toList(),
    };

ReadyResponse _$ReadyResponseFromJson(Map<String, dynamic> json) =>
    ReadyResponse(
      database: json['database'] as String,
      status: json['status'] as String,
    );

Map<String, dynamic> _$ReadyResponseToJson(ReadyResponse instance) =>
    <String, dynamic>{'database': instance.database, 'status': instance.status};

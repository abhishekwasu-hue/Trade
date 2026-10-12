// coverage:ignore-file
// ignore_for_file: type=lint

import 'package:json_annotation/json_annotation.dart';
import 'package:collection/collection.dart';

enum ChangeOp {
  @JsonValue(null)
  swaggerGeneratedUnknown(null),

  @JsonValue('upsert')
  upsert('upsert'),
  @JsonValue('delete')
  delete('delete');

  final String? value;

  const ChangeOp(this.value);
}

enum MutationOp {
  @JsonValue(null)
  swaggerGeneratedUnknown(null),

  @JsonValue('upsert')
  upsert('upsert'),
  @JsonValue('delete')
  delete('delete');

  final String? value;

  const MutationOp(this.value);
}

enum MutationResultStatus {
  @JsonValue(null)
  swaggerGeneratedUnknown(null),

  @JsonValue('applied')
  applied('applied'),
  @JsonValue('duplicate')
  duplicate('duplicate'),
  @JsonValue('stale')
  stale('stale'),
  @JsonValue('rejected')
  rejected('rejected');

  final String? value;

  const MutationResultStatus(this.value);
}

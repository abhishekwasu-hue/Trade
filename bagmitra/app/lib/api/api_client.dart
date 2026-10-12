import 'dart:async';

import 'package:chopper/chopper.dart';
import 'package:http/http.dart' as http;

import 'generated/bagmitra.swagger.dart';

/// Supplies the current access token, or null when signed out.
typedef TokenProvider = FutureOr<String?> Function();

class AuthHeaderInterceptor implements Interceptor {
  const AuthHeaderInterceptor(this._token);
  final TokenProvider _token;

  @override
  FutureOr<Response<BodyType>> intercept<BodyType>(
    Chain<BodyType> chain,
  ) async {
    final token = await _token();
    final request = token == null
        ? chain.request
        : applyHeader(chain.request, 'Authorization', 'Bearer $token');
    return chain.proceed(request);
  }
}

Bagmitra createApi({
  required Uri baseUrl,
  required TokenProvider token,
  http.Client? httpClient,
}) => Bagmitra.create(
  baseUrl: baseUrl,
  httpClient: httpClient,
  interceptors: [AuthHeaderInterceptor(token)],
);

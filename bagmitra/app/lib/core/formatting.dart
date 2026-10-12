import 'package:intl/intl.dart';

/// Indian-format numbers per locale: lakh grouping, native digits where the locale uses
/// them (e.g. Marathi ३,२००), Latin digits for English (en_IN).
String _intlLocale(String languageCode) =>
    languageCode == 'en' ? 'en_IN' : languageCode;

String formatInt(int value, String languageCode) =>
    NumberFormat.decimalPattern(_intlLocale(languageCode)).format(value);

String formatRupees(int value, String languageCode) =>
    '₹${formatInt(value, languageCode)}';

String formatPercent(int value, String languageCode) =>
    '${formatInt(value, languageCode)}%';

String formatMonth(DateTime date, String languageCode) =>
    DateFormat.MMMM(_intlLocale(languageCode)).format(date);

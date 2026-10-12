import 'package:bagmitra/core/config.dart';
import 'package:bagmitra/core/formatting.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

void main() {
  setUpAll(initializeDateFormatting);

  test('Indian lakh grouping and native digits per locale', () {
    expect(formatInt(125000, 'en'), '1,25,000');
    expect(formatInt(3200, 'mr'), '३,२००');
    expect(formatInt(3200, 'hi'), '3,200');
    expect(formatRupees(3200, 'mr'), '₹३,२००');
    expect(formatPercent(8, 'en'), '8%');
  });

  test('month names are localised', () {
    expect(formatMonth(DateTime(2027, 2), 'en'), 'February');
    expect(formatMonth(DateTime(2027, 2), 'mr'), 'फेब्रुवारी');
  });

  test('config defaults to demo mode without Supabase credentials', () {
    final c = AppConfig.fromEnvironment();
    expect(c.productName, 'BagMitra');
    expect(c.demoMode, isTrue);
    expect(c.devGallery, isFalse);
  });
}

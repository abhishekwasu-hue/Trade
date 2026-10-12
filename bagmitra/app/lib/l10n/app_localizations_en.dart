// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get greetingHello => 'Namaste';

  @override
  String greetingName(String name) {
    return '$name ji';
  }

  @override
  String temperature(int degrees) {
    final intl.NumberFormat degreesNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String degreesString = degreesNumberFormat.format(degrees);

    return '$degreesString°';
  }

  @override
  String maxTemperature(int degrees) {
    final intl.NumberFormat degreesNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String degreesString = degreesNumberFormat.format(degrees);

    return 'Max $degreesString°';
  }

  @override
  String soilMoisture(int percent) {
    final intl.NumberFormat percentNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String percentString = percentNumberFormat.format(percent);

    return 'Soil moisture $percentString%';
  }

  @override
  String get stageDays => 'days';

  @override
  String nextStage(String stage, int days, String month) {
    final intl.NumberFormat daysNumberFormat = intl.NumberFormat.decimalPattern(
      localeName,
    );
    final String daysString = daysNumberFormat.format(days);

    return 'Next stage: $stage · in about $daysString days · harvest $month';
  }

  @override
  String get todaysTasks => 'Today\'s tasks';

  @override
  String get seeAll => 'See all';

  @override
  String marketTitle(String market) {
    return '$market market';
  }

  @override
  String get sevenDayTrend => '7-day trend';

  @override
  String get perQuintal => 'per quintal';

  @override
  String get vsLastWeek => 'vs last week';

  @override
  String get takePhoto => 'Take photo';

  @override
  String get navHome => 'Home';

  @override
  String get navOrchard => 'Orchard';

  @override
  String get navAccounts => 'Accounts';

  @override
  String get navAsk => 'Ask';

  @override
  String get taskDone => 'Done';

  @override
  String get markTaskDone => 'Mark task done';

  @override
  String get offlineBanner =>
      'You are offline. Your entries are saved and will sync.';

  @override
  String pendingSync(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count changes waiting to sync',
      one: '1 change waiting to sync',
    );
    return '$_temp0';
  }

  @override
  String get syncFailed => 'Sync failed. Will retry automatically.';

  @override
  String get loginTitle => 'Sign in with your mobile number';

  @override
  String get loginPhoneLabel => 'Mobile number';

  @override
  String get loginSendOtp => 'Send OTP';

  @override
  String loginOtpTitle(String phone) {
    return 'Enter the OTP sent to $phone';
  }

  @override
  String get loginOtpLabel => '6-digit OTP';

  @override
  String get loginVerify => 'Verify';

  @override
  String get loginInvalidPhone => 'Enter a valid 10-digit mobile number';

  @override
  String get loginInvalidOtp => 'The OTP is incorrect or expired';

  @override
  String get loginDemoNotice => 'Demo mode: any 6 digits will work';

  @override
  String get voiceInput => 'Speak';

  @override
  String get galleryTitle => 'Component gallery';

  @override
  String adminTitle(String product) {
    return '$product Admin';
  }

  @override
  String get adminCropTemplates => 'Crop stage templates';

  @override
  String get adminRiskRules => 'Risk rules';

  @override
  String get adminPrompts => 'AI prompt templates';

  @override
  String get adminTranslations => 'Translations';

  @override
  String get adminAiUsage => 'AI usage';

  @override
  String adminComingSoon(int milestone) {
    return 'Editing arrives in Milestone $milestone.';
  }

  @override
  String get demoDataNotice => 'Sample data';
}

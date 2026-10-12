// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get greetingHello => 'नमस्ते';

  @override
  String greetingName(String name) {
    return '$name जी';
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

    return 'अधिकतम $degreesString°';
  }

  @override
  String soilMoisture(int percent) {
    final intl.NumberFormat percentNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String percentString = percentNumberFormat.format(percent);

    return 'मिट्टी की नमी $percentString%';
  }

  @override
  String get stageDays => 'दिन';

  @override
  String nextStage(String stage, int days, String month) {
    final intl.NumberFormat daysNumberFormat = intl.NumberFormat.decimalPattern(
      localeName,
    );
    final String daysString = daysNumberFormat.format(days);

    return 'अगला चरण: $stage · लगभग $daysString दिनों में · तुड़ाई $month';
  }

  @override
  String get todaysTasks => 'आज के काम';

  @override
  String get seeAll => 'सभी देखें';

  @override
  String marketTitle(String market) {
    return '$market मंडी';
  }

  @override
  String get sevenDayTrend => '7 दिन का रुझान';

  @override
  String get perQuintal => 'प्रति क्विंटल';

  @override
  String get vsLastWeek => 'पिछले सप्ताह से';

  @override
  String get takePhoto => 'फोटो लें';

  @override
  String get navHome => 'होम';

  @override
  String get navOrchard => 'बाग';

  @override
  String get navAccounts => 'हिसाब';

  @override
  String get navAsk => 'पूछें';

  @override
  String get taskDone => 'पूरा';

  @override
  String get markTaskDone => 'काम पूरा हुआ';

  @override
  String get offlineBanner =>
      'नेटवर्क नहीं है। आपकी एंट्री सहेजी गई है और बाद में भेजी जाएगी।';

  @override
  String pendingSync(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count बदलाव भेजने बाकी',
      one: '1 बदलाव भेजना बाकी',
    );
    return '$_temp0';
  }

  @override
  String get syncFailed => 'भेजना नहीं हो पाया। अपने आप फिर कोशिश होगी।';

  @override
  String get loginTitle => 'अपने मोबाइल नंबर से शुरू करें';

  @override
  String get loginPhoneLabel => 'मोबाइल नंबर';

  @override
  String get loginSendOtp => 'OTP भेजें';

  @override
  String loginOtpTitle(String phone) {
    return '$phone पर आया OTP डालें';
  }

  @override
  String get loginOtpLabel => '6 अंकों का OTP';

  @override
  String get loginVerify => 'जाँचें';

  @override
  String get loginInvalidPhone => '10 अंकों का सही मोबाइल नंबर डालें';

  @override
  String get loginInvalidOtp => 'OTP गलत है या समय समाप्त हो गया';

  @override
  String get loginDemoNotice => 'डेमो मोड: कोई भी 6 अंक चलेंगे';

  @override
  String get voiceInput => 'बोलें';

  @override
  String get galleryTitle => 'कंपोनेंट गैलरी';

  @override
  String adminTitle(String product) {
    return '$product एडमिन';
  }

  @override
  String get adminCropTemplates => 'फसल चरण साँचे';

  @override
  String get adminRiskRules => 'जोखिम नियम';

  @override
  String get adminPrompts => 'AI प्रॉम्प्ट साँचे';

  @override
  String get adminTranslations => 'अनुवाद';

  @override
  String get adminAiUsage => 'AI उपयोग';

  @override
  String adminComingSoon(int milestone) {
    return 'संपादन माइलस्टोन $milestone में आएगा।';
  }

  @override
  String get demoDataNotice => 'नमूना जानकारी';
}

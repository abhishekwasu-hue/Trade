// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Marathi (`mr`).
class AppLocalizationsMr extends AppLocalizations {
  AppLocalizationsMr([String locale = 'mr']) : super(locale);

  @override
  String get greetingHello => 'नमस्कार';

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

    return 'कमाल $degreesString°';
  }

  @override
  String soilMoisture(int percent) {
    final intl.NumberFormat percentNumberFormat =
        intl.NumberFormat.decimalPattern(localeName);
    final String percentString = percentNumberFormat.format(percent);

    return 'माती ओली $percentString%';
  }

  @override
  String get stageDays => 'दिवस';

  @override
  String nextStage(String stage, int days, String month) {
    final intl.NumberFormat daysNumberFormat = intl.NumberFormat.decimalPattern(
      localeName,
    );
    final String daysString = daysNumberFormat.format(days);

    return 'पुढचा टप्पा: $stage · अंदाजे $daysString दिवसांत · काढणी $month';
  }

  @override
  String get todaysTasks => 'आजची कामं';

  @override
  String get seeAll => 'सगळी पाहा';

  @override
  String marketTitle(String market) {
    return '$market बाजार';
  }

  @override
  String get sevenDayTrend => '७ दिवसांचा कल';

  @override
  String get perQuintal => 'प्रति क्विंटल';

  @override
  String get vsLastWeek => 'गेल्या आठवड्यापेक्षा';

  @override
  String get takePhoto => 'फोटो काढा';

  @override
  String get navHome => 'घर';

  @override
  String get navOrchard => 'बाग';

  @override
  String get navAccounts => 'हिशोब';

  @override
  String get navAsk => 'विचारा';

  @override
  String get taskDone => 'पूर्ण';

  @override
  String get markTaskDone => 'काम पूर्ण झालं';

  @override
  String get offlineBanner =>
      'नेटवर्क नाही. तुमची नोंद जतन झाली आहे, नंतर पाठवली जाईल.';

  @override
  String pendingSync(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count नोंदी पाठवायच्या बाकी',
      one: '१ नोंद पाठवायची बाकी',
    );
    return '$_temp0';
  }

  @override
  String get syncFailed => 'पाठवणं जमलं नाही. आपोआप पुन्हा प्रयत्न होईल.';

  @override
  String get loginTitle => 'तुमच्या मोबाईल नंबरने सुरू करा';

  @override
  String get loginPhoneLabel => 'मोबाईल नंबर';

  @override
  String get loginSendOtp => 'OTP पाठवा';

  @override
  String loginOtpTitle(String phone) {
    return '$phone वर आलेला OTP टाका';
  }

  @override
  String get loginOtpLabel => '६ अंकी OTP';

  @override
  String get loginVerify => 'तपासा';

  @override
  String get loginInvalidPhone => '१० अंकी योग्य मोबाईल नंबर टाका';

  @override
  String get loginInvalidOtp => 'OTP चुकीचा आहे किंवा मुदत संपली';

  @override
  String get loginDemoNotice => 'डेमो मोड: कोणतेही ६ अंक चालतील';

  @override
  String get voiceInput => 'बोला';

  @override
  String get galleryTitle => 'घटक संग्रह';

  @override
  String adminTitle(String product) {
    return '$product प्रशासन';
  }

  @override
  String get adminCropTemplates => 'पीक टप्पा साचे';

  @override
  String get adminRiskRules => 'धोका नियम';

  @override
  String get adminPrompts => 'AI प्रॉम्प्ट साचे';

  @override
  String get adminTranslations => 'भाषांतरे';

  @override
  String get adminAiUsage => 'AI वापर';

  @override
  String adminComingSoon(int milestone) {
    return 'संपादन टप्पा $milestone मध्ये येईल.';
  }

  @override
  String get demoDataNotice => 'नमुना माहिती';
}

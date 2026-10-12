/// Everything the "today's orchard" screen shows. Built in M0 from a demo fixture;
/// later milestones fill it from plots, bahar cycles, weather, risk events and prices.
class HomeSnapshot {
  const HomeSnapshot({
    required this.farmerName,
    required this.weather,
    required this.stage,
    required this.tasks,
    required this.market,
    this.alert,
    this.isDemo = false,
  });

  factory HomeSnapshot.fromJson(
    Map<String, Object?> j, {
    bool isDemo = false,
  }) => HomeSnapshot(
    farmerName: j['farmer_name']! as String,
    weather: WeatherNow.fromJson(_map(j['weather'])),
    stage: StageSummary.fromJson(_map(j['stage'])),
    tasks: [
      for (final t in j['tasks']! as List<Object?>) TaskItem.fromJson(_map(t)),
    ],
    market: MarketQuote.fromJson(_map(j['market'])),
    alert: j['alert'] == null ? null : RiskAlert.fromJson(_map(j['alert'])),
    isDemo: isDemo,
  );

  final String farmerName;
  final WeatherNow weather;
  final StageSummary stage;
  final List<TaskItem> tasks;
  final MarketQuote market;
  final RiskAlert? alert;
  final bool isDemo;

  String get initial =>
      farmerName.isEmpty ? '' : String.fromCharCodes(farmerName.runes.take(1));

  HomeSnapshot withTasks(List<TaskItem> tasks) => HomeSnapshot(
    farmerName: farmerName,
    weather: weather,
    stage: stage,
    tasks: tasks,
    market: market,
    alert: alert,
    isDemo: isDemo,
  );
}

Map<String, Object?> _map(Object? o) =>
    (o! as Map<Object?, Object?>).cast<String, Object?>();

class WeatherNow {
  const WeatherNow({
    required this.place,
    required this.condition,
    required this.tempC,
    required this.maxC,
    required this.soilMoisturePct,
  });

  factory WeatherNow.fromJson(Map<String, Object?> j) => WeatherNow(
    place: j['place']! as String,
    condition: j['condition']! as String,
    tempC: j['temp_c']! as int,
    maxC: j['max_c']! as int,
    soilMoisturePct: j['soil_moisture_pct']! as int,
  );

  final String place;
  final String condition;
  final int tempC;
  final int maxC;
  final int soilMoisturePct;
}

enum StageKind { stress, flowering, fruitSet, fruitGrowth, harvest }

class StageMilestone {
  const StageMilestone({
    required this.kind,
    required this.label,
    required this.position,
  });

  factory StageMilestone.fromJson(Map<String, Object?> j) => StageMilestone(
    kind: StageKind.values.byName(j['kind']! as String),
    label: j['label']! as String,
    position: (j['position']! as num).toDouble(),
  );

  final StageKind kind;
  final String label;
  final double position;
}

class StageSummary {
  const StageSummary({
    required this.tag,
    required this.currentName,
    required this.day,
    required this.milestones,
    required this.currentIndex,
    required this.progress,
    required this.nextName,
    required this.nextInDays,
    required this.harvestMonth,
  });

  factory StageSummary.fromJson(Map<String, Object?> j) => StageSummary(
    tag: j['tag']! as String,
    currentName: j['current_name']! as String,
    day: j['day']! as int,
    milestones: [
      for (final m in j['milestones']! as List<Object?>)
        StageMilestone.fromJson(_map(m)),
    ],
    currentIndex: j['current_index']! as int,
    progress: (j['progress']! as num).toDouble(),
    nextName: j['next_name']! as String,
    nextInDays: j['next_in_days']! as int,
    harvestMonth: DateTime.parse(j['harvest_month']! as String),
  );

  final String tag;
  final String currentName;
  final int day;
  final List<StageMilestone> milestones;
  final int currentIndex;
  final double progress;
  final String nextName;
  final int nextInDays;
  final DateTime harvestMonth;
}

enum TaskKind { irrigation, spray, scouting, other }

class TaskItem {
  const TaskItem({
    required this.id,
    required this.kind,
    required this.title,
    required this.subtitle,
    required this.done,
  });

  factory TaskItem.fromJson(Map<String, Object?> j) => TaskItem(
    id: j['id']! as String,
    kind: TaskKind.values.byName(j['kind']! as String),
    title: j['title']! as String,
    subtitle: j['subtitle']! as String,
    done: j['done']! as bool,
  );

  final String id;
  final TaskKind kind;
  final String title;
  final String subtitle;
  final bool done;

  TaskItem copyWith({bool? done}) => TaskItem(
    id: id,
    kind: kind,
    title: title,
    subtitle: subtitle,
    done: done ?? this.done,
  );
}

class MarketQuote {
  const MarketQuote({
    required this.market,
    required this.pricePerQuintal,
    required this.grade,
    required this.weeklyChangePct,
  });

  factory MarketQuote.fromJson(Map<String, Object?> j) => MarketQuote(
    market: j['market']! as String,
    pricePerQuintal: j['price_per_quintal']! as int,
    grade: j['grade']! as String,
    weeklyChangePct: j['weekly_change_pct']! as int,
  );

  final String market;
  final int pricePerQuintal;
  final String grade;
  final int weeklyChangePct;
}

class RiskAlert {
  const RiskAlert({required this.title, required this.body});

  factory RiskAlert.fromJson(Map<String, Object?> j) =>
      RiskAlert(title: j['title']! as String, body: j['body']! as String);

  final String title;
  final String body;
}

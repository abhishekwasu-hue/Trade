import 'package:flutter/material.dart';

import '../../design_system/alert_banner.dart';
import '../../design_system/cards.dart';
import '../../design_system/glyphs.dart';
import '../../design_system/navigation.dart';
import '../../design_system/price_card.dart';
import '../../design_system/stage_timeline.dart';
import '../../design_system/sync_banner.dart';
import '../../design_system/task_tile.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_theme.dart';

/// Every design-system component on one screen. Reachable only with --dart-define=DEV_GALLERY=true.
class ComponentGalleryScreen extends StatelessWidget {
  const ComponentGalleryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final c = context.bm;
    const gap = SizedBox(height: BmSpace.md);
    return Scaffold(
      appBar: AppBar(title: Text(t.galleryTitle, style: BmType.section)),
      body: ListView(
        padding: const EdgeInsets.all(BmSpace.lg),
        children: [
          const SectionHeader(title: 'Glyphs'),
          Wrap(
            spacing: BmSpace.sm,
            runSpacing: BmSpace.sm,
            children: [
              for (final g in BmGlyph.values)
                Container(
                  width: 56,
                  height: 56,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: g == BmGlyph.warning || g == BmGlyph.sunCloud
                        ? c.brand
                        : c.card,
                    borderRadius: BorderRadius.circular(BmRadius.chip),
                  ),
                  child: GlyphIcon(g, semanticLabel: g.name),
                ),
            ],
          ),
          gap,
          const SectionHeader(title: 'Stage card + timeline'),
          const StageCard(
            tag: 'Mrig bahar · Orchard 1',
            stageName: 'Fruit set',
            dayCount: '68',
            dayUnit: 'days',
            progress: 0.58,
            nextLine: 'Next: fruit growth',
            nodes: [
              StageNodeData(
                label: 'Stress',
                glyph: BmGlyph.drop,
                state: StageState.done,
                position: 0,
              ),
              StageNodeData(
                label: 'Flower',
                glyph: BmGlyph.flower,
                state: StageState.done,
                position: 0.33,
              ),
              StageNodeData(
                label: 'Fruit set',
                glyph: BmGlyph.fruitSet,
                state: StageState.now,
                position: 0.58,
              ),
              StageNodeData(
                label: 'Harvest',
                glyph: BmGlyph.orange,
                state: StageState.upcoming,
                position: 1,
              ),
            ],
          ),
          gap,
          const SectionHeader(title: 'Alert banner'),
          const AlertBanner(
            title: 'Heat wave tomorrow',
            body: 'Irrigate this evening.',
          ),
          gap,
          const SectionHeader(title: 'Task tiles', action: 'See all'),
          TaskTile(
            title: 'Drip 4 h',
            subtitle: '6:00 am',
            glyph: BmGlyph.drop,
            done: true,
            checkLabel: t.markTaskDone,
            onToggle: (_) {},
          ),
          const SizedBox(height: BmSpace.xs),
          TaskTile(
            title: 'Zinc + boron spray',
            subtitle: 'Fruit-set stage',
            glyph: BmGlyph.spray,
            done: false,
            checkLabel: t.markTaskDone,
            onToggle: (_) {},
          ),
          gap,
          const SectionHeader(title: 'Price hero'),
          const PriceHeroCard(
            price: '₹3,200',
            caption: 'per quintal',
            change: '8%',
            changeCaption: 'vs last week',
            rising: true,
          ),
          gap,
          const SectionHeader(title: 'Sync banners'),
          SyncBanner(kind: SyncBannerKind.offline, message: t.offlineBanner),
          const SizedBox(height: BmSpace.xs),
          SyncBanner(kind: SyncBannerKind.pending, message: t.pendingSync(3)),
          const SizedBox(height: BmSpace.xs),
          SyncBanner(kind: SyncBannerKind.failed, message: t.syncFailed),
          gap,
          const SectionHeader(title: 'Buttons'),
          FilledButton(onPressed: () {}, child: Text(t.loginSendOtp)),
          gap,
          Row(
            children: [
              VoiceButton(label: t.voiceInput, onPressed: () {}),
              const SizedBox(width: BmSpace.md),
              CameraButton(label: t.takePhoto, onPressed: () {}),
            ],
          ),
          gap,
          const SectionHeader(title: 'Card'),
          const BmCard(child: Text('BmCard')),
          const SizedBox(height: 120),
        ],
      ),
    );
  }
}

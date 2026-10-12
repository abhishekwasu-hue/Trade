import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'cards.dart';
import 'glyphs.dart';

enum StageState { done, now, upcoming }

class StageNodeData {
  const StageNodeData({
    required this.label,
    required this.glyph,
    required this.state,
    required this.position,
  });

  final String label;
  final BmGlyph glyph;
  final StageState state;

  /// 0..1 along the season track.
  final double position;
}

/// Illustrated bahar timeline: stage glyphs on a progress track (not a text list).
class StageTimeline extends StatelessWidget {
  const StageTimeline({super.key, required this.nodes, required this.progress});

  final List<StageNodeData> nodes;
  final double progress;

  static const _inset = 22.0;
  static const _nodeWidth = 72.0;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    return SizedBox(
      height: 76,
      child: LayoutBuilder(
        builder: (context, box) {
          final track = box.maxWidth - 2 * _inset;
          return Stack(
            clipBehavior: Clip.none,
            children: [
              Positioned(
                left: _inset,
                right: _inset,
                top: 18,
                child: Container(
                  height: 6,
                  decoration: BoxDecoration(
                    color: c.line,
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
              ),
              Positioned(
                left: _inset,
                top: 18,
                child: TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: progress.clamp(0, 1)),
                  duration: MediaQuery.disableAnimationsOf(context)
                      ? Duration.zero
                      : BmMotion.gentle,
                  builder: (context, t, _) => Container(
                    width: track * t,
                    height: 6,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(colors: [c.brandSoft, c.accent]),
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                ),
              ),
              for (final n in nodes)
                Positioned(
                  left: _inset + track * n.position - _nodeWidth / 2,
                  top: 0,
                  width: _nodeWidth,
                  child: _StageNode(n),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _StageNode extends StatelessWidget {
  const _StageNode(this.data);
  final StageNodeData data;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    final isNow = data.state == StageState.now;
    final (border, fill) = switch (data.state) {
      StageState.done => (c.brandSoft, c.doneTint),
      StageState.now => (c.accent, c.nowTint),
      StageState.upcoming => (c.line, c.card),
    };
    final dot = isNow ? 40.0 : 34.0;
    return Semantics(
      label: data.label,
      selected: isNow,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Transform.translate(
            offset: Offset(0, isNow ? -3 : 0),
            child: Container(
              width: dot,
              height: dot,
              padding: const EdgeInsets.all(5),
              decoration: BoxDecoration(
                color: fill,
                shape: BoxShape.circle,
                border: Border.all(color: border, width: 3),
                boxShadow: isNow
                    ? [
                        BoxShadow(
                          color: c.accent.withValues(alpha: 0.15),
                          spreadRadius: 6,
                        ),
                      ]
                    : null,
              ),
              child: GlyphIcon(data.glyph),
            ),
          ),
          SizedBox(height: isNow ? 3 : 6),
          Text(
            data.label,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.visible,
            softWrap: false,
            style: BmType.label.copyWith(
              color: isNow ? c.accent : c.inkMuted,
              fontWeight: isNow ? FontWeight.w700 : FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

/// Bahar stage card: where the orchard is in its cycle, with a big day counter.
class StageCard extends StatelessWidget {
  const StageCard({
    super.key,
    required this.tag,
    required this.stageName,
    required this.dayCount,
    required this.dayUnit,
    required this.nodes,
    required this.progress,
    required this.nextLine,
  });

  final String tag;
  final String stageName;
  final String dayCount;
  final String dayUnit;
  final List<StageNodeData> nodes;
  final double progress;
  final String nextLine;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    return BmCard(
      padding: const EdgeInsets.fromLTRB(
        BmSpace.lg,
        BmSpace.lg,
        BmSpace.lg,
        BmSpace.md,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      tag,
                      style: BmType.label.copyWith(
                        color: c.inkMuted,
                        fontSize: 14,
                      ),
                    ),
                    Text(
                      stageName,
                      style: BmType.cardTitle.copyWith(color: c.brand),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    dayCount,
                    style: BmType.bigNumber.copyWith(color: c.accent),
                  ),
                  Text(
                    dayUnit,
                    style: BmType.label.copyWith(color: c.inkMuted),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: BmSpace.sm),
          StageTimeline(nodes: nodes, progress: progress),
          const SizedBox(height: BmSpace.xxs),
          Text(nextLine, style: BmType.meta.copyWith(color: c.inkMuted)),
        ],
      ),
    );
  }
}

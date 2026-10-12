import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'glyphs.dart';

/// Curved gradient header: greeting, avatar, and today's weather strip.
class WeatherHeader extends StatelessWidget {
  const WeatherHeader({
    super.key,
    required this.greeting,
    required this.name,
    required this.initial,
    required this.temperature,
    required this.place,
    required this.condition,
    required this.maxTemperature,
    required this.soilPill,
    this.trailingAction,
  });

  final String greeting;
  final String name;
  final String initial;
  final String temperature;
  final String place;
  final String condition;
  final String maxTemperature;
  final String soilPill;
  final Widget? trailingAction;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    final onBrand = c.onBrand;
    final topInset = MediaQuery.paddingOf(context).top;
    final meta = BmType.meta.copyWith(
      color: onBrand.withValues(alpha: 0.92),
      height: 1.25,
    );
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: c.headerGradient,
          stops: const [0, 0.7, 1],
        ),
        borderRadius: const BorderRadius.vertical(
          bottom: Radius.circular(BmRadius.header),
        ),
      ),
      child: Padding(
        padding: EdgeInsets.fromLTRB(22, topInset + 20, 22, 78),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        greeting,
                        style: BmType.body.copyWith(
                          color: onBrand.withValues(alpha: 0.85),
                        ),
                      ),
                      Text(name, style: BmType.title.copyWith(color: onBrand)),
                    ],
                  ),
                ),
                ?trailingAction,
                const SizedBox(width: BmSpace.xs),
                Container(
                  width: 46,
                  height: 46,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: c.sun,
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: onBrand.withValues(alpha: 0.5),
                      width: 3,
                    ),
                  ),
                  child: Text(
                    initial,
                    style: BmType.alertTitle.copyWith(
                      fontSize: 19,
                      color: BmColors.light.brand,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: BmSpace.lg),
            Row(
              children: [
                const GlyphIcon(BmGlyph.sunCloud, size: 52),
                const SizedBox(width: BmSpace.sm),
                Text(
                  temperature,
                  style: BmType.heroNumber.copyWith(color: onBrand),
                ),
                const SizedBox(width: BmSpace.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '$place · $condition',
                        style: meta,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(maxTemperature, style: meta, maxLines: 1),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: BmSpace.sm,
                    vertical: BmSpace.xs,
                  ),
                  decoration: BoxDecoration(
                    color: onBrand.withValues(alpha: 0.16),
                    borderRadius: BorderRadius.circular(BmRadius.pill),
                    border: Border.all(color: onBrand.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      GlyphIcon(BmGlyph.drop, size: 16, color: onBrand),
                      const SizedBox(width: BmSpace.xxs),
                      Text(
                        soilPill,
                        style: BmType.label.copyWith(color: onBrand),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

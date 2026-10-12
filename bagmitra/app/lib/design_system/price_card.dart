import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Market price hero: one big number, its unit, and the weekly change chip.
class PriceHeroCard extends StatelessWidget {
  const PriceHeroCard({
    super.key,
    required this.price,
    required this.caption,
    required this.change,
    required this.changeCaption,
    required this.rising,
  });

  final String price;
  final String caption;
  final String change;
  final String changeCaption;
  final bool rising;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    return Container(
      padding: const EdgeInsets.all(BmSpace.md),
      decoration: BoxDecoration(
        color: c.heroCard,
        borderRadius: BorderRadius.circular(BmRadius.card),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(price, style: BmType.money.copyWith(color: c.onBrand)),
                const SizedBox(height: 2),
                Text(
                  caption,
                  style: BmType.label.copyWith(
                    color: c.onBrand.withValues(alpha: 0.85),
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: BmSpace.sm,
              vertical: BmSpace.xs,
            ),
            decoration: BoxDecoration(
              color: c.onBrand.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Column(
              children: [
                Text(
                  '${rising ? '▲' : '▼'} $change',
                  style: BmType.alertTitle.copyWith(fontSize: 19, color: c.sun),
                ),
                Text(
                  changeCaption,
                  style: BmType.label.copyWith(
                    fontSize: 12,
                    color: c.onBrand.withValues(alpha: 0.9),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

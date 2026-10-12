import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'glyphs.dart';

class TaskTile extends StatelessWidget {
  const TaskTile({
    super.key,
    required this.title,
    required this.subtitle,
    required this.glyph,
    required this.done,
    required this.checkLabel,
    this.onToggle,
  });

  final String title;
  final String subtitle;
  final BmGlyph glyph;
  final bool done;
  final String checkLabel;
  final ValueChanged<bool>? onToggle;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    final animate = !MediaQuery.disableAnimationsOf(context);
    return Semantics(
      checked: done,
      label: '$checkLabel: $title',
      child: Material(
        color: c.card,
        borderRadius: BorderRadius.circular(BmRadius.tile),
        shadowColor: c.shadow.withValues(alpha: 0.2),
        elevation: 1,
        child: InkWell(
          borderRadius: BorderRadius.circular(BmRadius.tile),
          onTap: onToggle == null ? null : () => onToggle!(!done),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 64),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(
                children: [
                  AnimatedContainer(
                    duration: animate ? BmMotion.quick : Duration.zero,
                    width: 30,
                    height: 30,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: done ? c.brandStrong : c.card,
                      border: Border.all(
                        color: done ? c.brandStrong : c.brandSoft,
                        width: 2.5,
                      ),
                    ),
                    child: AnimatedScale(
                      duration: animate ? BmMotion.quick : Duration.zero,
                      scale: done ? 1 : 0,
                      child: Icon(
                        Icons.check_rounded,
                        size: 20,
                        color: c.onBrand,
                      ),
                    ),
                  ),
                  const SizedBox(width: BmSpace.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: BmType.bodyStrong.copyWith(
                            color: done ? c.inkMuted : c.ink,
                            decoration: done
                                ? TextDecoration.lineThrough
                                : null,
                          ),
                        ),
                        Text(
                          subtitle,
                          style: BmType.meta.copyWith(
                            color: c.inkMuted,
                            fontSize: 13.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: BmSpace.xs),
                  GlyphIcon(glyph, size: 28),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class BmCard extends StatelessWidget {
  const BmCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(BmSpace.lg),
    this.radius = BmRadius.hero,
    this.elevated = true,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final bool elevated;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.card,
        borderRadius: BorderRadius.circular(radius),
        boxShadow: elevated ? BmElevation.card(c) : BmElevation.tile(c),
      ),
      child: Padding(padding: padding, child: child),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.action,
    this.onAction,
  });

  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    return Row(
      children: [
        Expanded(
          child: Semantics(
            header: true,
            child: Text(title, style: BmType.section.copyWith(color: c.ink)),
          ),
        ),
        if (action != null)
          TextButton(
            onPressed: onAction,
            style: TextButton.styleFrom(
              foregroundColor: c.brandStrong,
              minimumSize: const Size(BmSpace.tapTarget, BmSpace.tapTarget),
              textStyle: BmType.label.copyWith(fontSize: 14),
            ),
            child: Text(action!),
          ),
      ],
    );
  }
}

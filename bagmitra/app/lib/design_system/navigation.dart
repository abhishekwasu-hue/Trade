import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'glyphs.dart';

class BmNavItem {
  const BmNavItem(this.glyph, this.label);
  final BmGlyph glyph;
  final String label;
}

/// Bottom bar with a raised centre camera button (the most important action).
class BmBottomBar extends StatelessWidget {
  const BmBottomBar({
    super.key,
    required this.items,
    required this.selected,
    required this.cameraLabel,
    required this.onCamera,
    this.onSelect,
  }) : assert(items.length == 4, 'two items on each side of the camera');

  final List<BmNavItem> items;
  final int selected;
  final String cameraLabel;
  final VoidCallback onCamera;
  final ValueChanged<int>? onSelect;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    Widget item(int i) {
      final on = i == selected;
      final color = on ? c.brand : c.inkMuted;
      return Expanded(
        child: Semantics(
          selected: on,
          button: true,
          child: InkResponse(
            onTap: onSelect == null ? null : () => onSelect!(i),
            child: SizedBox(
              height: 64,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  GlyphIcon(items[i].glyph, color: color),
                  const SizedBox(height: 3),
                  Text(
                    items[i].label,
                    style: BmType.label.copyWith(color: color, fontSize: 12.5),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    return SizedBox(
      height: 78 + 40 + bottomInset,
      child: Stack(
        alignment: Alignment.bottomCenter,
        clipBehavior: Clip.none,
        children: [
          Container(
            height: 78 + bottomInset,
            padding: EdgeInsets.only(
              bottom: 10 + bottomInset,
              left: 10,
              right: 10,
            ),
            decoration: BoxDecoration(
              color: c.card,
              border: Border(top: BorderSide(color: c.line)),
            ),
            child: Row(
              children: [
                item(0),
                item(1),
                const SizedBox(width: 84),
                item(2),
                item(3),
              ],
            ),
          ),
          Positioned(
            bottom: 10 + bottomInset,
            child: Text(
              cameraLabel,
              style: BmType.label.copyWith(
                color: c.accent,
                fontWeight: FontWeight.w700,
                fontSize: 12.5,
              ),
            ),
          ),
          Positioned(
            bottom: 40 + bottomInset,
            child: CameraButton(label: cameraLabel, onPressed: onCamera),
          ),
        ],
      ),
    );
  }
}

class CameraButton extends StatelessWidget {
  const CameraButton({super.key, required this.label, required this.onPressed});

  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    return Semantics(
      button: true,
      label: label,
      child: GestureDetector(
        onTap: onPressed,
        child: Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [c.accentSoft, c.accent],
            ),
            boxShadow: [
              ...BmElevation.fab(c),
              BoxShadow(color: c.card, spreadRadius: 6),
            ],
          ),
          padding: const EdgeInsets.all(19),
          child: GlyphIcon(BmGlyph.camera, color: c.onBrand),
        ),
      ),
    );
  }
}

/// Prominent microphone affordance for voice entry (spec §4A).
class VoiceButton extends StatelessWidget {
  const VoiceButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.onBrand = false,
  });

  final String label;
  final VoidCallback onPressed;
  final bool onBrand;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    return Tooltip(
      message: label,
      child: Semantics(
        button: true,
        label: label,
        child: InkResponse(
          onTap: onPressed,
          radius: 28,
          child: Container(
            width: BmSpace.tapTarget,
            height: BmSpace.tapTarget,
            padding: const EdgeInsets.all(11),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: onBrand ? c.onBrand.withValues(alpha: 0.16) : c.nowTint,
            ),
            child: GlyphIcon(
              BmGlyph.mic,
              color: onBrand ? c.onBrand : c.accent,
            ),
          ),
        ),
      ),
    );
  }
}

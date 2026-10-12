import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// The app's own flat illustration set, painted from theme colours so it tints with
/// light/dark mode and costs no asset bytes. Extend by adding a kind + painter branch.
enum BmGlyph {
  drop,
  flower,
  fruitSet,
  orange,
  sunCloud,
  spray,
  camera,
  warning,
  mic,
  home,
  orchard,
  ledger,
}

class GlyphIcon extends StatelessWidget {
  const GlyphIcon(
    this.glyph, {
    super.key,
    this.size = 24,
    this.color,
    this.semanticLabel,
  });

  final BmGlyph glyph;
  final double size;

  /// Overrides the glyph's own colours with a single tint (used for nav and on-brand icons).
  final Color? color;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final painted = CustomPaint(
      size: Size.square(size),
      painter: _GlyphPainter(glyph, context.bm, color),
    );
    return semanticLabel == null
        ? ExcludeSemantics(child: painted)
        : Semantics(label: semanticLabel, image: true, child: painted);
  }
}

class _GlyphPainter extends CustomPainter {
  _GlyphPainter(this.glyph, this.c, this.tint);

  final BmGlyph glyph;
  final BmColors c;
  final Color? tint;

  Paint _fill(Color color) => Paint()..color = tint ?? color;

  Paint _stroke(Color color, double w) => Paint()
    ..color = tint ?? color
    ..style = PaintingStyle.stroke
    ..strokeWidth = w
    ..strokeCap = StrokeCap.round
    ..strokeJoin = StrokeJoin.round;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 24, size.height / 24);
    switch (glyph) {
      case BmGlyph.drop:
        final p = Path()
          ..moveTo(12, 2.5)
          ..cubicTo(12, 2.5, 5, 10.5, 5, 14.5)
          ..arcToPoint(
            const Offset(19, 14.5),
            radius: const Radius.circular(7),
            clockwise: false,
          )
          ..cubicTo(19, 10.5, 12, 2.5, 12, 2.5)
          ..close();
        canvas.drawPath(p, _fill(c.sky));
        canvas.drawPath(p, _stroke(c.brandStrong, 1.6));
        canvas.drawArc(
          const Rect.fromLTWH(8.5, 11.5, 6, 6),
          math.pi * 0.6,
          math.pi * 0.6,
          false,
          _stroke(c.card, 1.6),
        );
      case BmGlyph.flower:
        for (var i = 0; i < 5; i++) {
          final a = i * 2 * math.pi / 5 - math.pi / 2;
          canvas.drawCircle(
            Offset(12 + 5 * math.cos(a), 12 + 5 * math.sin(a)),
            4,
            _fill(c.card),
          );
          canvas.drawCircle(
            Offset(12 + 5 * math.cos(a), 12 + 5 * math.sin(a)),
            4,
            _stroke(c.brandSoft, 1.2),
          );
        }
        canvas.drawCircle(const Offset(12, 12), 3, _fill(c.sun));
      case BmGlyph.fruitSet:
        canvas.drawPath(
          Path()
            ..moveTo(12, 4)
            ..quadraticBezierTo(17, 2, 19, 6)
            ..quadraticBezierTo(14, 7.5, 12, 4),
          _fill(c.brandStrong),
        );
        canvas.drawCircle(const Offset(9, 14), 4.2, _fill(c.brandSoft));
        canvas.drawCircle(const Offset(15.5, 15.5), 3.4, _fill(c.brandStrong));
        canvas.drawLine(
          const Offset(12, 4),
          const Offset(10, 10),
          _stroke(c.soil, 1.4),
        );
      case BmGlyph.orange:
        canvas.drawCircle(const Offset(12, 13.5), 8, _fill(c.accent));
        canvas.drawCircle(const Offset(9.5, 11), 2, _fill(c.accentSoft));
        canvas.drawPath(
          Path()
            ..moveTo(12, 5.5)
            ..quadraticBezierTo(16, 1.5, 19.5, 4)
            ..quadraticBezierTo(15.5, 7, 12, 5.5),
          _fill(c.brandStrong),
        );
      case BmGlyph.sunCloud:
        canvas.drawCircle(const Offset(11, 10), 4.6, _fill(c.sun));
        for (var i = 0; i < 8; i++) {
          final a = i * math.pi / 4;
          canvas.drawLine(
            Offset(11 + 6.6 * math.cos(a), 10 + 6.6 * math.sin(a)),
            Offset(11 + 8.4 * math.cos(a), 10 + 8.4 * math.sin(a)),
            _stroke(c.sun, 1.4),
          );
        }
        final cloud = Path()
          ..addOval(const Rect.fromLTWH(7, 14, 7, 7))
          ..addOval(const Rect.fromLTWH(11, 11.5, 8, 8))
          ..addRRect(
            RRect.fromLTRBR(8.5, 16.5, 21.5, 21, const Radius.circular(2.4)),
          )
          ..addOval(const Rect.fromLTWH(16, 15, 6, 6));
        canvas.drawPath(cloud, _fill(c.onBrand));
      case BmGlyph.spray:
        canvas.drawRRect(
          RRect.fromLTRBR(6, 9, 15, 21.5, const Radius.circular(2.5)),
          _fill(c.brandSoft),
        );
        canvas.drawRect(
          const Rect.fromLTWH(8.5, 5.5, 4, 3.5),
          _fill(c.brandStrong),
        );
        canvas.drawLine(
          const Offset(12.5, 6.5),
          const Offset(16, 6.5),
          _stroke(c.brandStrong, 1.6),
        );
        for (final o in const [Offset(19, 4), Offset(20, 7), Offset(19, 10)]) {
          canvas.drawCircle(o, 1, _fill(c.sky));
        }
        canvas.drawLine(
          const Offset(8, 14),
          const Offset(13, 14),
          _stroke(c.card, 1.4),
        );
      case BmGlyph.camera:
        final body = Path()
          ..moveTo(4, 8)
          ..lineTo(7, 8)
          ..lineTo(9, 5)
          ..lineTo(15, 5)
          ..lineTo(17, 8)
          ..lineTo(20, 8)
          ..lineTo(20, 19)
          ..lineTo(4, 19)
          ..close();
        canvas.drawPath(body, _stroke(c.brandStrong, 2));
        canvas.drawCircle(const Offset(12, 13), 3.5, _stroke(c.accent, 2));
      case BmGlyph.warning:
        final tri = Path()
          ..moveTo(12, 3)
          ..lineTo(22, 21)
          ..lineTo(2, 21)
          ..close();
        canvas.drawPath(tri, _stroke(c.onBrand, 2.4));
        canvas.drawLine(
          const Offset(12, 10),
          const Offset(12, 15),
          _stroke(c.onBrand, 2.4),
        );
        canvas.drawLine(
          const Offset(12, 18.5),
          const Offset(12, 19),
          _stroke(c.onBrand, 2.4),
        );
      case BmGlyph.mic:
        canvas.drawRRect(
          RRect.fromLTRBR(8, 2, 16, 15, const Radius.circular(4)),
          _stroke(c.inkMuted, 2.2),
        );
        canvas.drawArc(
          const Rect.fromLTWH(6, 5, 12, 12),
          0,
          math.pi,
          false,
          _stroke(c.inkMuted, 2.2),
        );
        canvas.drawLine(
          const Offset(12, 17),
          const Offset(12, 21),
          _stroke(c.inkMuted, 2.2),
        );
      case BmGlyph.home:
        final p = Path()
          ..moveTo(3, 11)
          ..lineTo(12, 4)
          ..lineTo(21, 11)
          ..lineTo(21, 20)
          ..lineTo(3, 20)
          ..close();
        canvas.drawPath(p, _stroke(c.inkMuted, 2.2));
      case BmGlyph.orchard:
        final p = Path()
          ..moveTo(12, 21)
          ..cubicTo(7, 17, 4, 14, 4, 10)
          ..arcToPoint(const Offset(20, 10), radius: const Radius.circular(8))
          ..cubicTo(20, 14, 17, 17, 12, 21)
          ..close();
        canvas.drawPath(p, _stroke(c.inkMuted, 2.2));
      case BmGlyph.ledger:
        final s = _stroke(c.inkMuted, 2.2);
        canvas.drawLine(const Offset(4, 19), const Offset(20, 19), s);
        canvas.drawLine(const Offset(6, 16), const Offset(6, 9), s);
        canvas.drawLine(const Offset(11, 16), const Offset(11, 5), s);
        canvas.drawLine(const Offset(16, 16), const Offset(16, 9), s);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_GlyphPainter old) =>
      old.glyph != glyph || old.c != c || old.tint != tint;
}

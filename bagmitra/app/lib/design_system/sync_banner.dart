import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

enum SyncBannerKind { offline, pending, failed }

/// Compact status strip shown only when something is not synced.
class SyncBanner extends StatelessWidget {
  const SyncBanner({super.key, required this.kind, required this.message});

  final SyncBannerKind kind;
  final String message;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    final (bg, fg, icon) = switch (kind) {
      SyncBannerKind.offline => (c.ink, c.background, Icons.cloud_off_rounded),
      SyncBannerKind.pending => (
        c.nowTint,
        c.warnTitle,
        Icons.cloud_upload_rounded,
      ),
      SyncBannerKind.failed => (
        c.danger,
        c.onBrand,
        Icons.sync_problem_rounded,
      ),
    };
    return Semantics(
      liveRegion: true,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(
          horizontal: BmSpace.md,
          vertical: 10,
        ),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(BmRadius.chip),
        ),
        child: Row(
          children: [
            Icon(icon, size: 20, color: fg),
            const SizedBox(width: BmSpace.xs),
            Expanded(
              child: Text(
                message,
                style: BmType.label.copyWith(color: fg, fontSize: 14),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

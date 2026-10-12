import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../design_system/glyphs.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_theme.dart';
import '../domain/auth.dart';

class _AuthScaffold extends StatelessWidget {
  const _AuthScaffold({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final c = context.bm;
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(BmSpace.xl),
          children: [
            const SizedBox(height: BmSpace.xxl),
            Center(
              child: Container(
                width: 96,
                height: 96,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(colors: c.headerGradient),
                ),
                child: const GlyphIcon(BmGlyph.orange),
              ),
            ),
            const SizedBox(height: BmSpace.xl),
            Text(
              title,
              style: BmType.title.copyWith(color: c.brand),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: BmSpace.xl),
            ...children,
          ],
        ),
      ),
    );
  }
}

class PhoneLoginScreen extends ConsumerStatefulWidget {
  const PhoneLoginScreen({super.key});

  @override
  ConsumerState<PhoneLoginScreen> createState() => _PhoneLoginScreenState();
}

class _PhoneLoginScreenState extends ConsumerState<PhoneLoginScreen> {
  final _phone = TextEditingController();
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _phone.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final t = AppLocalizations.of(context);
    final e164 = normalizeIndianMobile(_phone.text);
    if (e164 == null) {
      setState(() => _error = t.loginInvalidPhone);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(authRepositoryProvider).sendOtp(e164);
      if (mounted) {
        await context.push(
          Uri(path: Routes.otp, queryParameters: {'phone': e164}).toString(),
        );
      }
    } on AuthFailure {
      setState(() => _error = t.loginInvalidPhone);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final demo = ref.watch(appConfigProvider).demoMode;
    return _AuthScaffold(
      title: t.loginTitle,
      children: [
        TextField(
          key: const Key('phone'),
          controller: _phone,
          keyboardType: TextInputType.phone,
          autofillHints: const [AutofillHints.telephoneNumber],
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp(r'[0-9+ ]')),
          ],
          style: BmType.bigNumber.copyWith(fontSize: 26, letterSpacing: 1.5),
          decoration: InputDecoration(
            labelText: t.loginPhoneLabel,
            prefixText: '+91  ',
            errorText: _error,
          ),
          onSubmitted: (_) => _submit(),
        ),
        const SizedBox(height: BmSpace.lg),
        FilledButton(
          onPressed: _busy ? null : _submit,
          child: Text(t.loginSendOtp),
        ),
        if (demo) ...[
          const SizedBox(height: BmSpace.md),
          Text(
            t.loginDemoNotice,
            textAlign: TextAlign.center,
            style: BmType.meta,
          ),
        ],
      ],
    );
  }
}

class OtpScreen extends ConsumerStatefulWidget {
  const OtpScreen({super.key, required this.phone});

  final String phone;

  @override
  ConsumerState<OtpScreen> createState() => _OtpScreenState();
}

class _OtpScreenState extends ConsumerState<OtpScreen> {
  final _code = TextEditingController();
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _verify() async {
    final t = AppLocalizations.of(context);
    if (!isValidOtp(_code.text)) {
      setState(() => _error = t.loginInvalidOtp);
      return;
    }
    setState(() => _busy = true);
    try {
      await ref
          .read(authRepositoryProvider)
          .verifyOtp(widget.phone, _code.text);
      // The router redirects home once the session stream reports the sign-in.
    } on AuthFailure {
      if (mounted) setState(() => _error = t.loginInvalidOtp);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return _AuthScaffold(
      title: t.loginOtpTitle(widget.phone),
      children: [
        TextField(
          key: const Key('otp'),
          controller: _code,
          keyboardType: TextInputType.number,
          autofillHints: const [AutofillHints.oneTimeCode],
          maxLength: 6,
          textAlign: TextAlign.center,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          style: BmType.bigNumber.copyWith(fontSize: 30, letterSpacing: 10),
          decoration: InputDecoration(
            labelText: t.loginOtpLabel,
            errorText: _error,
            counterText: '',
          ),
          onSubmitted: (_) => _verify(),
        ),
        const SizedBox(height: BmSpace.lg),
        FilledButton(
          onPressed: _busy ? null : _verify,
          child: Text(t.loginVerify),
        ),
      ],
    );
  }
}

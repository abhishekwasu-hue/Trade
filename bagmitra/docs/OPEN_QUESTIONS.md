# Open questions

Each item has a provisional default that the work proceeds on. Owner: answer inline or in a PR.

| # | Question | Provisional default |
|---|---|---|
| Q1 | The spec asks for a new `bagmitra` repo; this session could only write to `trade`. Create a separate repo? | Built in `bagmitra/` (self-contained). Split with `git subtree split` when the owner creates the repo (ADR 0001). |
| Q2 | M0 is one PR well over the 400-line rule (foundation spans API, app, CI, docs). | Accept for M0 only; from M1 on, one feature per PR ≤ 400 production lines. |
| Q3 | Supabase project, JWT secret and anon key are not available yet. | API verifies HS256 tokens from env; app runs in **demo mode** (local OTP, no backend) when `SUPABASE_URL` is unset. |
| Q4 | Android emulator demo (DoD) cannot run in this cloud container (no KVM/Android SDK). | Demo executed via widget/golden tests at phone size plus a web build; APK built in CI. Emulator run to be recorded by the first session that has one. |
| Q5 | STT/TTS provider: Bhashini, Sarvam or Google? | Decide in M3; keep adapter interface. Mic buttons exist in the design system but are not wired on screens until STT works (no dead buttons). |
| Q6 | Default app language when the device language is unsupported. | English (spec: fall back to English). Onboarding (M1) asks the grower to pick their language explicitly, Marathi first. |
| Q7 | Home must fit without scrolling on a 5.5" screen; at 393×851 dp the market card is just below the fold. | Tighten header/stage-card heights in the M1 design-system pass and add a golden that asserts it. |
| Q8 | Demo "today's orchard" content (tasks, alert, price) is sample data. | Shipped as a language-keyed asset with a visible "Sample data" chip; replaced by real data as M1–M5 land. Not used by any logic. |

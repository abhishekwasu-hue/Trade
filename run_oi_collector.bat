@echo off
REM ============================================================
REM run_oi_collector.bat
REM ------------------------------------------------------------
REM Windows Task Scheduler साठी सोपं wrapper — SUPABASE_DB_URL आणि Upstox Token इथेच
REM (खाली) एकदा भरा, मग हीच .bat file Task Scheduler मध्ये "दर १० मिनिटांनी चालवा" म्हणून द्या.
REM
REM वापरणे:
REM   १. खालच्या SET ओळींमध्ये तुमचा खरा Supabase Connection String आणि Upstox Token भरा.
REM   २. Windows Search मध्ये "Task Scheduler" शोधा -> उघडा.
REM   ३. "Create Basic Task" -> नाव द्या (उदा. "OI Snapshot Collector").
REM   ४. Trigger: "Daily", Recur every 1 day -> Advanced Settings मध्ये "Repeat task every: 10 minutes",
REM      "for a duration of: 8 hours" (बाजार तासांसाठी पुरेसं).
REM   ५. Action: "Start a program" -> Program/script मध्ये या .bat file चा पूर्ण मार्ग (path) द्या
REM      (उदा. C:\amw_a1_trading_system\run_oi_collector.bat).
REM   ६. Finish. दर १० मिनिटांनी (बाजार तासात) आपोआप चालेल — browser बंद असला तरीही.
REM ============================================================

SET SUPABASE_DB_URL=postgresql://postgres:YOUR_PASSWORD_HERE@db.xxxxx.supabase.co:5432/postgres
SET UPSTOX_TOKEN=YOUR_UPSTOX_ACCESS_TOKEN_HERE

cd /d "%~dp0"
python oi_snapshot_collector.py --token "%UPSTOX_TOKEN%" >> data\oi_collector_log.txt 2>&1

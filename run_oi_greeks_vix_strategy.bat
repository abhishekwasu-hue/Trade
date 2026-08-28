@echo off
REM ============================================================
REM run_oi_greeks_vix_strategy.bat
REM ------------------------------------------------------------
REM Windows Task Scheduler साठी wrapper — तुमच्या हस्तक्षेपाशिवाय (without your interest) पूर्णपणे
REM स्वयंचलित चालण्यासाठी. खाली एकदा भरा, मग Task Scheduler मध्ये "दर १० मिनिटांनी चालवा" म्हणून द्या.
REM
REM ⚠️⚠️⚠️ अत्यंत महत्त्वाचं — MODE बद्दल ⚠️⚠️⚠️
REM   PAPER = काल्पनिक पैसे, खरा व्यवहार होत नाही (डीफॉल्ट, सुरक्षित)
REM   LIVE  = खरे पैसे, खरा व्यवहार होतो — किमान २-३ आठवडे PAPER मध्ये चालवून, निकाल समाधानकारक
REM           असल्याशिवाय LIVE करू नका. LIVE केल्यावर तुमचं यावर कुठलंही manual लक्ष राहणार नाही
REM           (तुम्हीच "without my interest" म्हणालात) — म्हणजे चूक झाल्यास ती लगेच कळणारही नाही,
REM           फक्त Telegram सूचना (सेटअप केली असेल तर) किंवा Health Check वरूनच कळेल.
REM
REM वापरणे:
REM   १. खालच्या SET ओळींमध्ये तुमचा खरा Upstox Token भरा, आणि MODE ठरवा (PAPER/LIVE).
REM   २. Windows Search -> "Task Scheduler" -> "Create Basic Task".
REM   ३. Trigger: Daily -> Advanced -> "Repeat task every: 10 minutes", "for a duration of: 8 hours".
REM   ४. Action: "Start a program" -> या .bat file चा पूर्ण मार्ग.
REM   ५. Finish — आता दर १० मिनिटांनी (बाजार तासात) आपोआप चालेल.
REM ============================================================

SET UPSTOX_TOKEN=YOUR_UPSTOX_ACCESS_TOKEN_HERE
SET TRADING_MODE=PAPER

REM 🎓 Cloud DB (OI history browser बंद असतानाही उपलब्ध व्हावी म्हणून) वापरत असाल तर इथेही भरा,
REM नसेल तर ही ओळ तशीच ठेवा (रिकामी असल्यास आपोआप local SQLite कडे वळेल):
SET SUPABASE_DB_URL=

cd /d "%~dp0"
python oi_greeks_vix_strategy.py --token "%UPSTOX_TOKEN%" --mode %TRADING_MODE% >> data\oi_greeks_vix_log.txt 2>&1

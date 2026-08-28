@echo off
REM ============================================================
REM run_eod_market_report.bat
REM ------------------------------------------------------------
REM Windows Task Scheduler साठी wrapper — दररोज दुपारी ४ वाजता (बाजार बंद झाल्यानंतर) एकदाच
REM स्वयंचलितपणे EOD Market Report तयार करण्यासाठी (PDF + Telegram).
REM
REM वापरणे:
REM   १. खालच्या SET ओळीत तुमचा खरा Upstox Token भरा.
REM   २. Windows Search -> "Task Scheduler" -> "Create Basic Task".
REM   ३. Trigger: "Daily" -> वेळ: 16:00 (दुपारी ४ वाजता) -> "Recur every: 1 day" (एकदाच, दर १० मिनिटांनी
REM      चालणाऱ्या इतर scripts सारखं "Repeat task" इथे लावू नका — हे दिवसातून एकदाच चालायला हवं).
REM   ४. Action: "Start a program" -> या .bat file चा पूर्ण मार्ग.
REM   ५. Finish — आता दररोज दुपारी ४ वाजता आपोआप चालेल.
REM ============================================================

SET UPSTOX_TOKEN=YOUR_UPSTOX_ACCESS_TOKEN_HERE
SET TRADING_MODE=PAPER

REM 🎓 Telegram सूचना हव्या असतील तर data\notification_config.json मध्ये आधीच सेटअप केलेलं असू द्या
REM (notifications.py — credentials नसतील तर फक्त PDF तयार होईल, Telegram शांतपणे वगळलं जाईल).

cd /d "%~dp0"
python eod_market_report.py --token "%UPSTOX_TOKEN%" --mode %TRADING_MODE% >> data\eod_market_report_log.txt 2>&1

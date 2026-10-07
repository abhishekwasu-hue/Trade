"""vision — Vision + Human-Eye (PAPER signals ची chart तपासणी). V0 = shadow / notify: फक्त नोंद आणि Telegram माहिती, trading मध्ये बदल नाही.

🎓 अटळ नियम (docs/VISION_HUMAN_EYE.md):
  • Vision कधीच order देत नाही, size वाढवत नाही (reduce-only). V0 मध्ये तर कुठलाच परिणाम नाही — hook फक्त queue मध्ये row टाकतो.
  • Exits पूर्ण automatic — exit मार्गात vision नाही (या package ला trading_engine / trade_monitor मधून import नाही).
  • किंमती image वरून कधीच नाहीत — vision फक्त enum मध्ये मत देतो.
  • फक्त PAPER; LIVE bot ⇒ vision off (कुठलाही mode लागू होत नाही).
  • Chart signal च्या क्षणापर्यंतच (no-lookahead).
"""

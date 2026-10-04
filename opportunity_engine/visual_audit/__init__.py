"""opportunity_engine/visual_audit — Visual Level Reading आणि Dual-Eye Consensus (spec §17, PR-V).

render (chart PNG) → auditor (vision model; overlay आणि स्वतंत्र वाचन) → consensus (गणित + नजर) → store (Supabase) → evaluate (सिद्ध झाल्याशिवाय score मध्ये नाही).
Live intraday loop मध्ये API call नाही — EOD/pre-market run चे निकाल दिवसभर वापरले जातात (दिवस D चे consensus फक्त D−1 पर्यंतच्या chart वरून).
"""

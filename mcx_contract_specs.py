"""
mcx_contract_specs.py
------------------------------
🎓 वापरकर्त्याने सापडवलेली bug ("Mcx gold margin and pnl is wrong compare from fyers pnl calculators" ->
"Gold, lot size 1 but in kg asto, silver 30 kg") — bot चा P&L आतापर्यंत नेहमी `भावातील फरक × lots × lot_size`
असा काढला जायचा (lot_size = Upstox चा). हे फक्त तेव्हाच बरोबर असतं जेव्हा किंमत आणि lot_size एकाच एककात
असतात: CRUDEOIL (बॅरल/बॅरल), NATURALGAS (mmBtu), SILVER (kg/kg, lot 30), COPPER (kg/kg) — सगळ्यांना गुणक 1.
GOLD मात्र वेगळं: किंमत प्रति **10 ग्रॅम** सांगितली जाते, पण lot **1 kg** (=100 × 10g) चा — Upstox lot_size
= 1 (kg). म्हणजे ₹1 भाव-हालचाल = 1 lot वर ₹100 P&L, पण bot ₹1 धरायचा (100 पट कमी P&L/SL/Target/charges/
Contract Value). इथला गुणक फक्त P&L/SL/margin-अंदाज/charges च्या गणितात लागतो — broker ला जाणारी order
quantity (lots × Upstox lot_size) कधीच बदलत नाही.
"""

# price-unit गुणक = (एका lot मधले भाव-एकक) — फक्त जिथे १ पेक्षा वेगळा. नवीन commodity (उदा. GOLDM: lot 100g,
# भाव प्रति 10g => 10) जोडताना इथेच नोंद.
MCX_PRICE_MULTIPLIER = {"GOLD": 100}


def get_price_multiplier(symbol):
    """MCX commodity साठी P&L-गुणक (डीफॉल्ट 1)."""
    return MCX_PRICE_MULTIPLIER.get(str(symbol or "").upper(), 1)

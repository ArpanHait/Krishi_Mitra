import json
import logging
import re
from collections.abc import AsyncIterable

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    ModelSettings,
    RunContext,
    cli,
    function_tool,
    room_io,
    tokenize,
)
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import db
import outbound_dialer
import tools

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Farm & Field Track: Agricultural Voice Assistant for Indian Farmers (Krishi Mitra)
SYSTEM_PROMPT = """You are Krishi Mitra (🌾), an agricultural voice advisor speaking with a farmer.

### 1. STRICT LANGUAGE MATCHING DIRECTIVE (HIGHEST PRIORITY OVERRIDE)
- YOU MUST MATCH AND RESPOND IN THE EXACT SAME LANGUAGE AS THE USER'S LATEST INPUT!
- IF THE USER SPEAKS TO YOU IN ENGLISH (e.g., "What fertilizer should I use for wheat in the Rabi season?", "Hello", "Do you know my name?"):
  * YOU MUST RESPOND 100% IN PURE ENGLISH for BOTH "tts_text" AND "display_text"!
  * ABSOLUTELY ZERO HINDI WORDS AND ZERO DEVANAGARI CHARACTERS WHEN THE USER SPEAKS IN ENGLISH!
- IF THE USER SPEAKS TO YOU IN BENGALI:
  * YOU MUST RESPOND 100% IN PURE BENGALI SCRIPT (বাংলা অক্ষর) for BOTH "tts_text" AND "display_text"!
- IF THE USER SPEAKS TO YOU IN HINDI OR HINGLISH:
  * YOU MUST RESPOND 100% IN PURE DEVANAGARI HINDI (देवनागरी हिंदी) for BOTH "tts_text" AND "display_text"!

### 2. IDENTITY & TONAL STYLE
- Role: Helpful local agricultural expert speaking with a farmer over a phone call.
- Tone: Empathetic, respectful, practical, and conversational. Use warm, natural human connectors in the user's spoken language.
- Keep answers clear, detailed, and informative (around 3 to 4 natural sentences per turn) so the farmer gets actionable guidance, while avoiding overwhelming textbook jargon or excessively long lists.

### 3. GREETING & REPETITION RULE (STRICT)
- Greet the user warmly at the beginning of the conversation turn (e.g., "Namaste! / नमस्ते! / Hello!").
- DO NOT repeat greetings on subsequent turns during an ongoing conversation!
- On turn 2 onwards, jump straight into answering the user's question directly and conversationally.

### 4. EXPERTISE SCOPE — WHAT YOU CAN HELP WITH
You are an expert in the following agricultural and allied topics. Answer confidently within this scope:
- Crop Selection & Planning: Which crops to grow in which season, crop rotation, intercropping, mixed farming.
- Soil Health & Preparation: Soil testing, pH management, organic matter, composting, vermicompost, land preparation techniques.
- Pest & Disease Management: Identification of common pests/diseases, organic remedies (neem oil, trichoderma), IPM (Integrated Pest Management), when to use chemical pesticides (with safety warnings).
- Irrigation & Water Management: Drip irrigation, sprinkler systems, rain-fed farming, water conservation, mulching techniques.
- Fertilizers & Nutrients: NPK ratios, urea, DAP, organic fertilizers, micronutrient deficiency symptoms, foliar spray guidance.
- Seeds & Varieties: High-yield varieties (HYV), hybrid vs. desi seeds, seed treatment, recommended varieties by region.
- Government Schemes for Farmers: PM-Kisan, PMFBY, Kisan Credit Card, Soil Health Card, eNAM, subsidies.
- Post-Harvest & Storage: Drying, grading, storage techniques, preventing storage losses, cold chain basics.
- Organic Farming: Certification process, organic inputs, bio-pesticides, natural farming (Zero Budget Natural Farming / ZBNF).
- Animal Husbandry (Basic): Cattle care, poultry basics, dairy farming tips, fodder crops, veterinary first-aid advice.
- Weather & Climate: Monsoon planning, drought management, frost protection, climate-resilient crops.
- Farm Equipment: Basic guidance on tractors, tillers, sprayers, harvesting equipment, and maintenance tips.
- Mandi Prices & Market Rates: Real-time wholesale prices for paddy, potato, jute, mustard, wheat, rice, etc.

### 5. INDIA-SPECIFIC FARMING KNOWLEDGE
Always consider the Indian agricultural context when answering:

CROPPING SEASONS:
- Kharif (June-October, monsoon): Rice/Paddy (dhaan), Maize (makka), Cotton (kapas), Soybean, Groundnut (moongfali), Jute (paat), Bajra, Jowar, Tur/Arhar dal, Sugarcane (ganna).
- Rabi (October-March, winter): Wheat (gehun), Mustard (sarson), Gram/Chana, Peas (matar), Barley (jau), Linseed (alsi), Sunflower.
- Zaid (March-June, summer): Watermelon (tarbooz), Muskmelon (kharbooja), Cucumber (kheera), Moong dal, Vegetables (bhindi, lauki, tori, karela).

REGIONAL CROP PATTERNS:
- West Bengal / Eastern India: Paddy (aman, boro, aus), Jute (paat), Potato (aloo), Mustard, Vegetables, Tea.
- Punjab / Haryana / Western UP: Wheat, Paddy, Sugarcane, Cotton, Basmati Rice.
- Maharashtra / Gujarat: Cotton, Soybean, Sugarcane, Groundnut, Onion, Grapes.
- Karnataka / Tamil Nadu / Andhra Pradesh: Paddy, Ragi, Coconut, Arecanut, Turmeric, Sugarcane, Banana.
- Madhya Pradesh / Rajasthan: Wheat, Soybean, Gram, Mustard, Bajra, Maize.
- Assam / North-East: Tea, Paddy, Bamboo, Arecanut, Orange, Pineapple.

SOIL TYPES:
- Alluvial soil (Indo-Gangetic plains): Best for wheat, rice, sugarcane.
- Black/Regur soil (Deccan Plateau): Best for cotton, soybean, groundnut.
- Red & Laterite soil (Eastern/Southern India): Suitable for millets, groundnut, potato.
- Sandy/Desert soil (Rajasthan): Bajra, jowar, guar, moth dal.

### 6. GOVERNMENT SCHEMES REFERENCE
When a farmer asks about government schemes, provide accurate names and direct them to official sources:
- PM-Kisan Samman Nidhi: Rs 6,000/year in 3 installments. Portal: pmkisan.gov.in, Helpline: 155261.
- PMFBY (Pradhan Mantri Fasal Bima Yojana): Crop insurance. Portal: pmfby.gov.in.
- Kisan Credit Card (KCC): Low-interest farm loans up to Rs 3 lakh at 4% interest (with subsidy). Apply at any bank branch.
- Soil Health Card Scheme: Free soil testing. Portal: soilhealth.dac.gov.in.
- eNAM (National Agriculture Market): Online mandi trading. Portal: enam.gov.in.
- PM Kisan Maandhan Yojana: Pension scheme for small/marginal farmers (Rs 3,000/month after age 60).
- Sub-Mission on Agricultural Mechanization (SMAM): Subsidies on farm equipment (up to 50-80%).
- ALWAYS recommend the farmer verify eligibility and current status at their nearest Common Service Centre (CSC), bank branch, or Krishi Vigyan Kendra (KVK).

### 7. CONVERSATION FLOW & ANSWER STRUCTURE
CLARIFYING QUESTIONS:
- If the farmer's query is vague or region-dependent, ask 1-2 short clarifying questions BEFORE answering (e.g., "Aap kaunse state mein hain?", "Kaunsi fasal lagai hai?", "Mitti ki jaanch karwai hai?").
- Do NOT ask too many questions at once. Ask only what is essential.

ANSWER STRUCTURE (follow this pattern for farming answers):
1. Acknowledge: Show you understood the farmer's problem (e.g., "Haan, dhaan mein patte peele hona ek aam samasya hai.").
2. Cause/Reason: Briefly explain the likely cause (e.g., "Yeh nitrogen ki kami ya paani ka adhik hona ho sakta hai.").
3. Solution/Action: Give a clear, practical, step-by-step solution the farmer can act on immediately.
4. Next Step: End with ONE clear next step (e.g., "Agar 1 hafte mein sudhar na ho, toh apne nazdeeki KVK se mitti ki jaanch karwaein.").

### 8. BORDERLINE TOPIC RULES
These topics ARE within your scope (answer them):
- Farm loans via Kisan Credit Card (KCC) → Guide on application process, interest rates, bank eligibility.
- Cattle, poultry, goat, fishery (basic animal husbandry) → Provide practical tips.
- Farm equipment (tractor, pump, sprayer) → Basic guidance and maintenance tips.
- Weather impact on crops → Monsoon, drought, frost advice.
- Selling crops at mandi / eNAM → Basic guidance on mandi process.

These topics are OFF-TOPIC (refuse politely and redirect):
- Personal bank accounts, OTPs, UPI, net banking → Redirect to bank customer care / branch.
- Personal loans (non-farm), credit cards, insurance (non-crop) → Redirect to bank / insurance company.
- Medical / health advice → Redirect to doctor / hospital / health helpline.
- Legal disputes, court cases, property matters → Redirect to lawyer / legal aid.
- Programming, tech, coding, apps, software → Redirect to technical resources / courses.
- Entertainment, movies, sports, celebrities → Politely decline, explain your scope.
- Political opinions → Politely decline, stay neutral.
- Cooking recipes (non-farming context) → Politely decline unless related to farm produce value-addition.

### 9. DISCLAIMER & ESCALATION FREQUENCY RULE (STRICT)
- DO NOT attach disclaimers, warnings, or advice to visit local offices/KVKs on standard farming queries (e.g., crop timing, soil prep, seed choice)!
- Include safety warnings ONLY if the user specifically asks about chemical pesticide dosages.
- Keep standard responses direct, friendly, and natural without repetitive disclaimers.

### 10. CALL OBJECTIVES
Achieve at least one of these in every response:
1. Understand the farmer's specific query and provide simple, actionable guidance.
2. Safely direct the farmer to official local resources when exact official data or local verification is required.
3. Provide reassurance and clear next steps without making unsupported promises.

### 11. GUARDRAILS & LIMITS (STRICT COMPLIANCE REQUIRED)
- Market Prices (Mandi Bhav): NEVER state a market price as a current guaranteed fact without using `get_mandi_prices` tool and advising local mandi verification.
- Pesticides & Chemicals: NEVER recommend chemical dosages or dangerous pesticides without adding a safety warning to consult a local agricultural extension officer before application.
- Promises: NEVER guarantee crop yields, profits, or government scheme approvals.
- Dynamic Off-Topic Refusal (Non-Agricultural / Financial / Medical / General off-topic):
  * DO NOT use a rigid hardcoded sentence or direct everything to an agricultural officer!
  * Politely state that you are Krishi Mitra (an agricultural assistant) and cannot help with that specific off-topic subject.
  * Dynamically suggest the proper, logical resource for that specific question (e.g., bank/customer care for loans/OTPs, doctor for medical queries, tech support for programming questions).
  * Keep the refusal short (1 to 2 sentences) and follow the exact language matching rules (Pure Devanagari Hindi for Hindi, pure Bengali script for Bengali, English for English).

### 12. CRITICAL DUAL-OUTPUT JSON FORMAT
You MUST ALWAYS respond ONLY with a valid JSON object containing exactly two keys: "tts_text" and "display_text". Do not include any extra commentary or markdown code fences.

JSON Structure:
{
  "tts_text": "<Text for Text-To-Speech audio synthesis>",
  "display_text": "<Text for screen display>"
}

### 13. FEW-SHOT EXAMPLES (Follow these patterns)

EXAMPLE 1 — English weather & mandi query:
User: "What is the mandi price of paddy in Burdwan today?"
Response:
{"tts_text": "As per today's live Agmarknet report for paddy in Burdwan Mandi, the modal price is 2,180 rupees per quintal, with a minimum of 2,050 rupees and a maximum of 2,250 rupees. Please verify rates at your local market before finalizing any sale.", "display_text": "As per today's live Agmarknet report for paddy in Burdwan Mandi, the modal price is ₹2,180/quintal (Min: ₹2,050, Max: ₹2,250). Please verify rates at your local market before finalizing any sale."}

EXAMPLE 2 — Hindi weather query:
User: "Kya aaj Burdwan mein baarish hogi?"
Response:
{"tts_text": "आज बर्धमान में लाइव मौसम रिपोर्ट के अनुसार तापमान 32 डिग्री सेल्सियस रहेगा और आज लगभग 5 मिलीमीटर बारिश होने की संभावना है। छिड़काव या कटाई का काम बारिश को ध्यान में रखकर करें।", "display_text": "आज बर्धमान में लाइव मौसम रिपोर्ट के अनुसार तापमान 32°C रहेगा और आज लगभग 5 mm बारिश होने की संभावना है। छिड़काव या कटाई का काम बारिश को ध्यान में रखकर करें।"}

EXAMPLE 3 — Bengali farming query:
User: "আমার পাট গাছের পাতা হলুদ হয়ে যাচ্ছে"
Response:
{"tts_text": "পাট গাছের পাতা হলুদ হওয়া প্রধানত নাইট্রোজেনের অভাবের লক্ষণ। আপনি প্রতি একরে ১৫-২০ কেজি ইউরিয়া সার প্রয়োগ করুন। এছাড়া জমিতে নিষ্কাশনের ব্যবস্থা ভালো রাখুন। সমস্যা বজায় থাকলে নিকটস্থ কৃষি কর্মকর্তার সাথে কথা বলুন।", "display_text": "পাট গাছের পাতা হলুদ হওয়া প্রধানত নাইট্রোজেনের অভাবের লক্ষণ। আপনি প্রতি একরে ১৫-২০ কেজি ইউরিয়া সার প্রয়োগ করুন। এছাড়া জমিতে নিষ্কাশনের ব্যবস্থা ভালো রাখুন। সমস্যা বজায় থাকলে নিকটস্থ কৃষি কর্মকর্তার সাথে কথা বলুন।"}

### 14. PERSISTENT MEMORY, CONSENT & DELETION PROTOCOL
You have access to tools `lookup_caller`, `save_farmer_facts`, and `forget_farmer_facts`.

1. EXPLICIT CONSENT BEFORE SAVING ANY INFORMATION:
   - Whenever the farmer shares information about themselves (their name, crops grown, land size, district/location, language preference, topic, or sensitive numbers/accounts):
     * Answer the user's question first in the USER'S SPOKEN LANGUAGE.
     * AFTER giving your answer, explicitly ask the user for permission to remember this information:
       - English: "I am going to remember your details (name, crop, location) so I can help you better next time. May I save this information?"
       - Hindi: "मैं आपकी जानकारी (नाम, फ़सल, खेत) याद रखने जा रहा हूँ ताकि अगली बार आपकी बेहतर मदद कर सकूँ। क्या मैं इसे सहेज सकता हूँ?"
       - Bengali: "আমি আপনার তথ্য (নাম, ফসল, জায়গা) মনে রাখতে যাচ্ছি যাতে পরের বার আরও ভালোভাবে সাহায্য করতে পারি। আমি কি এটি সংরক্ষণ করতে পারি?"

2. HANDLING USER PERMISSION RESPONSE:
   - IF THE USER SAYS YES / AGREE (e.g. "Yes", "Sure", "Haan", "Haanji", "Rakh lijiye", "Okay"):
     * Call function tool `save_farmer_facts(user_id=..., name=..., crops=..., land_size=..., language_preference=..., district=..., last_topic=...)`.
     * Set `language_preference="english"` if spoken in English, `"hindi"` if in Hindi, `"bengali"` if in Bengali!
     * Confirm warmly in the spoken language ("Thank you! I have saved your details." / "धन्यवाद! मैंने आपकी जानकारी सहेज ली है।").
   - IF THE USER SAYS NO / DECLINE (e.g. "No", "Nahi", "Na", "Don't save"):
     * Respectfully acknowledge: "No problem! I will not save this." / "कोई बात नहीं! मैं इसे नहीं सहेजूंगा।"
     * DO NOT call `save_farmer_facts` under any circumstances!

3. DELETING / FORGETTING USER INFORMATION (MANDATORY TOOL CALL):
   - Whenever the user asks to "delete my info", "forget my name", "remove my data", "clear my memory", or "don't remember me":
     * YOU MUST IMMEDIATELY EXECUTE `forget_farmer_facts(user_id=...)` during the turn!
     * Confirm warmly in the user's spoken language:
       - English: "I have deleted all your stored information from memory."
       - Hindi: "मैंने आपकी सभी सहेजी गई जानकारी को हटा दिया है।"
       - Bengali: "আমি আপনার সমস্ত সংরক্ষিত তথ্য মুছে ফেলেছি।"

4. RETURNING FARMERS (AUTOMATIC WELCOME BACK):
   - When a returning farmer calls back, if their saved profile exists in the database, welcome them back by name in their saved language_preference, reference their last discussed topic or crops, and ask how things are going:
     * English: "Hello Ramesh! Last time we spoke about your cotton. Did that help? How is your field doing today?"
     * Hindi: "नमस्ते रमेश जी! पिछली बार हमने आपकी कपास की फ़सल के बारे में चर्चा की थी। क्या उससे फ़ायदा हुआ? आज आपकी फ़सल कैसी है?"

### 15. EXTERNAL REAL-TIME TOOLS & MANDI/WEATHER PROTOCOL
You have access to real-time tools `get_district_weather` and `get_mandi_prices`.

1. WEATHER LOOKUP MANDATE (`get_district_weather`):
   - Use `get_district_weather(district_name=..., state=...)` whenever the user asks about weather, temperature, rain forecasts, or sowing/spraying weather conditions for a district.
   - Always report the date, current temperature, min/max temperatures, and rain expectation in the user's spoken language.

2. MANDI / MARKET PRICE MANDATE (`get_mandi_prices`):
   - Use `get_mandi_prices(commodity=..., district=..., state=...)` whenever the user asks about current mandi rates, wholesale prices, crop market prices (e.g. paddy, potato, jute, mustard, wheat), or selling rates in a district.
   - TIMESTAMP RULE: You MUST state the date of the report (e.g. "Aaj ke live update ke anusar..." / "As per today's report...").
   - MANDI GUARDRAIL: Speak the modal price per quintal clearly and ALWAYS remind the farmer to verify rates at their local market before selling!
   - NEVER hallucinate or invent market rates out of thin air. Always rely on the tool output!

### 16. DAY 6 OUTBOUND TELEPHONY, SCHEDULING & CONDITIONAL ALERTS PROTOCOL
You have access to tools `schedule_outbound_call`, `register_conditional_alert`, and `stop_alerts`.

1. VOICE CALL SCHEDULING (`schedule_outbound_call`):
   - Trigger `schedule_outbound_call(delay_or_time_str=..., topic=..., phone_number=..., language=...)` whenever the farmer requests a call at a specific time or after a delay (e.g. "call me in 10 seconds with potato mandi rates").
   - Set `language` parameter to `"english"`, `"hindi"`, or `"bengali"` matching the farmer's spoken register.
   - CRITICAL PRIVACY & SCHEDULE EXCLUSIVITY RULE:
     * When scheduling a call for a topic or question, you MUST ONLY confirm the call schedule in the web chat box (e.g. "Got it! I have scheduled a call for you in 30 seconds. All market details will be provided to you directly over the phone call.").
     * DO NOT call `get_mandi_prices` or write market rates, weather data, or topic answer details in the web chat box!
     * All answer details will be delivered EXCLUSIVELY over the scheduled phone call.

2. CONDITIONAL ALERT REGISTRATION (`register_conditional_alert`):
   - Trigger `register_conditional_alert(district=..., alert_type=..., phone_number=..., language=...)` whenever the farmer asks for automatic alerts on future conditions (e.g. "If you see heavy rain in Hooghly, call me").
   - Set `language` parameter to `"english"`, `"hindi"`, or `"bengali"` matching the farmer's spoken register.

3. STOP ALERTS / CANCELLATION (`stop_alerts`):
   - Trigger `stop_alerts(user_id=...)` whenever the user says "Stop alert", "stop automated calls", "অ্যালার্ট বন্ধ করুন", or "स्टॉप अलर्ट".
   - Confirm warmly: "All your automated alerts have been cancelled." / "आपके सभी ऑटोमेटेड अलर्ट रद्द कर दिए गए हैं।" / "আপনার সমস্ত অটোমেটেড অ্যালার্ট বাতিল করা হয়েছে।"

4. OUTBOUND CALL OPENING RULE (3 MANDATORY ELEMENTS):
   - When initiating or starting an Outbound Call, retrieve the farmer's stored language preference ('en', 'hi', 'bn').
   - Upon the farmer picking up the phone, YOU MUST IMMEDIATELY SPEAK THE 3 MANDATORY OPENING ELEMENTS WITHIN THE FIRST TWO SENTENCES:
     * English:
       1. Who: "Hello [Name/Farmer]! This is Krishi Mitra calling."
       2. Why: "You have an urgent alert update regarding [Topic] in [District] district."
       3. Stop: "If you do not want to receive these automated alerts in the future, you can say 'Stop alert' right now."
     * Hindi (Devanagari Script):
       1. Who: "नमस्ते [Name/Farmer]! मैं कृषि मित्र से बोल रहा हूँ।"
       2. Why: "आपके [District] जिले के लिए [Topic] का ज़रूरी अपडेट है।"
       3. Stop: "अगर आप आगे से ऐसे ऑटोमेटेड अलर्ट नहीं चाहते हैं, तो अभी 'स्टॉप अलर्ट' बोल सकते हैं।"
     * Bengali (Bengali Script):
       1. Who: "নমস্কার [Name/Farmer]! আমি কৃষি মিত্র বলছি।"
       2. Why: "আপনার [District] জেলার জন্য [Topic]-এর জরুরি অ্যালার্ট আপডেট রয়েছে।"
       3. Stop: "আপনি যদি ভবিষ্যতে এই ধরনের অটোমেটেড অ্যালার্ট বন্ধ করতে চান, তাহলে এখনই 'স্টপ অ্যালার্ট' বলতে পারেন।"

### 17. DAY 7 HUMAN ESCALATION, TICKET STATUS & COMFORTING FIRST-AID PROTOCOL
You have access to tools `create_escalation` and `check_ticket_status`.

0. TICKET STATUS INQUIRY MANDATE:
   - When the farmer asks if the support officer replied or asks for ticket status (e.g. "Did the support officer reply?", "What is the status of my ticket?", "Check my last ticket"):
     * Call `check_ticket_status(farmer_name=...)` immediately! NEVER say you don't have real-time access.
     * IF `has_officer_replied` is true: Read out the officer's response text warmly to the farmer.
     * IF `has_officer_replied` is false / status is OPEN: Inform the farmer warmly: "Your ticket #[ticket_id] is active and currently being reviewed by our agricultural officer. They will reply shortly." 

1. ESCALATION TRIGGERS:
   - TRIGGER A (DATA MISSING/OUTDATED): Mandi market prices or weather forecasts are unavailable or stale.
   - TRIGGER B (SERIOUS CROP CRISIS): Severe pest outbreaks, unexpected disease infections, high crop failure risks, or complex farming issues requiring expert intervention.
   - TRIGGER C (EXPLICIT USER REQUEST): The user explicitly asks to raise a ticket, contact support, or create an escalation (e.g., "raise a ticket", "create a support ticket", "contact support officer").

2. IMMEDIATE COMFORT & FIRST-AID ADVICE MANDATE:
   - When a farmer reports a severe crop issue or asks for an escalation ticket, ALWAYS provide 1 concise, comforting, immediate first-aid step (e.g. "For aphids, you can wash them off with a strong water jet or spray neem oil solution.") so the farmer feels comforted and supported immediately while waiting for officer follow-up.

3. EXPLICIT & CONDITIONAL TICKET CREATION PROTOCOL:
   - IF THE USER EXPLICITLY ASKS TO RAISE/CREATE A TICKET (e.g., "raise a ticket about pesticides", "support officer", "ticket create kar do"):
     * Immediately call `create_escalation(farmer_name=..., topic=..., summary=..., urgency=..., language=..., preferred_followup=...)`.
     * State out loud warmly with ticket confirmation and comforting next steps:
       - English: "I am creating an urgent support ticket for our agricultural officer. In the meantime, as an immediate solution you can spray neem oil mixed with water. The officer will contact you shortly."
       - Hindi: "मैं हमारे कृषि अधिकारी के लिए तुरंत एक सहायता टिकट बना रहा हूँ। इस बीच, आप नीम के तेल और पानी का छिड़काव कर सकते हैं। अधिकारी जल्द ही आपसे संपर्क करेंगे।"
       - Bengali: "আমি আমাদের কৃষি কর্মকর্তার জন্য একটি জরুরি সহায়তা টিকিট তৈরি করছি। এই সময়ে আপনি জলের সাথে নিম তেল মিশিয়ে স্প্রে করতে পারেন। কর্মকর্তা শীঘ্রই আপনার সাথে যোগাযোগ করবেন।"
   - IF PROPOSING ESCALATION (TRIGGER A or B without explicit user command):
     * Ask for permission out loud: "This crop issue requires expert review. Would you like me to create a support ticket and notify our agricultural officer to contact you?"
   - IF USER AGREES ("yes", "sure", "ha", "haan", "haan kar do", "thik ache"):
     * Call `create_escalation(...)` and speak the created ticket confirmation warmly.
   - IF USER REFUSES ("no", "na", "nahi", "don't create"):
     * Do NOT call `create_escalation`. Continue conversation normally.
"""


def parse_llm_json(raw_text: str) -> tuple[str, str]:
    """Parse JSON output from LLM, returning (tts_text, display_text) with robust regex fallback."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    # Attempt 1: Strict JSON parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            tts = data.get("tts_text")
            display = data.get("display_text")
            if tts and display:
                return str(tts).strip(), str(display).strip()
    except Exception:
        pass

    # Attempt 2: Regex extraction for JSON keys
    tts_match = re.search(r'"tts_text"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    display_match = re.search(
        r'"display_text"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL
    )

    tts_val = tts_match.group(1) if tts_match else None
    display_val = display_match.group(1) if display_match else None

    # Attempt 3: Loose key splitting if regex was partial
    if not tts_val and '"tts_text"' in text:
        try:
            part = text.split('"tts_text"', 1)[1]
            part = part.split(":", 1)[1].strip()
            if part.startswith('"'):
                part = part[1:]
            tts_val = part.split('",', 1)[0].split('"}', 1)[0].strip()
        except Exception:
            pass

    if not display_val and '"display_text"' in text:
        try:
            part = text.split('"display_text"', 1)[1]
            part = part.split(":", 1)[1].strip()
            if part.startswith('"'):
                part = part[1:]
            display_val = part.split('",', 1)[0].split('"}', 1)[0].strip()
        except Exception:
            pass

    clean_tts = tts_val if tts_val else text
    clean_display = display_val if display_val else text

    clean_tts = re.sub(r'^\s*\{\s*"tts_text"\s*:\s*"?', "", clean_tts)
    clean_tts = re.sub(r'"?\s*,\s*"display_text".*$', "", clean_tts, flags=re.DOTALL)
    clean_tts = clean_tts.strip("\"':{} ")

    clean_display = re.sub(r'^\s*\{\s*"display_text"\s*:\s*"?', "", clean_display)
    clean_display = clean_display.strip("\"':{} ")

    return clean_tts, clean_display


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    @function_tool
    async def lookup_caller(self, context: RunContext, user_id: str) -> str:
        """Lookup existing farmer profile in database to get saved name, location, crops, and last topic.

        Args:
            user_id: The phone number or caller ID of the farmer (e.g. '+919876543210' or 'default_farmer').
        """
        profile = db.get_farmer_profile(user_id)
        if profile:
            return json.dumps({"found": True, "profile": profile}, ensure_ascii=False)
        return json.dumps(
            {"found": False, "message": "No profile found for this caller."},
            ensure_ascii=False,
        )

    @function_tool
    async def save_farmer_facts(
        self,
        context: RunContext,
        user_id: str,
        name: str = "",
        crops: str = "",
        land_size: str = "",
        language_preference: str = "",
        district: str = "",
        last_topic: str = "",
    ) -> str:
        """Save or update farmer profile facts in SQLite database AFTER explicit user permission/consent has been granted by the user during the call.

        Args:
            user_id: Caller ID / phone number of the farmer.
            name: Farmer's name (e.g. 'Ramesh', 'Subhash').
            crops: Crops grown by the farmer (e.g. 'Paddy, Mustard').
            land_size: Size of farm land (e.g. '2 acres').
            language_preference: Primary language spoken by farmer ('english', 'hindi', 'bengali').
            district: District / state (e.g. 'Burdwan, West Bengal').
            last_topic: Last agricultural question/topic discussed (e.g. 'Sub-1 paddy selection', 'Mustard pest control'). NEVER pass location/district as last_topic.
        """
        facts = {
            "crops_grown": crops,
            "land_size": land_size,
            "language_preference": language_preference,
            "district": district,
            "last_topic": last_topic,
        }
        saved_profile = db.upsert_farmer_profile(
            user_id, name=name, facts=facts, consent=True
        )
        return json.dumps(
            {"success": True, "saved_profile": saved_profile}, ensure_ascii=False
        )

    @function_tool
    async def forget_farmer_facts(
        self,
        context: RunContext,
        user_id: str,
    ) -> str:
        """Delete and clear all stored farmer profile facts and memory from the SQLite database when requested by the user.

        Args:
            user_id: Caller ID / room ID of the farmer.
        """
        db.delete_farmer_profile(user_id)
        return json.dumps(
            {"success": True, "message": "All stored profile facts deleted."},
            ensure_ascii=False,
        )

    @function_tool
    async def get_district_weather(
        self,
        context: RunContext,
        district_name: str,
        state: str = "West Bengal",
    ) -> str:
        """TOOL 1: get_district_weather
        Use this tool whenever the user asks about weather, temperature, rain forecasts, or sowing/spraying conditions for a district.

        Args:
            district_name: Name of district (e.g. 'Burdwan', 'Hooghly', 'Bankura', 'Nadia', 'Kolkata').
            state: Name of state (default 'West Bengal').
        """
        return await tools.fetch_district_weather(
            district_name=district_name, state=state
        )

    @function_tool
    async def get_mandi_prices(
        self,
        context: RunContext,
        commodity: str,
        district: str = "Burdwan",
        state: str = "West Bengal",
    ) -> str:
        """TOOL 2: get_mandi_prices
        Use this tool whenever the user asks about current mandi rates, wholesale prices, crop market prices (e.g. paddy, potato, jute), or selling rates in a district.

        Args:
            commodity: Commodity / crop name (e.g. 'Paddy', 'Rice', 'Potato', 'Jute', 'Mustard', 'Wheat').
            district: District name (default 'Burdwan').
            state: State name (default 'West Bengal').
        """
        return await tools.fetch_mandi_prices(
            commodity=commodity, district=district, state=state
        )

    @function_tool
    async def schedule_outbound_call(
        self,
        context: RunContext,
        delay_or_time_str: str,
        topic: str,
        phone_number: str | None = None,
        district: str = "Burdwan",
        language: str = "hindi",
    ) -> str:
        """TOOL 3: schedule_outbound_call
        Use this tool whenever the farmer requests an outbound voice phone call after a delay or at a specific time (e.g. 'call me in 10 seconds with potato mandi rates').

        Args:
            delay_or_time_str: Time string (e.g. '10 seconds', '2 minutes', 'at 2:30 PM').
            topic: Agricultural topic context (e.g. 'potato mandi prices', 'heavy rain forecast').
            phone_number: Optional phone number.
            district: District name (default 'Burdwan').
            language: Spoken language ('english', 'hindi', 'bengali').
        """
        return await tools.schedule_outbound_call(
            delay_or_time_str=delay_or_time_str,
            topic=topic,
            phone_number=phone_number,
            user_id="default_farmer",
            district=district,
            language=language,
        )

    @function_tool
    async def register_conditional_alert(
        self,
        context: RunContext,
        district: str,
        alert_type: str,
        phone_number: str | None = None,
        language: str = "hindi",
    ) -> str:
        """TOOL 4: register_conditional_alert
        Use this tool whenever the farmer asks to register automatic future phone call alerts for a district (e.g. 'If you see heavy rain in Hooghly, call me').

        Args:
            district: District name (e.g. 'Hooghly', 'Burdwan').
            alert_type: Type of alert (e.g. 'heavy rain', 'mandi price drop', 'pest warning').
            phone_number: Optional phone number.
            language: Spoken language ('english', 'hindi', 'bengali').
        """
        return await tools.register_conditional_alert(
            district=district,
            alert_type=alert_type,
            phone_number=phone_number,
            user_id="default_farmer",
            language=language,
        )

    @function_tool
    async def stop_alerts(
        self,
        context: RunContext,
        user_id: str = "default_farmer",
    ) -> str:
        """TOOL 5: stop_alerts
        Use this tool whenever the user asks to stop alerts, stop service, cancel automated phone calls, unsubscribe, or says 'Stop alert', 'Stop service', 'Cancel calls', or 'End alerts'.

        Args:
            user_id: User ID / phone number of farmer.
        """
        cancelled_count = db.cancel_alert_subscription(user_id)
        return json.dumps(
            {
                "success": True,
                "cancelled_alerts_count": cancelled_count,
                "message": "All automated call services, alerts, and scheduled calls have been stopped.",
            },
            ensure_ascii=False,
        )

    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        farmer_name: str,
        topic: str,
        summary: str,
        urgency: str = "Medium",
        language: str = "english",
        preferred_followup: str = "Phone Call",
    ) -> str:
        """TOOL 6: create_escalation
        Use this tool ONLY AFTER asking explicit user permission to create a support ticket / escalation for missing data, crop disease crisis, or complex issues.

        Args:
            farmer_name: Name of the farmer.
            topic: Crop or topic needing escalation (e.g. Potato late blight disease).
            summary: Detailed summary of the issue (will be privacy-sanitized automatically).
            urgency: Urgency level ('Low', 'Medium', 'High', 'Emergency').
            language: Spoken language ('english', 'hindi', 'bengali').
            preferred_followup: Preferred followup method ('Phone Call', 'WhatsApp', 'Visit').
        """
        return await tools.create_escalation(
            farmer_name=farmer_name,
            topic=topic,
            summary=summary,
            urgency=urgency,
            language=language,
            preferred_followup=preferred_followup,
        )

    @function_tool
    async def check_ticket_status(
        self,
        context: RunContext,
        farmer_name: str = "Arpan",
    ) -> str:
        """TOOL 7: check_ticket_status
        Use this tool whenever the farmer asks if the support officer has replied, asks for the status of their ticket, or asks 'Did the support officer reply to my ticket?'.

        Args:
            farmer_name: Name of the farmer.
        """
        ticket = db.get_latest_escalation(farmer_name)
        if not ticket:
            return json.dumps(
                {
                    "found": False,
                    "message": "No escalation tickets found in database for this farmer.",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "found": True,
                "ticket_id": ticket["ticket_id"],
                "topic": ticket["topic"],
                "status": ticket["status"],
                "officer_response": ticket.get("officer_response"),
                "has_officer_replied": ticket["status"] == "OFFICER_REPLIED"
                or bool(ticket.get("officer_response")),
                "created_at": ticket["created_at"],
            },
            ensure_ascii=False,
        )

    async def tts_node(self, text: AsyncIterable[str], model_settings: ModelSettings):
        """Route tts_text to Murf Falcon TTS engine."""
        full_text = ""
        async for chunk in text:
            if isinstance(chunk, str):
                full_text += chunk
            elif hasattr(chunk, "text"):
                full_text += chunk.text

        tts_text, _ = parse_llm_json(full_text)

        # Split long tts_text into smaller sentence chunks so Murf TTS streaming WebSocket never times out
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", tts_text) if s.strip()
        ]
        if not sentences:
            sentences = [tts_text]

        async def _tts_stream():
            for sentence in sentences:
                yield sentence + " "

        async for frame in Agent.default.tts_node(self, _tts_stream(), model_settings):
            yield frame

    async def transcription_node(
        self, text: AsyncIterable[str], model_settings: ModelSettings
    ):
        """Route display_text to the user UI / transcript stream."""
        full_text = ""
        async for chunk in text:
            if isinstance(chunk, str):
                full_text += chunk
            elif hasattr(chunk, "text"):
                full_text += chunk.text

        _, display_text = parse_llm_json(full_text)

        async def _display_stream():
            yield display_text

        async for item in Agent.default.transcription_node(
            self, _display_stream(), model_settings
        ):
            yield item


server = AgentServer()


def prewarm(proc: JobProcess):
    import api_server
    import email_listener

    outbound_dialer.start_scheduled_call_poller()
    email_listener.start_poller_thread(interval_seconds=30)
    api_server.start_api_server_thread(port=8080)
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.5,
        min_silence_duration=1.2,
        prefix_padding_duration=0.6,
    )


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(
            model="nova-3",
            language="multi",
            keyterm=[
                "fertilizer",
                "pesticide",
                "irrigation",
                "wheat",
                "paddy",
                "cotton",
                "mustard",
                "potato",
                "jute",
                "mandi",
                "weather",
                "temperature",
                "rainfall",
                "soil",
                "NPK",
                "urea",
                "Burdwan",
                "Hooghly",
                "Bankura",
                "Nadia",
                "Krishi",
                "Mitra",
                "खेती",
                "किसान",
                "फसल",
                "गेहूं",
                "धान",
                "सरसों",
                "आलू",
                "मंडी",
                "भाव",
                "मौसम",
                "बारिश",
                "कीटनाशक",
                "यूरिया",
                "मिट्टी",
                "सिंचाई",
                "পাট",
                "ধান",
                "চাষ",
                "সার",
                "মাটি",
                "কৃষি",
                "গাছ",
                "ফসল",
                "পোকা",
                "রোগ",
                "বীজ",
                "আঁশ",
                "সেচ",
                "জমি",
                "কীটনাশক",
                "ইউরিয়া",
                "ফলন",
                "আমন",
                "বোরো",
                "কাটা",
                "আলু",
                "বাজার",
                "দাম",
                "আবহাওয়া",
                "বৃষ্টি",
            ],
            endpointing_ms=500,
            smart_format=True,
        ),
        llm=google.LLM(
            model="gemini-3.1-flash-lite",
        ),
        tts=murf.TTS(
            voice="Anisha",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    await ctx.connect()

    async def _on_shutdown():
        logger.info("Gracefully closing session room context.")

    ctx.add_shutdown_callback(_on_shutdown)

    # Caller lookup & dynamic welcoming greeting
    user_id = "default_farmer"
    if ctx.room and ctx.room.name:
        user_id = ctx.room.name

    # Automatic turn-level language & topic detector & persistence
    @session.on("user_speech_committed")
    def _on_user_speech(ev):
        user_text = ""
        if hasattr(ev, "content"):
            user_text = str(ev.content)
        elif hasattr(ev, "user_transcript"):
            user_text = str(ev.user_transcript)
        else:
            user_text = str(ev)

        if user_text and len(user_text.strip()) >= 3:
            # 1. Update language preference
            if re.search(r"[\u0980-\u09FF]", user_text):
                db.update_language_preference(user_id, "bengali")
            elif re.search(r"[\u0900-\u097F]", user_text):
                db.update_language_preference(user_id, "hindi")
            elif re.search(r"[a-zA-Z]", user_text):
                db.update_language_preference(user_id, "english")

            # 2. Extract and auto-save turn-level rich topic gist and commodity
            target_commodity = tools.extract_commodity_from_topic(user_text)
            topic_gist = tools.extract_topic_gist(user_text)
            existing_prof = db.get_farmer_profile(user_id) or {}
            existing_facts = dict(existing_prof)
            if target_commodity:
                existing_facts["crops_grown"] = target_commodity
            if topic_gist:
                existing_facts["last_topic"] = topic_gist
            db.upsert_farmer_profile(user_id=user_id, facts=existing_facts)

    profile = db.get_farmer_profile(user_id)
    lang_pref = (
        str(profile.get("language_preference", "")).lower() if profile else "hindi"
    )
    name = profile.get("name", "") if profile else ""
    last_topic = str(profile.get("last_topic") or "").strip() if profile else ""
    crops_grown = str(profile.get("crops_grown") or "").strip() if profile else ""

    if name:
        if last_topic:
            if lang_pref == "english":
                greeting_text = f"Hello {name}! Last time we discussed {last_topic}. How is your field doing today and how can I assist you?"
            elif lang_pref == "bengali":
                greeting_text = f"নমস্কার {name}! গতবার আমরা {last_topic} নিয়ে কথা বলেছিলাম। আজ আপনার ফসল কেমন আছে এবং আমি আপনাকে কীভাবে সাহায্য করতে পারি?"
            else:
                greeting_text = f"नमस्ते {name} जी! पिछली बार हमने {last_topic} के बारे में चर्चा की थी। क्या उससे फ़ायदा हुआ? आज आपकी फ़सल कैसी है और मैं कैसे सहायता कर सकता हूँ?"
        elif crops_grown:
            if lang_pref == "english":
                greeting_text = f"Hello {name}! Hope your {crops_grown} crop is doing well. How can I assist you with your farm today?"
            elif lang_pref == "bengali":
                greeting_text = f"নমস্কার {name}! আশা করি আপনার {crops_grown} ফসল ভালো আছে। আজ আমি আপনাকে কীভাবে সাহায্য করতে পারি?"
            else:
                greeting_text = f"नमस्ते {name} जी! आशा है आपकी {crops_grown} की फ़सल अच्छी चल रही है। आज मैं आपकी क्या सहायता कर सकता हूँ?"
        else:
            if lang_pref == "english":
                greeting_text = f"Hello {name}! Welcome back to Krishi Mitra. How can I assist you with your farm today?"
            elif lang_pref == "bengali":
                greeting_text = f"নমস্কার {name}! কৃষি মিত্রতে আপনাকে স্বাগতম। আজ আমি আপনাকে কীভাবে সাহায্য করতে পারি?"
            else:
                greeting_text = f"नमस्ते {name} जी! कृषि मित्र में आपका फिर से स्वागत है। आज मैं आपकी फ़सल या खेती में कैसे सहायता कर सकता हूँ?"
    else:
        if lang_pref == "english":
            greeting_text = "Hello! Welcome back to Krishi Mitra. How can I assist you with your farm today?"
        elif lang_pref == "bengali":
            greeting_text = (
                "নমস্কার! কৃষি মিত্রতে আপনাকে স্বাগতম। আজ আমি আপনাকে কীভাবে সাহায্য করতে পারি?"
            )
        else:
            greeting_text = "नमस्ते! मैं कृषि मित्र हूँ। आज मैं आपकी फ़सल, मिट्टी या सरकारी योजनाओं में कैसे सहायता कर सकता हूँ?"

    greeting_json = json.dumps(
        {
            "tts_text": greeting_text,
            "display_text": greeting_text,
        },
        ensure_ascii=False,
    )
    await session.say(greeting_json)


if __name__ == "__main__":
    cli.run_app(server)

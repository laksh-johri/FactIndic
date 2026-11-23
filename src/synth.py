"""Deterministic generator for the FactIndic synthetic benchmark.

Creates two JSONL files:
  data/factindic_synth_articles.jsonl  (128 articles: 64 Hindi, 64 Hinglish)
  data/factindic_synth_errors.jsonl    (512 rows: 128 CORRECT + 384 ERROR)

Every article is produced from a hand-written domain template (8 domains x 2
languages). Slot values (people, organisations, places, numbers, dates and a
polarity phrase) are sampled with a fixed seed, so running this file twice
gives byte-identical output.

Usage:  python -m src.synth            (writes to the paths in config.yaml)
"""
from __future__ import annotations

import json
import random
import re
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Pools of slot values. Each entry is a (Hindi/Devanagari, Hinglish/Latin) pair.
# All names are fictional / generic.
# ---------------------------------------------------------------------------
PERSONS = [
    ("राजेश कुमार", "Rajesh Kumar"), ("सुनीता शर्मा", "Sunita Sharma"),
    ("अमित वर्मा", "Amit Verma"), ("प्रिया सिंह", "Priya Singh"),
    ("विकास यादव", "Vikas Yadav"), ("नेहा गुप्ता", "Neha Gupta"),
    ("संजय मिश्रा", "Sanjay Mishra"), ("अंजलि पटेल", "Anjali Patel"),
    ("रोहित चौहान", "Rohit Chauhan"), ("कविता जोशी", "Kavita Joshi"),
    ("मनोज त्रिपाठी", "Manoj Tripathi"), ("पूजा रस्तोगी", "Pooja Rastogi"),
    ("आलोक सक्सेना", "Alok Saxena"), ("रेखा पांडे", "Rekha Pandey"),
    ("दीपक मेहरा", "Deepak Mehra"), ("सीमा अग्रवाल", "Seema Agarwal"),
    ("अर्जुन रावत", "Arjun Rawat"), ("मीना कुशवाहा", "Meena Kushwaha"),
    ("सुरेश नायर", "Suresh Nair"), ("फ़रहान अली", "Farhan Ali"),
    ("ज़ोया ख़ान", "Zoya Khan"), ("गुरप्रीत सिंह", "Gurpreet Singh"),
    ("हर्ष भटनागर", "Harsh Bhatnagar"), ("ललिता देवी", "Lalita Devi"),
]

LOCATIONS = [
    ("लखनऊ", "Lucknow"), ("पटना", "Patna"), ("जयपुर", "Jaipur"),
    ("भोपाल", "Bhopal"), ("इंदौर", "Indore"), ("वाराणसी", "Varanasi"),
    ("कानपुर", "Kanpur"), ("नागपुर", "Nagpur"), ("देहरादून", "Dehradun"),
    ("रांची", "Ranchi"), ("आगरा", "Agra"), ("अहमदाबाद", "Ahmedabad"),
    ("चंडीगढ़", "Chandigarh"), ("गोरखपुर", "Gorakhpur"),
    ("प्रयागराज", "Prayagraj"), ("ग्वालियर", "Gwalior"),
]

MONTHS = [
    ("जनवरी", "January"), ("फ़रवरी", "February"), ("मार्च", "March"),
    ("अप्रैल", "April"), ("मई", "May"), ("जून", "June"), ("जुलाई", "July"),
    ("अगस्त", "August"), ("सितंबर", "September"), ("अक्टूबर", "October"),
    ("नवंबर", "November"), ("दिसंबर", "December"),
]

# ---------------------------------------------------------------------------
# Domain templates. Slots: {person} {org} {loc} {date} {num} {num2} {pol}
#   num  = the key number that appears in the summary
#   num2 = a distractor number that appears ONLY in the source
#   pol  = polarity phrase (positive, negative) -> used for negation errors
# Every summary template must contain person, org, loc, date, num, pol once.
# ---------------------------------------------------------------------------
DOMAINS: dict[str, dict] = {
    "politics": {
        "orgs": [("जन विकास पार्टी", "Jan Vikas Party"), ("लोक कल्याण मोर्चा", "Lok Kalyan Morcha"),
                 ("राष्ट्रीय प्रगति दल", "Rashtriya Pragati Dal"), ("नव भारत संघ", "Nav Bharat Sangh"),
                 ("किसान एकता पार्टी", "Kisan Ekta Party")],
        "num": (5000, 60000, 500), "num2": (5000, 60000, 500),
        "hi": {
            "pol": ("की", "नहीं की"),
            "title": "{loc} में {org} की जनसभा",
            "source": ["{org} के अध्यक्ष {person} ने {date} को {loc} में एक जनसभा को संबोधित किया।",
                       "आयोजकों के अनुसार इस सभा में लगभग {num} लोग शामिल हुए।",
                       "{person} ने अपने भाषण में बेरोज़गारी और महँगाई के मुद्दे उठाए।",
                       "उन्होंने आगामी चुनाव के लिए किसी नए गठबंधन की घोषणा {pol}।",
                       "पिछली बार इसी मैदान में लगभग {num2} लोग जुटे थे।"],
            "summary": ["{org} के अध्यक्ष {person} ने {date} को {loc} में जनसभा को संबोधित किया।",
                        "सभा में लगभग {num} लोग शामिल हुए।",
                        "उन्होंने किसी नए गठबंधन की घोषणा {pol}।"],
            "claims": ["{person} {org} के अध्यक्ष हैं।", "{person} ने {loc} में जनसभा को संबोधित किया।",
                       "जनसभा {date} को हुई।", "सभा में लगभग {num} लोग शामिल हुए।",
                       "{person} ने नए गठबंधन की घोषणा {pol}।"],
        },
        "hg": {
            "pol": ("kiya", "nahi kiya"),
            "title": "{loc} mein {org} ki rally",
            "source": ["{org} ke president {person} ne {date} ko {loc} mein ek public rally ko address kiya.",
                       "Organisers ke mutabik is rally mein lagbhag {num} log shamil hue.",
                       "{person} ne apni speech mein unemployment aur inflation ke issues uthaye.",
                       "Unhone upcoming election ke liye kisi naye alliance ka announcement {pol}.",
                       "Pichhli baar isi ground par lagbhag {num2} log jute the."],
            "summary": ["{org} ke president {person} ne {date} ko {loc} mein rally ko address kiya.",
                        "Rally mein lagbhag {num} log shamil hue.",
                        "Unhone kisi naye alliance ka announcement {pol}."],
            "claims": ["{person} {org} ke president hain.", "{person} ne {loc} mein rally ko address kiya.",
                       "Rally {date} ko hui.", "Rally mein lagbhag {num} log shamil hue.",
                       "{person} ne naye alliance ka announcement {pol}."],
        },
    },
    "sports": {
        "orgs": [("थंडर वॉरियर्स", "Thunder Warriors"), ("रॉयल स्ट्राइकर्स", "Royal Strikers"),
                 ("ईगल्स क्रिकेट क्लब", "Eagles Cricket Club"), ("टाइगर्स इलेवन", "Tigers Eleven"),
                 ("सनराइज़ क्लब", "Sunrise Club")],
        "num": (150, 400, 1), "num2": (90, 149, 1),
        "hi": {
            "pol": ("गया", "नहीं गया"),
            "title": "{loc} में {org} का दमदार प्रदर्शन",
            "source": ["{date} को {loc} में खेले गए मुकाबले में {org} ने शानदार प्रदर्शन किया।",
                       "कप्तान {person} ने टीम का नेतृत्व किया।",
                       "टीम ने पहले बल्लेबाज़ी करते हुए {num} रन बनाए।",
                       "विपक्षी टीम केवल {num2} रन ही बना सकी।",
                       "बारिश के कारण मैच को बीच में रोका {pol}।"],
            "summary": ["{date} को {loc} में हुए मुकाबले में {org} की कप्तानी {person} ने की।",
                        "टीम ने {num} रन बनाए।",
                        "बारिश के कारण मैच को बीच में रोका {pol}।"],
            "claims": ["{person} {org} के कप्तान हैं।", "मुकाबला {loc} में हुआ।", "मुकाबला {date} को हुआ।",
                       "{org} ने {num} रन बनाए।", "बारिश के कारण मैच को बीच में रोका {pol}।"],
        },
        "hg": {
            "pol": ("gaya", "nahi gaya"),
            "title": "{loc} mein {org} ka dumdaar performance",
            "source": ["{date} ko {loc} mein khele gaye match mein {org} ne shandaar performance diya.",
                       "Captain {person} ne team ko lead kiya.",
                       "Team ne pehle batting karte hue {num} runs banaye.",
                       "Opposition team sirf {num2} runs hi bana payi.",
                       "Baarish ki wajah se match ko beech mein roka {pol}."],
            "summary": ["{date} ko {loc} mein hue match mein {org} ki captaincy {person} ne ki.",
                        "Team ne {num} runs banaye.",
                        "Baarish ki wajah se match ko beech mein roka {pol}."],
            "claims": ["{person} {org} ke captain hain.", "Match {loc} mein hua.", "Match {date} ko hua.",
                       "{org} ne {num} runs banaye.", "Baarish ki wajah se match ko beech mein roka {pol}."],
        },
    },
    "business": {
        "orgs": [("सूर्या टेक्सटाइल्स", "Surya Textiles"), ("गंगा फ़ूड्स", "Ganga Foods"),
                 ("हिमालय स्टील", "Himalaya Steel"), ("नवरत्न मोटर्स", "Navratna Motors"),
                 ("कृषि मित्र लिमिटेड", "Krishi Mitra Limited")],
        "num": (50, 900, 5), "num2": (50, 900, 5),
        "hi": {
            "pol": ("की", "नहीं की"),
            "title": "{org} के तिमाही नतीजे जारी",
            "source": ["{org} के सीईओ {person} ने {date} को {loc} में एक प्रेस कॉन्फ़्रेंस में कंपनी के तिमाही नतीजे जारी किए।",
                       "उन्होंने बताया कि इस तिमाही में कंपनी का मुनाफ़ा {num} करोड़ रुपये रहा।",
                       "पिछले साल इसी तिमाही में मुनाफ़ा {num2} करोड़ रुपये था।",
                       "{person} ने कहा कि कंपनी नए बाज़ारों में विस्तार करेगी।",
                       "कंपनी ने कर्मचारियों की छँटनी की घोषणा {pol}।"],
            "summary": ["{org} के सीईओ {person} ने {date} को {loc} में तिमाही नतीजे जारी किए।",
                        "कंपनी का मुनाफ़ा {num} करोड़ रुपये रहा।",
                        "कंपनी ने कर्मचारियों की छँटनी की घोषणा {pol}।"],
            "claims": ["{person} {org} के सीईओ हैं।", "तिमाही नतीजे {loc} में जारी किए गए।",
                       "तिमाही नतीजे {date} को जारी किए गए।", "कंपनी का मुनाफ़ा {num} करोड़ रुपये रहा।",
                       "कंपनी ने छँटनी की घोषणा {pol}।"],
        },
        "hg": {
            "pol": ("kiya", "nahi kiya"),
            "title": "{org} ke quarterly results jaari",
            "source": ["{org} ke CEO {person} ne {date} ko {loc} mein ek press conference mein company ke quarterly results release kiye.",
                       "Unhone bataya ki is quarter mein company ka profit {num} crore rupaye raha.",
                       "Pichhle saal isi quarter mein profit {num2} crore rupaye tha.",
                       "{person} ne kaha ki company naye markets mein expand karegi.",
                       "Company ne employees ki layoffs ka announcement {pol}."],
            "summary": ["{org} ke CEO {person} ne {date} ko {loc} mein quarterly results release kiye.",
                        "Company ka profit {num} crore rupaye raha.",
                        "Company ne layoffs ka announcement {pol}."],
            "claims": ["{person} {org} ke CEO hain.", "Quarterly results {loc} mein release kiye gaye.",
                       "Quarterly results {date} ko release kiye gaye.", "Company ka profit {num} crore rupaye raha.",
                       "Company ne layoffs ka announcement {pol}."],
        },
    },
    "health": {
        "orgs": [("जीवन ज्योति अस्पताल", "Jeevan Jyoti Hospital"), ("आरोग्य सेवा केंद्र", "Arogya Seva Kendra"),
                 ("सिटी केयर अस्पताल", "City Care Hospital"), ("संजीवनी मेडिकल कॉलेज", "Sanjeevani Medical College"),
                 ("स्वस्थ भारत ट्रस्ट", "Swasth Bharat Trust")],
        "num": (200, 1500, 10), "num2": (10, 150, 1),
        "hi": {
            "pol": ("आया", "नहीं आया"),
            "title": "{loc} में मुफ़्त स्वास्थ्य शिविर",
            "source": ["{loc} के {org} ने {date} को एक मुफ़्त स्वास्थ्य शिविर का आयोजन किया।",
                       "शिविर के प्रभारी डॉ. {person} ने बताया कि कुल {num} मरीज़ों की जाँच की गई।",
                       "इनमें से {num2} मरीज़ों को आगे के इलाज के लिए भेजा गया।",
                       "डॉक्टरों ने लोगों को साफ़ पानी पीने की सलाह दी।",
                       "शिविर में किसी गंभीर बीमारी का मामला सामने {pol}।"],
            "summary": ["{org} ने {date} को {loc} में मुफ़्त स्वास्थ्य शिविर लगाया, जिसके प्रभारी डॉ. {person} थे।",
                        "शिविर में {num} मरीज़ों की जाँच की गई।",
                        "किसी गंभीर बीमारी का मामला सामने {pol}।"],
            "claims": ["{org} ने मुफ़्त स्वास्थ्य शिविर लगाया।", "शिविर {loc} में लगा।", "शिविर {date} को लगा।",
                       "शिविर के प्रभारी डॉ. {person} थे।", "शिविर में {num} मरीज़ों की जाँच की गई।",
                       "किसी गंभीर बीमारी का मामला सामने {pol}।"],
        },
        "hg": {
            "pol": ("aaya", "nahi aaya"),
            "title": "{loc} mein free health camp",
            "source": ["{loc} ke {org} ne {date} ko ek free health camp organise kiya.",
                       "Camp ke incharge Dr. {person} ne bataya ki total {num} patients ka checkup kiya gaya.",
                       "Inmein se {num2} patients ko aage ke treatment ke liye refer kiya gaya.",
                       "Doctors ne logon ko saaf paani peene ki salah di.",
                       "Camp mein kisi serious bimari ka case saamne {pol}."],
            "summary": ["{org} ne {date} ko {loc} mein free health camp lagaya, jiske incharge Dr. {person} the.",
                        "Camp mein {num} patients ka checkup kiya gaya.",
                        "Kisi serious bimari ka case saamne {pol}."],
            "claims": ["{org} ne free health camp lagaya.", "Camp {loc} mein laga.", "Camp {date} ko laga.",
                       "Camp ke incharge Dr. {person} the.", "Camp mein {num} patients ka checkup kiya gaya.",
                       "Kisi serious bimari ka case saamne {pol}."],
        },
    },
    "education": {
        "orgs": [("विद्या भारती विश्वविद्यालय", "Vidya Bharati University"), ("सरस्वती इंस्टीट्यूट", "Saraswati Institute"),
                 ("ज्ञानोदय विश्वविद्यालय", "Gyanodaya University"), ("आदर्श कॉलेज", "Adarsh College"),
                 ("प्रज्ञा विश्वविद्यालय", "Pragya University")],
        "num": (800, 6000, 10), "num2": (800, 6000, 10),
        "hi": {
            "pol": ("गया", "नहीं गया"),
            "title": "{org} का दीक्षांत समारोह",
            "source": ["{org} ने {date} को {loc} में दीक्षांत समारोह आयोजित किया।",
                       "कुलपति {person} ने समारोह की अध्यक्षता की।",
                       "इस वर्ष कुल {num} छात्रों को डिग्रियाँ प्रदान की गईं।",
                       "पिछले वर्ष यह संख्या {num2} थी।",
                       "समारोह में फ़ीस बढ़ाने का प्रस्ताव पारित किया {pol}।"],
            "summary": ["{org} ने {date} को {loc} में दीक्षांत समारोह आयोजित किया, जिसकी अध्यक्षता कुलपति {person} ने की।",
                        "कुल {num} छात्रों को डिग्रियाँ दी गईं।",
                        "फ़ीस बढ़ाने का प्रस्ताव पारित किया {pol}।"],
            "claims": ["{person} {org} के कुलपति हैं।", "दीक्षांत समारोह {loc} में हुआ।",
                       "दीक्षांत समारोह {date} को हुआ।", "{num} छात्रों को डिग्रियाँ दी गईं।",
                       "फ़ीस बढ़ाने का प्रस्ताव पारित किया {pol}।"],
        },
        "hg": {
            "pol": ("gaya", "nahi gaya"),
            "title": "{org} ki convocation ceremony",
            "source": ["{org} ne {date} ko {loc} mein convocation ceremony organise ki.",
                       "Vice-chancellor {person} ne ceremony ki adhyakshata ki.",
                       "Is saal total {num} students ko degrees di gayi.",
                       "Pichhle saal yeh number {num2} tha.",
                       "Ceremony mein fees badhane ka proposal pass kiya {pol}."],
            "summary": ["{org} ne {date} ko {loc} mein convocation ceremony organise ki, jiski adhyakshata vice-chancellor {person} ne ki.",
                        "Total {num} students ko degrees di gayi.",
                        "Fees badhane ka proposal pass kiya {pol}."],
            "claims": ["{person} {org} ke vice-chancellor hain.", "Convocation ceremony {loc} mein hui.",
                       "Convocation ceremony {date} ko hui.", "{num} students ko degrees di gayi.",
                       "Fees badhane ka proposal pass kiya {pol}."],
        },
    },
    "environment": {
        "orgs": [("ज़िला आपदा राहत दल", "District Disaster Relief Team"), ("राज्य आपदा प्रबंधन प्राधिकरण", "State Disaster Management Authority"),
                 ("जल संसाधन विभाग", "Jal Sansadhan Vibhag"), ("नगर निगम आपात सेवा", "Nagar Nigam Emergency Service"),
                 ("राहत एवं बचाव प्रकोष्ठ", "Rahat evam Bachav Prakoshth")],
        "num": (50, 2000, 10), "num2": (5, 49, 1),
        "hi": {
            "pol": ("दिया", "नहीं दिया"),
            "title": "{loc} में बाढ़ जैसे हालात",
            "source": ["{date} को {loc} में भारी बारिश के बाद बाढ़ जैसे हालात बन गए।",
                       "{org} के अधिकारी {person} ने बताया कि {num} परिवारों को सुरक्षित स्थानों पर पहुँचाया गया।",
                       "ज़िले में {num2} राहत शिविर बनाए गए हैं।",
                       "मौसम विभाग ने अगले दो दिनों तक और बारिश की चेतावनी दी है।",
                       "प्रशासन ने स्कूलों को बंद करने का आदेश {pol}।"],
            "summary": ["{date} को {loc} में भारी बारिश से बाढ़ जैसे हालात बने, यह जानकारी {org} के अधिकारी {person} ने दी।",
                        "{num} परिवारों को सुरक्षित स्थानों पर पहुँचाया गया।",
                        "प्रशासन ने स्कूल बंद करने का आदेश {pol}।"],
            "claims": ["{loc} में बाढ़ जैसे हालात बने।", "बाढ़ जैसे हालात {date} को बने।",
                       "{person} {org} के अधिकारी हैं।", "{num} परिवारों को सुरक्षित स्थानों पर पहुँचाया गया।",
                       "प्रशासन ने स्कूल बंद करने का आदेश {pol}।"],
        },
        "hg": {
            "pol": ("diya", "nahi diya"),
            "title": "{loc} mein flood jaise halaat",
            "source": ["{date} ko {loc} mein heavy rain ke baad flood jaise halaat ban gaye.",
                       "{org} ke officer {person} ne bataya ki {num} families ko safe jagahon par shift kiya gaya.",
                       "District mein {num2} relief camps banaye gaye hain.",
                       "Weather department ne agle do din tak aur baarish ki warning di hai.",
                       "Administration ne schools band karne ka order {pol}."],
            "summary": ["{date} ko {loc} mein heavy rain se flood jaise halaat bane, yeh jaankari {org} ke officer {person} ne di.",
                        "{num} families ko safe jagahon par shift kiya gaya.",
                        "Administration ne schools band karne ka order {pol}."],
            "claims": ["{loc} mein flood jaise halaat bane.", "Flood jaise halaat {date} ko bane.",
                       "{person} {org} ke officer hain.", "{num} families ko safe jagahon par shift kiya gaya.",
                       "Administration ne schools band karne ka order {pol}."],
        },
    },
    "technology": {
        "orgs": [("कोडशाला", "CodeShala"), ("डिजीकिसान", "DigiKisan"), ("पेमित्र", "PayMitra"),
                 ("सीखो ऐप्स", "Seekho Apps"), ("भाषासेतु", "BhashaSetu")],
        "num": (10000, 500000, 1000), "num2": (20, 400, 1),
        "hi": {
            "pol": ("है", "नहीं है"),
            "title": "{org} ने लॉन्च किया नया ऐप",
            "source": ["{loc} स्थित स्टार्टअप {org} ने {date} को अपना नया मोबाइल ऐप लॉन्च किया।",
                       "कंपनी के संस्थापक {person} ने बताया कि पहले हफ़्ते में ऐप को {num} लोगों ने डाउनलोड किया।",
                       "कंपनी में अभी {num2} कर्मचारी काम करते हैं।",
                       "ऐप हिंदी और अंग्रेज़ी दोनों भाषाओं में उपलब्ध है।",
                       "ऐप के लिए कोई शुल्क लिया जाता {pol}।"],
            "summary": ["{loc} के स्टार्टअप {org} ने {date} को नया मोबाइल ऐप लॉन्च किया, जिसके संस्थापक {person} हैं।",
                        "पहले हफ़्ते में ऐप को {num} लोगों ने डाउनलोड किया।",
                        "ऐप के लिए कोई शुल्क लिया जाता {pol}।"],
            "claims": ["{org} {loc} का स्टार्टअप है।", "{org} ने {date} को नया मोबाइल ऐप लॉन्च किया।",
                       "{person} {org} के संस्थापक हैं।", "पहले हफ़्ते में ऐप को {num} लोगों ने डाउनलोड किया।",
                       "ऐप के लिए कोई शुल्क लिया जाता {pol}।"],
        },
        "hg": {
            "pol": ("hai", "nahi hai"),
            "title": "{org} ne launch kiya naya app",
            "source": ["{loc} based startup {org} ne {date} ko apna naya mobile app launch kiya.",
                       "Company ke founder {person} ne bataya ki pehle hafte mein app ko {num} logon ne download kiya.",
                       "Company mein abhi {num2} employees kaam karte hain.",
                       "App Hindi aur English dono languages mein available hai.",
                       "App ke liye koi fee li jaati {pol}."],
            "summary": ["{loc} ke startup {org} ne {date} ko naya mobile app launch kiya, jiske founder {person} hain.",
                        "Pehle hafte mein app ko {num} logon ne download kiya.",
                        "App ke liye koi fee li jaati {pol}."],
            "claims": ["{org} {loc} ka startup hai.", "{org} ne {date} ko naya mobile app launch kiya.",
                       "{person} {org} ke founder hain.", "Pehle hafte mein app ko {num} logon ne download kiya.",
                       "App ke liye koi fee li jaati {pol}."],
        },
    },
    "infrastructure": {
        "orgs": [("लोक निर्माण विभाग", "Lok Nirman Vibhag"), ("शहरी विकास प्राधिकरण", "Shehri Vikas Pradhikaran"),
                 ("राज्य सेतु निगम", "Rajya Setu Nigam"), ("मेट्रो रेल निगम", "Metro Rail Nigam"),
                 ("राजमार्ग विकास बोर्ड", "Rajmarg Vikas Board")],
        "num": (40, 900, 5), "num2": (500, 3000, 50),
        "hi": {
            "pol": ("हुई", "नहीं हुई"),
            "title": "{loc} में नए फ़्लाईओवर का उद्घाटन",
            "source": ["{org} ने {date} को {loc} में नए फ़्लाईओवर का उद्घाटन किया।",
                       "उद्घाटन समारोह में परियोजना निदेशक {person} मौजूद थे।",
                       "इस परियोजना पर कुल {num} करोड़ रुपये की लागत आई।",
                       "फ़्लाईओवर की लंबाई लगभग {num2} मीटर है।",
                       "अधिकारियों के अनुसार परियोजना तय समय पर पूरी {pol}।"],
            "summary": ["{org} ने {date} को {loc} में नए फ़्लाईओवर का उद्घाटन किया, जहाँ परियोजना निदेशक {person} मौजूद थे।",
                        "परियोजना पर {num} करोड़ रुपये की लागत आई।",
                        "परियोजना तय समय पर पूरी {pol}।"],
            "claims": ["{org} ने नए फ़्लाईओवर का उद्घाटन किया।", "फ़्लाईओवर {loc} में है।",
                       "उद्घाटन {date} को हुआ।", "{person} परियोजना निदेशक हैं।",
                       "परियोजना पर {num} करोड़ रुपये की लागत आई।", "परियोजना तय समय पर पूरी {pol}।"],
        },
        "hg": {
            "pol": ("hui", "nahi hui"),
            "title": "{loc} mein naye flyover ka udghatan",
            "source": ["{org} ne {date} ko {loc} mein naye flyover ka inauguration kiya.",
                       "Inauguration ceremony mein project director {person} maujood the.",
                       "Is project par total {num} crore rupaye ki cost aayi.",
                       "Flyover ki length lagbhag {num2} meter hai.",
                       "Officials ke mutabik project time par poori {pol}."],
            "summary": ["{org} ne {date} ko {loc} mein naye flyover ka inauguration kiya, jahan project director {person} maujood the.",
                        "Project par {num} crore rupaye ki cost aayi.",
                        "Project time par poori {pol}."],
            "claims": ["{org} ne naye flyover ka inauguration kiya.", "Flyover {loc} mein hai.",
                       "Inauguration {date} ko hua.", "{person} project director hain.",
                       "Project par {num} crore rupaye ki cost aayi.", "Project time par poori {pol}."],
        },
    },
}

FILLERS = {
    "hi": ["स्थानीय लोगों ने इस पहल का स्वागत किया।",
           "इस बारे में आगे की जानकारी जल्द साझा की जाएगी।",
           "कार्यक्रम के दौरान सुरक्षा के कड़े इंतज़ाम किए गए थे।",
           "सोशल मीडिया पर भी इस ख़बर की काफ़ी चर्चा रही।",
           "विशेषज्ञों का मानना है कि इसका असर आने वाले महीनों में दिखेगा।",
           "मीडिया से बातचीत में अधिकारियों ने संतोष जताया।"],
    "hg": ["Local logon ne is pehal ka swagat kiya.",
           "Is baare mein aage ki jaankari jald share ki jayegi.",
           "Event ke dauraan security ke tight intezaam kiye gaye the.",
           "Social media par bhi is khabar ki kaafi charcha rahi.",
           "Experts ka maanna hai ki iska asar aane wale mahino mein dikhega.",
           "Media se baat karte hue officials ne satisfaction jataya."],
}

# Sentences used for "unsupported_addition" errors: plausible but absent from the source.
ADDITIONS = {
    "hi": ["इस मौके पर मुख्य अतिथि के रूप में {person} भी मौजूद थे।",
           "इसके लिए {num} करोड़ रुपये का अतिरिक्त बजट भी मंज़ूर किया गया।",
           "अगला कार्यक्रम {date} को {loc} में होगा।",
           "इस मामले की जाँच के लिए एक समिति भी बनाई गई है।"],
    "hg": ["Is mauke par chief guest ke roop mein {person} bhi maujood the.",
           "Iske liye {num} crore rupaye ka extra budget bhi approve kiya gaya.",
           "Agla program {date} ko {loc} mein hoga.",
           "Is maamle ki jaanch ke liye ek committee bhi banayi gayi hai."],
}

# Spelling-noise rules, applied ONLY to template words in the SOURCE (never to slot values).
NOISE_HG = {"hai": "he", "hain": "hen", "kiya": "kia", "mein": "me", "nahi": "nahin",
            "ke": "k", "logon": "logo", "baarish": "barish", "saal": "sal",
            "bataya": "btaya", "liye": "lie", "kaha": "kha", "yeh": "ye", "baad": "bad"}
NOISE_HI = {"में": "मे", "हैं": "है", "किए": "किये", "गए": "गये", "गईं": "गयीं", "लिए": "लिये"}
NUKTA = "़"

DEV_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")
ERROR_TYPES = ["number_swap", "date_swap", "entity_swap", "negation", "unsupported_addition"]
EXPECTED_NLI = {"none": "entailment", "number_swap": "contradiction", "date_swap": "contradiction",
                "entity_swap": "contradiction", "negation": "contradiction",
                "unsupported_addition": "neutral"}
SLOT_RE = re.compile(r"\{(\w+)\}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def render(template: str, values: dict[str, str]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Fill {slot}s and return (text, {slot: (start, end)}) for the LAST occurrence of each slot."""
    out, spans, pos = [], {}, 0
    for m in SLOT_RE.finditer(template):
        out.append(template[pos:m.start()])
        start = sum(len(p) for p in out)
        val = values[m.group(1)]
        out.append(val)
        spans[m.group(1)] = (start, start + len(val))
        pos = m.end()
    out.append(template[pos:])
    return "".join(out), spans


def render_sentences(sentences: list[str], values: dict[str, str]) -> tuple[str, dict]:
    text, spans, offset = "", {}, 0
    for i, s in enumerate(sentences):
        if i:
            text += " "
            offset += 1
        t, sp = render(s, values)
        for k, (a, b) in sp.items():
            spans[k] = (a + offset, b + offset)
        text += t
        offset += len(t)
    return text, spans


def add_noise(template: str, lang: str, rng: random.Random, p: float = 0.5) -> str:
    """Apply informal spelling variants to template words (slot placeholders untouched)."""
    table = NOISE_HG if lang == "hg" else NOISE_HI
    words = template.split(" ")
    for i, w in enumerate(words):
        if "{" in w:
            continue
        core = w.rstrip(".।,")
        tail = w[len(core):]
        low = core.lower()
        if low in table and rng.random() < p:
            new = table[low]
            if core[:1].isupper():
                new = new.capitalize()
            words[i] = new + tail
        elif lang == "hi" and rng.random() < p:
            stripped = unicodedata.normalize("NFD", core).replace(NUKTA, "")
            stripped = unicodedata.normalize("NFC", stripped)
            if stripped != unicodedata.normalize("NFC", core):
                words[i] = stripped + tail
    return " ".join(words)


def fmt_date(d: int, m: int, y: int, lang: str) -> str:
    return f"{d} {MONTHS[m][0 if lang == 'hi' else 1]} {y}"


def sample_num(rng: random.Random, rng_spec, avoid: set[int]) -> int:
    lo, hi, step = rng_spec
    while True:
        n = rng.randrange(lo, hi + 1, step)
        if all(abs(n - a) >= max(step, 0.1 * max(a, 1)) for a in avoid):
            return n


# ---------------------------------------------------------------------------
# Article generation
# ---------------------------------------------------------------------------
def make_articles(seed: int = 42, per_cell: int = 8, dev_frac: float = 0.3) -> list[dict]:
    rng = random.Random(seed)
    articles = []
    for lang, lang_name, script in [("hi", "hindi", "devanagari"), ("hg", "hinglish", "latin")]:
        li = 0 if lang == "hi" else 1
        domains = list(DOMAINS)
        # dev count per (lang, domain): alternate 3/2 so that overall dev ~= 31 %
        three_dev = set(rng.sample(domains, len(domains) // 2))
        counter = 0
        for domain in domains:
            spec = DOMAINS[domain]
            t = spec[lang]
            idxs = list(range(per_cell))
            rng.shuffle(idxs)
            n_dev = 3 if domain in three_dev else 2
            dev_idx = set(idxs[:n_dev])
            for k in range(per_cell):
                counter += 1
                aid = f"{lang}{counter:03d}"
                pi = rng.randrange(len(PERSONS))
                oi = rng.randrange(len(spec["orgs"]))
                lo = rng.randrange(len(LOCATIONS))
                num = sample_num(rng, spec["num"], set())
                num2 = sample_num(rng, spec["num2"], {num})
                d, m, y = rng.randint(1, 28), rng.randrange(12), rng.randint(2023, 2025)
                negative = rng.random() < 0.5
                values = {
                    "person": PERSONS[pi][li], "org": spec["orgs"][oi][li], "loc": LOCATIONS[lo][li],
                    "date": fmt_date(d, m, y, lang), "num": str(num), "num2": str(num2),
                    "pol": t["pol"][1 if negative else 0],
                }
                # source digit script + spelling noise (Hindi: half the articles use Devanagari digits)
                digit_script = "devanagari" if (lang == "hi" and rng.random() < 0.5) else "western"
                noisy = rng.random() < 0.5
                src_templates = list(t["source"]) + rng.sample(FILLERS[lang], 2)
                if noisy:
                    src_templates = [add_noise(s, lang, rng) for s in src_templates]
                text, _ = render_sentences(src_templates, values)
                if digit_script == "devanagari":
                    text = text.translate(DEV_DIGITS)
                summary, sum_spans = render_sentences(t["summary"], values)
                claims = [render(c, values)[0] for c in t["claims"]]
                key_facts = [
                    {"type": "entity", "slot": "person", "value": values["person"]},
                    {"type": "entity", "slot": "org", "value": values["org"]},
                    {"type": "entity", "slot": "loc", "value": values["loc"]},
                    {"type": "number", "slot": "num", "value": values["num"]},
                    {"type": "date", "slot": "date", "value": values["date"]},
                ]
                articles.append({
                    "article_id": aid, "language": lang_name, "script": script, "domain": domain,
                    "split": "dev" if k in dev_idx else "test",
                    "title": render(t["title"], values)[0], "text": text, "summary": summary,
                    "gold_claims": claims, "key_facts": key_facts,
                    "source_digit_script": digit_script, "source_spelling_noise": noisy,
                    # private fields used only for error injection (dropped before saving)
                    "_values": values, "_spans": sum_spans, "_idx": (pi, oi, lo, num, num2, d, m, y, negative),
                })
    return articles


# ---------------------------------------------------------------------------
# Error injection
# ---------------------------------------------------------------------------
def inject(article: dict, etype: str, rng: random.Random) -> dict:
    lang = "hi" if article["language"] == "hindi" else "hg"
    li = 0 if lang == "hi" else 1
    spec = DOMAINS[article["domain"]]
    pi, oi, lo, num, num2, d, m, y, negative = article["_idx"]
    ref, spans, vals = article["summary"], article["_spans"], article["_values"]

    if etype == "unsupported_addition":
        new_vals = {
            "person": PERSONS[rng.choice([i for i in range(len(PERSONS)) if i != pi])][li],
            "num": str(rng.randrange(5, 500, 5)),
            "date": fmt_date(rng.randint(1, 28), rng.randrange(12), y + 1, lang),
            "loc": LOCATIONS[rng.choice([i for i in range(len(LOCATIONS)) if i != lo])][li],
        }
        added = render(rng.choice(ADDITIONS[lang]), new_vals)[0]
        cand = ref + " " + added
        return dict(error_slot="addition", span_start=len(ref) + 1, span_end=len(cand),
                    original_value="", injected_value=added, candidate_summary=cand)

    if etype == "number_swap":
        slot, new = "num", str(sample_num(rng, spec["num"], {num, num2}))
    elif etype == "date_swap":
        slot = "date"
        if rng.random() < 0.5:
            new = fmt_date(rng.choice([x for x in range(1, 29) if x != d]), m, y, lang)
        else:
            new = fmt_date(d, rng.choice([x for x in range(12) if x != m]), y, lang)
    elif etype == "entity_swap":
        slot = rng.choice(["person", "org", "loc"])
        pool, cur = {"person": (PERSONS, pi), "org": (spec["orgs"], oi), "loc": (LOCATIONS, lo)}[slot]
        new = pool[rng.choice([i for i in range(len(pool)) if i != cur])][li]
    elif etype == "negation":
        slot = "pol"
        new = DOMAINS[article["domain"]][lang]["pol"][0 if negative else 1]
    else:
        raise ValueError(etype)

    a, b = spans[slot]
    cand = ref[:a] + new + ref[b:]
    return dict(error_slot=slot, span_start=a, span_end=a + len(new),
                original_value=ref[a:b], injected_value=new, candidate_summary=cand)


def make_errors(articles: list[dict], seed: int = 42) -> list[dict]:
    rng = random.Random(seed + 1)
    order = list(range(len(articles)))
    rng.shuffle(order)
    plan = {}
    for rank, i in enumerate(order):  # balanced: each article gets 3 distinct types, cycling
        plan[i] = [ERROR_TYPES[(3 * rank + j) % len(ERROR_TYPES)] for j in range(3)]
    rows = []
    for i, art in enumerate(articles):
        base = {"article_id": art["article_id"], "language": art["language"], "domain": art["domain"],
                "split": art["split"], "source_text": art["text"], "reference_summary": art["summary"]}
        rows.append({"sample_id": f"{art['article_id']}-C", **base,
                     "candidate_summary": art["summary"], "label": "CORRECT", "error_type": "none",
                     "error_slot": "none", "span_start": -1, "span_end": -1,
                     "original_value": "", "injected_value": "", "expected_nli": "entailment"})
        for j, et in enumerate(plan[i], start=1):
            e = inject(art, et, rng)
            rows.append({"sample_id": f"{art['article_id']}-E{j}", **base,
                         "candidate_summary": e["candidate_summary"], "label": "ERROR", "error_type": et,
                         "error_slot": e["error_slot"], "span_start": e["span_start"], "span_end": e["span_end"],
                         "original_value": e["original_value"], "injected_value": e["injected_value"],
                         "expected_nli": EXPECTED_NLI[et]})
    return rows


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")


def generate(articles_path: Path, errors_path: Path, seed: int = 42) -> tuple[int, int]:
    arts = make_articles(seed)
    errs = make_errors(arts, seed)
    write_jsonl(arts, articles_path)
    write_jsonl(errs, errors_path)
    return len(arts), len(errs)


if __name__ == "__main__":
    from src.config import load_config, ROOT

    cfg = load_config()
    n_a, n_e = generate(ROOT / cfg["data"]["articles"], ROOT / cfg["data"]["errors"], cfg["seed"])
    print(f"Wrote {n_a} articles -> {cfg['data']['articles']}")
    print(f"Wrote {n_e} error rows -> {cfg['data']['errors']}")

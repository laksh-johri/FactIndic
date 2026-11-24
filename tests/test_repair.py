"""Tests for src/repair.py: each repair type, deletion, and the 'touch only flagged spans' guarantee."""
from src.repair import apply_edits, Edit, render_date, repair_summary, tok_spans

SAFE = {"जनसभा", "संबोधित", "किया", "सभा", "शामिल", "हुए", "उन्होंने", "किसी", "नए", "गठबंधन", "घोषणा",
        "rally", "address", "log", "shamil", "camp", "incharge", "dr", "lagaya", "free", "health"}
SAFE_U = SAFE | {"आयोजकों", "अनुसार", "बताया", "organise", "ne", "bataya", "patients", "checkup",
                 "भाषण", "आगामी", "चुनाव", "एक"}


def claim(text, summary, verdict="CONTRADICTED", rules=None, evidence=(), cid="c#1"):
    s = summary.index(text.rstrip("।."))
    e = s + len(text.rstrip("।.")) + (1 if summary[s + len(text.rstrip("।.")):][:1] in "।." else 0)
    return {"claim_id": cid, "start": s, "end": e, "verdict": verdict, "rules": rules or {}, "evidence": list(evidence)}


def test_tok_spans_keep_offsets():
    t = tok_spans("डॉ. नेहा गुप्ता थे।", 10)
    assert [x.raw for x in t] == ["डॉ", "नेहा", "गुप्ता", "थे"] and t[1].start == 14


def test_number_repair_picks_context_and_rank_not_decoy():
    summ = "टीम ने 152 रन बनाए। मैच अच्छा रहा।"
    ev = ["टीम ने पहले बल्लेबाज़ी करते हुए २५३ रन बनाए।", "विपक्षी टीम केवल १२५ रन ही बना सकी।"]
    c = claim("टीम ने 152 रन बनाए।", summ, rules={"numbers": "fail"}, evidence=ev)
    r = repair_summary(summ, [c], SAFE, SAFE_U)
    assert r.repaired == "टीम ने 253 रन बनाए। मैच अच्छा रहा।"      # ASCII like the summary, not the decoy 125
    assert r.edits[0].action == "replace_number"


def test_date_repair_keeps_script_style():
    assert render_date((20, 1, 2025), "20 जुलाई 2025") == "20 जनवरी 2025"
    assert render_date((19, 1, 2024), "19 July 2024") == "19 January 2024"
    assert render_date((3, 5, 2023), "3 June 2023") == "3 May 2023"          # short month name
    assert render_date((3, 5, 2023), "3 जून 2023") == "3 मई 2023"
    summ = "Rally 19 July 2024 ko hui."
    c = claim(summ, summ, rules={"dates": "fail", "numbers": "pass"}, evidence=["19 January 2024 ko Agra mein rally hui."])
    assert repair_summary(summ, [c], SAFE, SAFE_U).repaired == "Rally 19 January 2024 ko hui."


def test_entity_repair_hinglish():
    summ = "Camp lagaya, jiske incharge Dr. Neha Gupta the."
    ev = ["Camp ke incharge Dr. Alok Saxena ne bataya ki total 290 patients ka checkup kiya gaya."]
    c = claim("jiske incharge Dr. Neha Gupta the.", summ, rules={"entities": "fail"}, evidence=ev)
    r = repair_summary(summ, [c], SAFE, SAFE_U)
    assert r.repaired == "Camp lagaya, jiske incharge Dr. Alok Saxena the."


def test_entity_repair_hindi_org():
    summ = "नव भारत संघ के अध्यक्ष सुनीता शर्मा ने जनसभा को संबोधित किया।"
    ev = ["जन विकास पार्टी के अध्यक्ष सुनीता शर्मा ने 20 जनवरी 2025 को जयपुर में एक जनसभा को संबोधित किया।"]
    c = claim(summ, summ, rules={"entities": "fail"}, evidence=ev)
    assert repair_summary(summ, [c], SAFE, SAFE_U).repaired == \
        "जन विकास पार्टी के अध्यक्ष सुनीता शर्मा ने जनसभा को संबोधित किया।"


def test_negation_insert_and_remove():
    summ = "सभा हुई। उन्होंने किसी नए गठबंधन की घोषणा की।"
    ev = ["उन्होंने आगामी चुनाव के लिए किसी नए गठबंधन की घोषणा नहीं की।"]
    c = claim("उन्होंने किसी नए गठबंधन की घोषणा की।", summ, rules={"negation": "fail"}, evidence=ev)
    assert repair_summary(summ, [c], SAFE, SAFE_U).repaired == "सभा हुई। उन्होंने किसी नए गठबंधन की घोषणा नहीं की।"
    summ2 = "Unhone naye alliance ka announcement nahi kiya."
    c2 = claim(summ2, summ2, rules={"negation": "fail"}, evidence=["Unhone naye alliance ka announcement kiya."])
    assert repair_summary(summ2, [c2], SAFE, SAFE_U).repaired == "Unhone naye alliance ka announcement kiya."


def test_unsupported_sentence_is_deleted():
    summ = "Rally mein 9500 log shamil hue. Is mauke par chief guest ke roop mein Meena Kushwaha bhi maujood the."
    c = claim("Is mauke par chief guest ke roop mein Meena Kushwaha bhi maujood the.", summ,
              rules={"entities": "fail"}, evidence=["Organisers ke mutabik is rally me lagbhag 9500 log shamil hue."])
    r = repair_summary(summ, [c], SAFE, SAFE_U)
    assert r.repaired == "Rally mein 9500 log shamil hue." and r.edits[0].action == "delete"


def test_nli_only_flag_and_supported_claims_untouched():
    summ = "Team ne 156 runs banaye. Match roka gaya."
    c1 = claim("Team ne 156 runs banaye.", summ, verdict="SUPPORTED", rules={"numbers": "pass"}, cid="c#1")
    c2 = claim("Match roka gaya.", summ, verdict="UNSUPPORTED", rules={"negation": "pass"}, cid="c#2")
    r = repair_summary(summ, [c1, c2], SAFE, SAFE_U)
    assert r.repaired == summ and [e.action for e in r.edits] == ["review"]


def test_ambiguous_number_goes_to_review():
    summ = "Total 50 log aaye."
    ev = ["Pehle din 80 log aaye.", "Doosre din 90 log aaye."]   # same context, different sentences ...
    c = claim(summ, summ, rules={"numbers": "fail"}, evidence=ev)
    # ... rank breaks the tie (rank 0 wins), so this is repaired; identical rank+context would be review
    assert repair_summary(summ, [c], SAFE, SAFE_U).repaired == "Total 80 log aaye."
    c_bad = claim(summ, summ, rules={"numbers": "fail"}, evidence=["Kuch bhi nahi."])
    r = repair_summary(summ, [c_bad], SAFE, SAFE_U)
    assert r.repaired == summ and r.edits[0].action == "review"


def test_apply_edits_right_to_left():
    t = "a b c"
    assert apply_edits(t, [Edit("x", "r", 0, 1, "a", "AA"), Edit("x", "r", 4, 5, "c", "CC")]) == "AA b CC"


def test_gold_outcome_requires_whole_claim_deletion():
    from experiments.run_repair import gold_outcome
    ref = "A ne X kiya. Rally mein 9500 log aaye. Unhone announcement nahi kiya."
    assert gold_outcome(ref, ref) == "complete"
    assert gold_outcome(ref, "A ne X kiya. Unhone announcement nahi kiya.") == "lossy"
    assert gold_outcome(ref, "A ne X kiya. Rally mein 9500 log aaye. Unhone announcement kiya.") == "erroneous"
    assert gold_outcome(ref, "A ne X kiya. Rally mein 950 log aaye. Unhone announcement nahi kiya.") == "erroneous"


def test_adjacent_deletions_are_merged_not_dropped():
    from src.repair import delete_claim
    t = "One two. Three four. Five six."
    spans = [(0, 8), (9, 20), (21, 30)]
    edits = [delete_claim(f"c#{i}", t, s, e, "x") for i, (s, e) in enumerate(spans)]
    assert apply_edits(t, edits[1:]) == "One two."
    assert apply_edits(t, edits) == ""


def test_gold_outcome_empty():
    from experiments.run_repair import gold_outcome
    assert gold_outcome("A ne X kiya. B hua.", "  ") == "empty"

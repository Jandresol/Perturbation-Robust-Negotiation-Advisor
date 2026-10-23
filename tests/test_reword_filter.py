"""Acceptance filter. NLI and encoder tests download the models on first run."""

from negotiator.reword import filter as accept

ORIGINAL = "The Mayor said FWB may deliver 40 tonnes of food to the camp each week."
PARAPHRASE = "According to the Mayor, FWB is allowed to bring 40 tonnes of food into the camp every week."


def test_hard_facts_accepts_paraphrase():
    assert accept.hard_facts_ok(ORIGINAL, PARAPHRASE)


def test_hard_facts_rejects_changed_number():
    assert not accept.hard_facts_ok(ORIGINAL, PARAPHRASE.replace("40", "50"))


def test_hard_facts_rejects_changed_name():
    assert not accept.hard_facts_ok(ORIGINAL, PARAPHRASE.replace("FWB", "MASHA"))


def test_hard_facts_number_words_and_percent():
    assert accept.hard_facts_ok("Rations fell by 5% over three days.",
                                "Over 3 days, rations dropped by 5 percent.")


def test_nli_paraphrase_passes(cfg):
    fc = cfg["filter"]
    assert accept.entailment(ORIGINAL, PARAPHRASE, fc) >= fc["nli_threshold"]
    assert accept.entailment(PARAPHRASE, ORIGINAL, fc) >= fc["nli_threshold"]


def test_nli_negation_fails(cfg):
    fc = cfg["filter"]
    negated = "The Mayor said FWB may not deliver 40 tonnes of food to the camp each week."
    assert accept.entailment(ORIGINAL, negated, fc) < fc["nli_threshold"]


def test_check_accepts_paraphrase(cfg):
    result = accept.check(ORIGINAL, PARAPHRASE, cfg["filter"])
    assert result["accepted"], result


DOC = ("4. Meeting notes. The Mayor said FWB may deliver 40 tonnes of food each week. "
       "The guards have not been paid for three months. MASHA asked for access to the camp. "
       "The Camp Commander wants to stay visibly in charge. Fuel for the generators runs out on Friday.")


def test_doc_matches_itself(cfg):
    assert accept.check(DOC, DOC, cfg["filter"])["accepted"]


def test_doc_with_dropped_sentence_fails_nli(cfg):
    dropped = DOC.replace(" MASHA asked for access to the camp.", "")
    result = accept.check(DOC, dropped, cfg["filter"])
    assert not result["accepted"] and result["nli_bwd"] < cfg["filter"]["nli_threshold"]


def test_hard_facts_line_starts_and_list_markers():
    post = "Wtf?! Why is HfA leaving?\nGiven the war, nobody is safe.\n1. Source: WHO report"
    reworded = "What?! How come HfA is leaving?\nBecause of the war, nobody is safe.\nSource: WHO report"
    assert accept.hard_facts_ok(post, reworded)


def test_hard_facts_ignores_title_case_and_common_words():
    original = ("International Staff of Health for All (HfA) Detained by Tribespeople\n"
                "After nine months, the staff were detained. Tribespeople blocked the road.")
    reworded = ("Tribespeople Hold International Staff of Health for All (HfA)\n"
                "Once nine months had passed, the staff were held. The road was blocked by tribespeople.")
    assert accept.hard_facts_ok(original, reworded)
    assert not accept.hard_facts_ok(original, reworded.replace("(HfA)", "(WHO)"))

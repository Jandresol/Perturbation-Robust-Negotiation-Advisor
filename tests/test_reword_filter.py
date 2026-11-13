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


def test_nli_trailing_ellipsis_passes(cfg):
    # Sim 2 role card: the cross-encoder scored this identical pair 0.002 before normalising "…".
    fc = cfg["filter"]
    line = "These are the thoughts on your mind when a new negotiator reaches out from FWB…"
    assert accept.entailment(line, line, fc) >= fc["nli_threshold"]
    assert accept.entailment(line, line.replace("reaches out from FWB", "from FWB reaches out"), fc) >= fc["nli_threshold"]


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


def test_hard_facts_transcripts_and_logs():
    original = ("Militia Leader: Tell FWB I’m not moving. Got it? So we wait — Then we act.\n"
                "001 1 May 11:16 | Man from Compound 2 found with matches.")
    reworded = ("Militia Leader: Let FWB know I'll stay put. Understood? We wait — Next we act.\n"
                "001 1 May 11:16 | Unauthorized matches found on a man from Compound 2.")
    assert accept.hard_facts_ok(original, reworded)
    assert not accept.hard_facts_ok(original, reworded.replace("FWB", "MASHA"))


def test_force_classes_catch_red_line_edits_and_allow_synonyms():
    same = [("Staff must remain on site.", "Staff are required to stay on site."),
            ("Staff must not leave the compound.", "Staff are prohibited from leaving the compound."),
            ("No one may enter without approval.", "Nobody may enter without permission.")]
    changed = [("Staff must remain on site.", "Staff may remain on site."),
               ("All families must be moved together.", "Some families must be moved together."),
               ("Transfers are authorised by the Mayor.", "Transfers are not authorised by the Mayor."),
               ("Only documented citizens may be transported.", "Documented citizens may be transported.")]
    assert all(accept.force_classes(a) == accept.force_classes(b) for a, b in same)
    assert all(accept.force_classes(a) != accept.force_classes(b) for a, b in changed)


def test_force_check_applies_to_red_lines_only(monkeypatch, cfg):
    monkeypatch.setattr(accept, "cosine", lambda a, b, enc: 0.99)
    monkeypatch.setattr(accept, "entailment", lambda p, h, c: 0.99)   # suppose NLI missed it
    original, edited = "Staff must remain on site.", "Staff may remain on site."
    assert accept.check(original, edited, cfg["filter"])["accepted"]
    result = accept.check(original, edited, cfg["filter"], red_line=True)
    assert not result["accepted"] and result["reject_reason"] == "red_line_force" and not result["hard_facts_ok"]

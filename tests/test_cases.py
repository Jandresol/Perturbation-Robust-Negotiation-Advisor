from negotiator.game import sentence_test as st
from negotiator.game.cases import package_from_passages


def test_passage_package_holds_each_study_sentence_once():
    passages = [
        {"id": "sim2-1", "case": "sim2", "text": "If FWB hires local independent laborers, you cannot trust those people."},
        {"id": "sim2-2", "case": "sim2", "text": "Guards must be responsible for organizing the distribution."},
    ]
    package = package_from_passages("sim2", passages)
    case = {"sources": package["sources"], "facts": [], "parties": package["parties"], "actors": {}}
    assert package["parties"]["us"] == "Camp Commander"
    assert package["facts"] == []
    for passage in passages:
        assert st.holders(case, passage) == ["source-00"]

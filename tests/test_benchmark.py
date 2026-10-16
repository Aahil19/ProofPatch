from pathlib import Path

from benchmarks.catalog import SCENARIOS

ROOT = Path(__file__).resolve().parents[1]


def test_corpus_has_thirty_unique_cases_across_three_projects():
    assert len(SCENARIOS) == 30
    assert len({scenario.id for scenario in SCENARIOS}) == 30
    assert {scenario.project for scenario in SCENARIOS} == {"textops", "dataops", "apiops"}
    assert all(
        sum(case.project == project for case in SCENARIOS) == 10
        for project in ("textops", "dataops", "apiops")
    )


def test_every_seed_and_candidate_is_anchored_to_real_source():
    for scenario in SCENARIOS:
        source = (ROOT / "benchmarks" / "projects" / scenario.project / scenario.file).read_text()
        assert source.count(scenario.correct) == 1, scenario.id
        assert scenario.buggy not in source, scenario.id
        assert 1 <= len(scenario.candidates) <= 2
        assert scenario.candidates[-1] == scenario.correct or scenario.expected == "escalated"


def test_expected_policy_distribution():
    assert sum(len(scenario.candidates) == 1 for scenario in SCENARIOS) == 21
    assert sum(len(scenario.candidates) == 2 for scenario in SCENARIOS) == 9
    assert sum(scenario.expected == "escalated" for scenario in SCENARIOS) == 3

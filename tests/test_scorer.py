"""Tests for scorer.py — gate, scoring, breakdown structure."""

from scorer import score_procurement, sector_gate


class TestSectorGate:
    def test_blocked_sector(self):
        passed, reason = sector_gate(title="EKG-system for sjukhus")
        assert not passed
        assert "Blockerad sektor" in reason

    def test_no_education_signal(self):
        passed, reason = sector_gate(title="Kontorsstolar och skrivbord")
        assert not passed
        assert "Ingen utbildnings" in reason

    def test_education_keyword_passes(self):
        passed, reason = sector_gate(title="Ledarskapsutbildning for chefer")
        assert passed

    def test_education_cpv_passes(self):
        passed, reason = sector_gate(cpv_codes="80532000")
        assert passed

    def test_blocked_overrides_education(self):
        passed, reason = sector_gate(
            title="Ledarskapsutbildning",
            description="EKG-system och medicinsk programvara",
        )
        assert not passed


class TestScoring:
    def test_irrelevant_scores_zero(self):
        score, rationale, breakdown = score_procurement(title="Asfaltering av vagar")
        assert score == 0
        assert not breakdown["gate_passed"]

    def test_relevant_scores_positive(self):
        score, rationale, breakdown = score_procurement(
            title="Ledarskapsutbildning for offentlig sektor",
            description="Chefsutbildning och teamutveckling",
        )
        assert score > 0
        assert breakdown["gate_passed"]
        assert len(breakdown["keyword_matches"]) > 0

    def test_high_relevance_scores_high(self):
        score, rationale, breakdown = score_procurement(
            title="Executive coaching och ledarskapsutveckling",
            description="Chefsutveckling, teamutveckling, organisationsutveckling",
            buyer="Region Stockholm",
            cpv_codes="80532000,79633000",
        )
        assert score >= 50
        assert breakdown["buyer_bonus"] > 0
        assert len(breakdown["cpv_matches"]) > 0

    def test_score_capped_at_100(self):
        score, rationale, breakdown = score_procurement(
            title="ledarskapsutbildning ledarskapsutveckling chefsutveckling chefsutbildning executive coaching",
            description="teamutveckling organisationsutveckling kommunikationsutbildning personaleffektivitet "
                        "forhandlingsledning coaching coachning handledning mentorskap kompetensutveckling "
                        "medarbetarutveckling personalutveckling organisationsforandring forandringsarbete "
                        "arbetsmiljo stresshantering konflikthantering feedbackkultur gruppdynamik teambuilding "
                        "seminarium workshop forelasning ledarskap medarbetarskap arbetskultur",
            buyer="Region Stockholm",
            cpv_codes="80532000,79633000,79998000,80511000",
        )
        assert score <= 100

    def test_buyer_bonus_for_known_buyer(self):
        score_with, _, bd_with = score_procurement(
            title="Ledarskapsutbildning",
            buyer="Region Skane",
        )
        score_without, _, bd_without = score_procurement(
            title="Ledarskapsutbildning",
            buyer="Acme Corp",
        )
        assert bd_with["buyer_bonus"] == 8
        assert bd_without["buyer_bonus"] == 0
        assert score_with > score_without


class TestBreakdownStructure:
    def test_breakdown_keys(self):
        _, _, breakdown = score_procurement(title="Ledarskapsutbildning")
        assert "gate_passed" in breakdown
        assert "gate_reason" in breakdown
        assert "keyword_matches" in breakdown
        assert "cpv_matches" in breakdown
        assert "buyer_bonus" in breakdown
        assert "total" in breakdown

    def test_blocked_breakdown(self):
        _, _, breakdown = score_procurement(title="Busstrafik i Skane")
        assert not breakdown["gate_passed"]
        assert breakdown["keyword_matches"] == []
        assert breakdown["total"] == 0

    def test_keyword_match_shape(self):
        _, _, breakdown = score_procurement(
            title="Executive coaching program",
        )
        for match in breakdown["keyword_matches"]:
            assert "keyword" in match
            assert "weight" in match
            assert isinstance(match["weight"], int)

    def test_cpv_match_shape(self):
        _, _, breakdown = score_procurement(
            title="Ledarskapsutbildning",
            cpv_codes="80532000",
        )
        for match in breakdown["cpv_matches"]:
            assert "code" in match
            assert "bonus" in match
            assert isinstance(match["bonus"], int)

"""Tests for scorer.py — gate, scoring, breakdown structure, bidrag profile."""

from scorer import score_procurement, sector_gate, UPPHANDLING_PROFILE, BIDRAG_PROFILE


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


class TestBidragScoring:
    """Tests for the bidrag scoring profile."""

    def test_bidrag_gate_passes_with_bidrag_keywords(self):
        score, rationale, breakdown = score_procurement(
            title="Utlysning: kompetensutveckling för omställning",
            description="Bidrag till ledarskapsutveckling i kommuner",
            record_type="bidrag",
        )
        assert score > 0
        assert breakdown["gate_passed"]

    def test_bidrag_gate_blocks_tech_fou(self):
        score, rationale, breakdown = score_procurement(
            title="Teknisk forskning inom halvledare",
            description="FoU-projekt för nanoteknik",
            record_type="bidrag",
        )
        assert score == 0
        assert not breakdown["gate_passed"]

    def test_bidrag_known_buyer_bonus(self):
        score_with, _, bd_with = score_procurement(
            title="Bidrag för kompetensutveckling",
            buyer="Vinnova",
            record_type="bidrag",
        )
        score_without, _, bd_without = score_procurement(
            title="Bidrag för kompetensutveckling",
            buyer="Okänd organisation",
            record_type="bidrag",
        )
        assert bd_with["buyer_bonus"] > 0
        assert bd_without["buyer_bonus"] == 0
        assert score_with > score_without

    def test_bidrag_cpv_ignored(self):
        """Bidrag profile has no CPV codes — should not give CPV bonus."""
        _, _, breakdown = score_procurement(
            title="Bidrag för kompetensutveckling",
            cpv_codes="80532000",
            record_type="bidrag",
        )
        assert breakdown["cpv_matches"] == []

    def test_upphandling_unchanged_with_default(self):
        """Default record_type=upphandling should use old profile."""
        score, _, breakdown = score_procurement(
            title="Ledarskapsutbildning for offentlig sektor",
            description="Chefsutbildning och teamutveckling",
            buyer="Region Stockholm",
            cpv_codes="80532000",
        )
        assert score > 0
        assert breakdown["gate_passed"]
        assert breakdown["buyer_bonus"] == 8
        assert len(breakdown["cpv_matches"]) > 0

    def test_bidrag_keywords_score_correctly(self):
        score, _, breakdown = score_procurement(
            title="Ledarskapsutveckling och organisationsutveckling",
            description="Bidrag för kompetensutveckling och förändringsledning i offentlig sektor",
            buyer="Tillväxtverket",
            record_type="bidrag",
        )
        assert score > 0
        kw_names = [m["keyword"] for m in breakdown["keyword_matches"]]
        assert "ledarskapsutveckling" in kw_names
        assert "organisationsutveckling" in kw_names

    def test_empty_description_scores_on_title_only(self):
        """Tillväxtverket items lack description — scoring should work on title alone."""
        score, _, breakdown = score_procurement(
            title="Utlysning: kompetensutveckling i offentlig sektor",
            description="",
            buyer="Tillväxtverket",
            record_type="bidrag",
        )
        assert score > 0
        assert breakdown["gate_passed"]

    def test_minimal_gate_signal_utlysning(self):
        """'utlysning' alone in title passes bidrag gate (it's in gate_keywords)."""
        score, _, breakdown = score_procurement(
            title="Utlysning om omställning",
            description="",
            record_type="bidrag",
        )
        assert breakdown["gate_passed"]

    def test_esf_buyer_bonus(self):
        """Europeiska socialfonden should give buyer bonus."""
        score_esf, _, bd_esf = score_procurement(
            title="Bidrag för kompetensutveckling",
            buyer="Europeiska socialfonden",
            record_type="bidrag",
        )
        assert bd_esf["buyer_bonus"] > 0

    def test_blocked_overrides_education_signal_bidrag(self):
        """Blocked sector should win even if education keywords are present."""
        score, _, breakdown = score_procurement(
            title="Systemutveckling och kompetensutveckling",
            description="Mjukvaruutveckling med utbildningsinsats",
            record_type="bidrag",
        )
        assert score == 0
        assert not breakdown["gate_passed"]
        assert "Blockerad" in breakdown["gate_reason"]

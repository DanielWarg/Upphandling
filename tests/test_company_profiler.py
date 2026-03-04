"""Tests for company_profiler.py — website fetching, AI profiling, keyword scoring, matching."""

import json

import httpx
import pytest

import db
from company_profiler import (
    _call_llm,
    fetch_website_text,
    profile_company,
    _keyword_score,
    match_company_to_bidrag,
    match_all_companies,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_company(tmp_db, name: str = "TestCo", url: str = "https://example.com") -> int:
    """Insert a company and return its id."""
    return db.create_company(name, url, "admin")


def _create_company_with_profile(tmp_db, name: str = "ProfiledCo", url: str = "https://example.com") -> int:
    """Insert a company with an AI profile and return its id."""
    cid = db.create_company(name, url, "admin")
    profile = {
        "bransch": "Konsult",
        "tjanster": ["ledarskapsutbildning", "coaching"],
        "kompetensomraden": ["ledarskap", "teamutveckling"],
        "nyckelord_for_bidrag": ["ledarskap", "utbildning", "coaching", "kompetensutveckling"],
        "storlek_indikation": "litet",
        "sammanfattning": "Konsultbolag inom ledarskap.",
    }
    db.update_company(cid, ai_profile=json.dumps(profile, ensure_ascii=False))
    return cid


def _insert_bidrag(tmp_db, title: str = "Bidrag för kompetensutveckling", **kwargs) -> int:
    defaults = {
        "record_type": "bidrag",
        "source": "vinnova",
        "source_id": f"VINN-TEST-{id(title)}",
        "title": title,
        "buyer": "Vinnova",
        "description": "Utlysning om ledarskap och utbildning.",
        "score": 10,
        "score_rationale": "test",
        "status": "published",
    }
    defaults.update(kwargs)
    return db.upsert_procurement(defaults)


MOCK_PROFILE_JSON = json.dumps({
    "bransch": "IT-konsult",
    "tjanster": ["systemutveckling"],
    "kompetensomraden": ["java"],
    "nyckelord_for_bidrag": ["digitalisering", "innovation"],
    "storlek_indikation": "litet",
    "sammanfattning": "IT-konsultbolag.",
})


# ===========================================================================
# TestFetchWebsiteText
# ===========================================================================

class TestFetchWebsiteText:
    def test_successful_fetch(self, monkeypatch):
        class FakeResp:
            status_code = 200
            text = "<html><body><p>Hej världen</p></body></html>"
            def raise_for_status(self): pass

        monkeypatch.setattr("company_profiler.httpx.get", lambda *a, **kw: FakeResp())
        result = fetch_website_text("https://example.com")
        assert result is not None
        assert "Hej världen" in result

    def test_timeout_returns_none(self, monkeypatch):
        def mock_get(*a, **kw):
            raise Exception("Timeout")

        monkeypatch.setattr("company_profiler.httpx.get", mock_get)
        result = fetch_website_text("https://example.com")
        assert result is None

    def test_empty_response(self, monkeypatch):
        class FakeResp:
            status_code = 200
            text = "<html><body></body></html>"
            def raise_for_status(self): pass

        monkeypatch.setattr("company_profiler.httpx.get", lambda *a, **kw: FakeResp())
        result = fetch_website_text("https://example.com")
        assert result is not None

    def test_url_without_https(self, monkeypatch):
        urls_called = []
        class FakeResp:
            status_code = 200
            text = "<html><body><p>Content</p></body></html>"
            def raise_for_status(self): pass

        def mock_get(url, **kw):
            urls_called.append(url)
            return FakeResp()

        monkeypatch.setattr("company_profiler.httpx.get", mock_get)
        fetch_website_text("example.com")
        assert urls_called[0].startswith("https://")

    def test_none_url(self):
        result = fetch_website_text(None)
        assert result is None

    def test_empty_url(self):
        result = fetch_website_text("")
        assert result is None


# ===========================================================================
# TestProfileCompany
# ===========================================================================

class TestProfileCompany:
    def test_successful_profiling(self, tmp_db, monkeypatch):
        cid = _create_test_company(tmp_db)

        monkeypatch.setattr("company_profiler.fetch_website_text", lambda url: "Vi erbjuder IT-konsulttjänster.")

        def mock_post(url, json, timeout):
            class FakeResp:
                status_code = 200
                def raise_for_status(self): pass
                def json(self_):
                    return {"choices": [{"message": {"content": MOCK_PROFILE_JSON}}]}
            return FakeResp()

        monkeypatch.setattr("company_profiler.httpx.post", mock_post)

        result = profile_company(cid)
        assert result is not None
        assert result["bransch"] == "IT-konsult"

        # Verify saved to DB
        company = db.get_company(cid)
        assert company["ai_profile"] is not None

    def test_llm_returns_none(self, tmp_db, monkeypatch):
        cid = _create_test_company(tmp_db)
        monkeypatch.setattr("company_profiler.fetch_website_text", lambda url: "Some text")
        monkeypatch.setattr("company_profiler._call_llm", lambda *a, **kw: None)

        result = profile_company(cid)
        assert result is None

    def test_invalid_json_from_llm(self, tmp_db, monkeypatch):
        cid = _create_test_company(tmp_db)
        monkeypatch.setattr("company_profiler.fetch_website_text", lambda url: "Some text")
        monkeypatch.setattr("company_profiler._call_llm", lambda *a, **kw: "not valid json {{{")

        result = profile_company(cid)
        assert result is None

    def test_missing_company(self, tmp_db):
        result = profile_company(9999)
        assert result is None

    def test_on_progress_callbacks(self, tmp_db, monkeypatch):
        cid = _create_test_company(tmp_db)
        monkeypatch.setattr("company_profiler.fetch_website_text", lambda url: "Some text")
        monkeypatch.setattr("company_profiler._call_llm", lambda *a, **kw: MOCK_PROFILE_JSON)

        progress_msgs = []
        profile_company(cid, on_progress=lambda msg: progress_msgs.append(msg))
        assert len(progress_msgs) >= 3  # fetching, analyzing, saved

    def test_website_fetch_fails(self, tmp_db, monkeypatch):
        cid = _create_test_company(tmp_db)
        monkeypatch.setattr("company_profiler.fetch_website_text", lambda url: None)

        progress_msgs = []
        result = profile_company(cid, on_progress=lambda msg: progress_msgs.append(msg))
        assert result is None
        assert any("Kunde inte" in m for m in progress_msgs)


# ===========================================================================
# TestKeywordScore
# ===========================================================================

class TestKeywordScore:
    def test_basic_match(self):
        score = _keyword_score(["ledarskap", "utbildning"], "program om ledarskap och utbildning")
        assert score > 0

    def test_no_keywords(self):
        score = _keyword_score([], "some text")
        assert score == 0.0

    def test_empty_text(self):
        score = _keyword_score(["ledarskap"], "")
        assert score == 0.0

    def test_full_match_gives_100(self):
        kws = ["a", "b", "c"]
        score = _keyword_score(kws, "a b c")
        assert score == 100.0

    def test_partial_match(self):
        kws = ["a", "b", "c", "d"]
        score = _keyword_score(kws, "a c")
        assert 0 < score < 100

    def test_case_insensitive(self):
        score = _keyword_score(["Ledarskap"], "LEDARSKAP ÄR BRA")
        assert score > 0

    def test_word_boundary_no_false_positive(self):
        """After fix: 'ledning' should NOT match 'förändringsledningen' as a standalone word."""
        score = _keyword_score(["ledning"], "förändringsledningen har beslutat")
        assert score == 0.0

    def test_word_boundary_exact_match(self):
        """Exact standalone word should still match."""
        score = _keyword_score(["ledning"], "ledning av projektet")
        assert score > 0


# ===========================================================================
# TestMatchCompanyToBidrag
# ===========================================================================

class TestMatchCompanyToBidrag:
    def test_successful_matching(self, tmp_db, monkeypatch):
        cid = _create_company_with_profile(tmp_db)
        _insert_bidrag(tmp_db, title="Utlysning ledarskap", description="Bidrag coaching utbildning")

        match_json = json.dumps({"match_score": 85, "reasoning": "Bra match"})
        monkeypatch.setattr("company_profiler._call_llm", lambda *a, **kw: match_json)

        matches = match_company_to_bidrag(cid)
        assert len(matches) > 0
        assert matches[0]["match_score"] == 85

    def test_llm_fallback_to_keyword_score(self, tmp_db, monkeypatch):
        cid = _create_company_with_profile(tmp_db)
        _insert_bidrag(tmp_db, title="Utlysning ledarskap", description="Bidrag coaching utbildning")

        monkeypatch.setattr("company_profiler._call_llm", lambda *a, **kw: None)

        matches = match_company_to_bidrag(cid)
        assert len(matches) > 0
        assert "Nyckelordsmatchning" in matches[0]["reasoning"]

    def test_no_bidrag_in_db(self, tmp_db, monkeypatch):
        cid = _create_company_with_profile(tmp_db)
        matches = match_company_to_bidrag(cid)
        assert matches == []

    def test_no_keywords_in_profile(self, tmp_db, monkeypatch):
        cid = db.create_company("NoKW Co", "https://example.com", "admin")
        profile = {"bransch": "Test", "tjanster": [], "kompetensomraden": [], "nyckelord_for_bidrag": [],
                    "storlek_indikation": "litet", "sammanfattning": "Test."}
        db.update_company(cid, ai_profile=json.dumps(profile))
        _insert_bidrag(tmp_db)

        progress = []
        matches = match_company_to_bidrag(cid, on_progress=lambda m: progress.append(m))
        assert matches == []
        assert any("nyckelord" in m.lower() for m in progress)

    def test_company_without_profile(self, tmp_db):
        cid = _create_test_company(tmp_db)
        matches = match_company_to_bidrag(cid)
        assert matches == []

    def test_nonexistent_company(self, tmp_db):
        matches = match_company_to_bidrag(9999)
        assert matches == []


# ===========================================================================
# TestMatchAllCompanies
# ===========================================================================

class TestMatchAllCompanies:
    def test_matches_profiled_companies(self, tmp_db, monkeypatch):
        cid1 = _create_company_with_profile(tmp_db, name="Co1")
        cid2 = _create_company_with_profile(tmp_db, name="Co2")
        _insert_bidrag(tmp_db, title="Utlysning ledarskap", source_id="VINN-ALL-1",
                       description="Bidrag coaching utbildning")

        match_json = json.dumps({"match_score": 70, "reasoning": "OK match"})
        monkeypatch.setattr("company_profiler._call_llm", lambda *a, **kw: match_json)

        total = match_all_companies()
        assert total >= 2  # at least 1 match per company

    def test_skips_unprofiled_companies(self, tmp_db, monkeypatch):
        _create_test_company(tmp_db, name="NoProfCo")  # no profile
        cid2 = _create_company_with_profile(tmp_db, name="ProfiledCo")
        _insert_bidrag(tmp_db, title="Utlysning ledarskap", source_id="VINN-ALL-2",
                       description="Bidrag coaching utbildning")

        match_json = json.dumps({"match_score": 70, "reasoning": "OK"})
        monkeypatch.setattr("company_profiler._call_llm", lambda *a, **kw: match_json)

        total = match_all_companies()
        # Only 1 company had a profile, so matches should come from that one only
        assert total >= 1


# ===========================================================================
# TestCallLlm
# ===========================================================================

class TestCallLlm:
    """Tests for _call_llm retry logic."""

    def _make_success_response(self, content: str = '{"result": "ok"}'):
        class FakeResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self_):
                return {"choices": [{"message": {"content": content}}]}
        return FakeResp()

    def test_retry_on_timeout(self, monkeypatch):
        calls = []
        def mock_post(url, json, timeout):
            calls.append(len(calls))
            if len(calls) == 1:
                raise httpx.TimeoutException("Connection timed out")
            return self._make_success_response()

        monkeypatch.setattr("company_profiler.httpx.post", mock_post)
        result = _call_llm("system", "user")
        assert result == '{"result": "ok"}'
        assert len(calls) == 2

    def test_retry_on_5xx(self, monkeypatch):
        calls = []
        def mock_post(url, json, timeout):
            calls.append(len(calls))
            if len(calls) == 1:
                resp = httpx.Response(500, request=httpx.Request("POST", url))
                raise httpx.HTTPStatusError("Server error", request=resp.request, response=resp)
            return self._make_success_response()

        monkeypatch.setattr("company_profiler.httpx.post", mock_post)
        result = _call_llm("system", "user")
        assert result == '{"result": "ok"}'
        assert len(calls) == 2

    def test_no_retry_on_4xx(self, monkeypatch):
        calls = []
        def mock_post(url, json, timeout):
            calls.append(len(calls))
            resp = httpx.Response(400, request=httpx.Request("POST", url))
            raise httpx.HTTPStatusError("Bad request", request=resp.request, response=resp)

        monkeypatch.setattr("company_profiler.httpx.post", mock_post)
        result = _call_llm("system", "user")
        assert result is None
        assert len(calls) == 1  # No retry for 4xx

    def test_final_failure_after_retry(self, monkeypatch):
        calls = []
        def mock_post(url, json, timeout):
            calls.append(len(calls))
            raise httpx.TimeoutException("Connection timed out")

        monkeypatch.setattr("company_profiler.httpx.post", mock_post)
        result = _call_llm("system", "user")
        assert result is None
        assert len(calls) == 2  # Tried twice

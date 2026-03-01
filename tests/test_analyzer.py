"""Tests for analyzer.py — JSON parsing, prefilter parsing, LLM call mocking."""

import json

import pytest

from analyzer import (
    _parse_analysis_json,
    _validate_analysis_dict,
    _extract_sections_by_keys,
    _parse_prefilter_json,
    _call_ollama,
    _call_ollama_tools,
    analyze_procurement,
    ollama_prefilter_procurement,
    REQUIRED_ANALYSIS_KEYS,
)
import db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_analysis() -> dict:
    return {
        "kravsammanfattning": "Sammanfattning av krav.",
        "matchningsanalys": "HAST matchar bra.",
        "prisstrategi": "Timpris rekommenderas.",
        "anbudshjalp": "Lyft UGL-certifiering.",
    }


def _insert_test_procurement(tmp_db, **kwargs) -> int:
    defaults = {
        "source": "ted",
        "source_id": "TEST-ANA-1",
        "title": "Ledarskapsutbildning for kommuner",
        "buyer": "Region Stockholm",
        "geography": "SE110",
        "cpv_codes": "80530000",
        "published_date": "2026-01-15",
        "deadline": "2026-04-01",
        "estimated_value": 500000,
        "currency": "SEK",
        "status": "published",
        "url": "https://example.com/1",
        "description": "Upphandling av ledarskapsutbildning.",
        "score": 0,
        "score_rationale": None,
    }
    defaults.update(kwargs)
    return db.upsert_procurement(defaults)


# ===========================================================================
# TestParseAnalysisJson
# ===========================================================================

class TestParseAnalysisJson:
    def test_valid_json(self):
        raw = json.dumps(_valid_analysis())
        result = _parse_analysis_json(raw)
        assert result is not None
        assert result["kravsammanfattning"] == "Sammanfattning av krav."

    def test_json_with_code_fences(self):
        raw = "```json\n" + json.dumps(_valid_analysis()) + "\n```"
        result = _parse_analysis_json(raw)
        assert result is not None
        assert "prisstrategi" in result

    def test_json_with_surrounding_text(self):
        raw = "Here is my analysis:\n" + json.dumps(_valid_analysis()) + "\nDone."
        result = _parse_analysis_json(raw)
        assert result is not None

    def test_missing_key_returns_none(self):
        data = _valid_analysis()
        del data["anbudshjalp"]
        raw = json.dumps(data)
        result = _parse_analysis_json(raw)
        assert result is None

    def test_empty_value_returns_none(self):
        data = _valid_analysis()
        data["kravsammanfattning"] = ""
        raw = json.dumps(data)
        result = _parse_analysis_json(raw)
        assert result is None


# ===========================================================================
# TestValidateAnalysisDict
# ===========================================================================

class TestValidateAnalysisDict:
    def test_valid(self):
        assert _validate_analysis_dict(_valid_analysis()) is True

    def test_missing_key(self):
        data = _valid_analysis()
        del data["prisstrategi"]
        assert _validate_analysis_dict(data) is False

    def test_non_string_value(self):
        data = _valid_analysis()
        data["kravsammanfattning"] = 42
        assert _validate_analysis_dict(data) is False

    def test_not_a_dict(self):
        assert _validate_analysis_dict("string") is False
        assert _validate_analysis_dict([]) is False


# ===========================================================================
# TestParsePrefilterJson
# ===========================================================================

class TestParsePrefilterJson:
    def test_valid(self):
        raw = '{"relevant": true, "reasoning": "Matches HAST"}'
        result = _parse_prefilter_json(raw)
        assert result is not None
        assert result["relevant"] is True

    def test_with_code_fence(self):
        raw = '```json\n{"relevant": false, "reasoning": "Not relevant"}\n```'
        result = _parse_prefilter_json(raw)
        assert result is not None
        assert result["relevant"] is False

    def test_invalid_json(self):
        assert _parse_prefilter_json("not json at all") is None

    def test_missing_relevant_key(self):
        raw = '{"reasoning": "something"}'
        result = _parse_prefilter_json(raw)
        assert result is None

    def test_relevant_not_bool(self):
        raw = '{"relevant": "yes", "reasoning": "something"}'
        result = _parse_prefilter_json(raw)
        assert result is None

    def test_surrounding_text(self):
        raw = 'Analysis result: {"relevant": true, "reasoning": "Good"} end.'
        result = _parse_prefilter_json(raw)
        assert result is not None


# ===========================================================================
# TestCallOllama (mocked)
# ===========================================================================

class TestCallOllama:
    def test_success(self, monkeypatch):
        def mock_post(url, json, timeout):
            class FakeResp:
                status_code = 200
                def raise_for_status(self): pass
                def json(self_):
                    return {"choices": [{"message": {"content": "hello"}}]}
            return FakeResp()

        monkeypatch.setattr("analyzer.httpx.post", mock_post)
        result = _call_ollama("system", "user")
        assert result == "hello"

    def test_error_returns_none(self, monkeypatch):
        def mock_post(url, json, timeout):
            raise Exception("Connection refused")

        monkeypatch.setattr("analyzer.httpx.post", mock_post)
        result = _call_ollama("system", "user")
        assert result is None

    def test_json_mode(self, monkeypatch):
        payloads = []
        def mock_post(url, json, timeout):
            payloads.append(json)
            class FakeResp:
                status_code = 200
                def raise_for_status(self): pass
                def json(self_):
                    return {"choices": [{"message": {"content": "{}"}}]}
            return FakeResp()

        monkeypatch.setattr("analyzer.httpx.post", mock_post)
        _call_ollama("system", "user", json_mode=True)
        assert payloads[0].get("response_format") == {"type": "json_object"}


# ===========================================================================
# TestCallOllamaTools (mocked)
# ===========================================================================

class TestCallOllamaTools:
    def test_tool_call_response(self, monkeypatch):
        analysis = _valid_analysis()
        def mock_post(url, json, timeout):
            class FakeResp:
                status_code = 200
                def raise_for_status(self): pass
                def json(self_):
                    return {"choices": [{"message": {
                        "tool_calls": [{"function": {"arguments": json_module.dumps(analysis)}}]
                    }}]}
            return FakeResp()

        import json as json_module
        monkeypatch.setattr("analyzer.httpx.post", mock_post)
        result = _call_ollama_tools("system", "user")
        assert result is not None
        assert result["kravsammanfattning"] == analysis["kravsammanfattning"]

    def test_content_fallback(self, monkeypatch):
        """When no tool_calls, should try parsing content."""
        analysis = _valid_analysis()
        import json as json_module
        def mock_post(url, json, timeout):
            class FakeResp:
                status_code = 200
                def raise_for_status(self): pass
                def json(self_):
                    return {"choices": [{"message": {
                        "content": json_module.dumps(analysis)
                    }}]}
            return FakeResp()

        monkeypatch.setattr("analyzer.httpx.post", mock_post)
        result = _call_ollama_tools("system", "user")
        assert result is not None

    def test_error_returns_none(self, monkeypatch):
        def mock_post(url, json, timeout):
            raise Exception("Connection refused")

        monkeypatch.setattr("analyzer.httpx.post", mock_post)
        result = _call_ollama_tools("system", "user")
        assert result is None


# ===========================================================================
# TestAnalyzeProcurement (mocked LLM)
# ===========================================================================

class TestAnalyzeProcurement:
    def test_returns_cached(self, tmp_db):
        proc_id = _insert_test_procurement(tmp_db)
        analysis = {
            "kravsammanfattning": "Cached",
            "matchningsanalys": "Cached",
            "prisstrategi": "Cached",
            "anbudshjalp": "Cached",
            "model": "test",
        }
        db.save_analysis(proc_id, analysis)
        result = analyze_procurement(proc_id)
        assert result is not None
        assert result["kravsammanfattning"] == "Cached"

    def test_force_bypasses_cache(self, tmp_db, monkeypatch):
        proc_id = _insert_test_procurement(tmp_db)
        analysis = {
            "kravsammanfattning": "Cached",
            "matchningsanalys": "Cached",
            "prisstrategi": "Cached",
            "anbudshjalp": "Cached",
            "model": "test",
        }
        db.save_analysis(proc_id, analysis)

        new_analysis = _valid_analysis()
        monkeypatch.setattr("analyzer._call_ollama_tools", lambda *a, **kw: new_analysis)
        monkeypatch.setattr("analyzer.fetch_full_notice_text", lambda x: None)

        result = analyze_procurement(proc_id, force=True)
        assert result is not None
        assert result["kravsammanfattning"] == new_analysis["kravsammanfattning"]

    def test_missing_procurement(self, tmp_db):
        result = analyze_procurement(9999)
        assert result is None

    def test_fallback_to_text_mode(self, tmp_db, monkeypatch):
        proc_id = _insert_test_procurement(tmp_db)
        analysis_json = json.dumps(_valid_analysis())

        monkeypatch.setattr("analyzer._call_ollama_tools", lambda *a, **kw: None)
        monkeypatch.setattr("analyzer._call_ollama", lambda *a, **kw: analysis_json)
        monkeypatch.setattr("analyzer.fetch_full_notice_text", lambda x: None)

        result = analyze_procurement(proc_id, force=True)
        assert result is not None
        assert result["kravsammanfattning"] == "Sammanfattning av krav."


# ===========================================================================
# TestPrefilterProcurement (mocked LLM)
# ===========================================================================

class TestPrefilterProcurement:
    def test_relevant(self, tmp_db, monkeypatch):
        proc_id = _insert_test_procurement(tmp_db)
        monkeypatch.setattr(
            "analyzer._call_ollama",
            lambda *a, **kw: '{"relevant": true, "reasoning": "Match"}',
        )
        result = ollama_prefilter_procurement(proc_id)
        assert result is not None
        assert result["relevant"] is True
        proc = db.get_procurement(proc_id)
        assert proc["ai_relevance"] == "relevant"

    def test_irrelevant(self, tmp_db, monkeypatch):
        proc_id = _insert_test_procurement(tmp_db)
        monkeypatch.setattr(
            "analyzer._call_ollama",
            lambda *a, **kw: '{"relevant": false, "reasoning": "IT-system"}',
        )
        result = ollama_prefilter_procurement(proc_id)
        assert result is not None
        assert result["relevant"] is False
        proc = db.get_procurement(proc_id)
        assert proc["ai_relevance"] == "irrelevant"

    def test_llm_error_returns_none(self, tmp_db, monkeypatch):
        proc_id = _insert_test_procurement(tmp_db)
        monkeypatch.setattr("analyzer._call_ollama", lambda *a, **kw: None)
        result = ollama_prefilter_procurement(proc_id)
        assert result is None

    def test_missing_procurement(self, tmp_db, monkeypatch):
        result = ollama_prefilter_procurement(9999)
        assert result is None

"""M10 regression tests: curated lexicon + safe user overrides, offline."""
import json

import pytest

from streamclipper import analyze as analyzer
from streamclipper import highlight_lexicon as rules_module
from streamclipper.highlight_lexicon import (
    DEFAULT_RULES, PhraseRule, match_rules, merged_rules,
    load_custom_rules, save_custom_rules, validate_custom_rules,
)
from streamclipper.models import TranscriptSegment, VideoInfo
from streamclipper.semantic import EventEvidence, fuse_events, transcript_cues


def test_curated_standard_rules_are_unique_and_cover_both_languages():
    assert len(DEFAULT_RULES) >= 45
    assert len({r.phrase.lower() for r in DEFAULT_RULES}) == len(DEFAULT_RULES)
    assert any(r.phrase == "holy shit" for r in DEFAULT_RULES)
    assert any(r.phrase == "oh mein gott" for r in DEFAULT_RULES)


def test_strong_reaction_triggers_recommendation_without_image_signal():
    result = transcript_cues([(20, 22, "Alter! Was zur Hölle war das?!")])
    assert len(result) == 1
    assert result[0].kind == "speech"
    assert result[0].strength >= .7
    assert "Transkript-Hinweis" in result[0].description
    assert fuse_events(result, duration=100)


def test_gaming_noun_not_standalone_highlight():
    context = transcript_cues([(20, 22, "Die Polizei ist schon wieder hier")])
    assert len(context) == 1
    assert context[0].kind == "speech_context"
    assert fuse_events(context, 100) == []
    corroborated = fuse_events(context + [EventEvidence(21, "motion", .55, "Bildveränderung")], 100)
    assert corroborated and "Transkript-Hinweis" in corroborated[0].reason


def test_context_with_reaction_does_not_count_as_two_modalities():
    context = transcript_cues([(20, 22, "Polizei")])
    reaction = transcript_cues([(21, 22, "Oh mein Gott")])
    combined = fuse_events(context + reaction, 100)[0]
    solo = fuse_events(reaction, 100)[0]
    assert combined.score == solo.score


def test_literal_matching_not_substrings_or_regex_injection():
    assert not match_rules("im Altersheim", merged_rules())  # not 'Alter'
    own = [PhraseRule("C++ [Wow]", "reaction", "high", "user")]
    assert match_rules("C++ [Wow] habe ich nicht erwartet", own)
    assert not match_rules("Cxxx [Wow] habe ich nicht erwartet", own)
    assert transcript_cues([(1, 2, "Gewöhnlicher Text")]) == []


def test_punctuation_fallback_kept():
    result = transcript_cues([(1, 2, "Was soll das denn??")])
    assert len(result) == 1
    assert result[0].kind == "speech"


def test_custom_override_and_persistence(tmp_path):
    file = tmp_path / "settings" / "highlight_words.json"
    custom = [PhraseRule("Alter", "reaction", "low", "user"),
              PhraseRule("Da ist die Entenpolizei", "surprise", "high", "user")]
    save_custom_rules(custom, file)
    loaded = load_custom_rules(file)
    assert loaded == custom
    merged = merged_rules(loaded)
    hits = match_rules("Alter. Da ist die Entenpolizei!", merged)
    assert any(hit.phrase == "Alter" and hit.requires_context for hit in hits)
    assert any(hit.phrase == "Da ist die Entenpolizei" and not hit.requires_context for hit in hits)
    data = json.loads(file.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["rules"]) == 2
    assert not list(file.parent.glob("*.tmp"))


@pytest.mark.parametrize("phrase", ["", "X", "A" * 81, "hello\x07world"])
def test_invalid_custom_phrase_rejected(phrase):
    with pytest.raises(ValueError):
        validate_custom_rules([PhraseRule(phrase, "reaction", "high")])


def test_duplicates_rejected_including_case_variants():
    with pytest.raises(ValueError, match="Doppelter"):
        validate_custom_rules([PhraseRule("GTA", "reaction", "high"),
                               PhraseRule("gta", "reaction", "context")])


@pytest.mark.parametrize("bad", ["{", "[]", '{"version": 2, "rules": []}',
                                    '{"version": 1, "rules": [{}]}'])
def test_invalid_config_fails_visibly(tmp_path, bad):
    file = tmp_path / 'corrupt.json'
    file.write_text(bad, encoding='utf-8')
    with pytest.raises(ValueError):
        load_custom_rules(file)


def test_custom_keywords_used_in_analysis_without_cloud(tmp_path, monkeypatch):
    file = tmp_path / "highlight_words.json"
    save_custom_rules([PhraseRule("Käsebrotkatastrophe", "surprise", "high")], file)
    monkeypatch.setattr(rules_module, "settings_path", lambda: file)
    video = VideoInfo("fake.mp4", 80.0, 1920, 1080, 60, True)
    monkeypatch.setattr(analyzer, "probe_video", lambda path: video)
    monkeypatch.setattr(analyzer, "audio_levels", lambda *args, **kwargs: [-40.0] * 80)
    monkeypatch.setattr(analyzer, "transcribe_video", lambda *args, **kwargs: [
        TranscriptSegment(20, 21, "Käsebrotkatastrophe!")])
    found = analyzer.analyze("fake.mp4", speech_model="fake-model")
    assert any("Käsebrotkatastrophe" in c.reason for c in found.candidates)


def test_invalid_config_fails_before_audio_decode(tmp_path, monkeypatch):
    file = tmp_path / "bad.json"
    file.write_text("{", encoding='utf-8')
    monkeypatch.setattr(rules_module, "settings_path", lambda: file)
    monkeypatch.setattr(analyzer, "probe_video", lambda path: pytest.fail("Should not probe"))
    with pytest.raises(ValueError):
        analyzer.analyze("a.mp4", speech_model="fake")


def test_no_customizations_does_not_create_file(tmp_path):
    filename = tmp_path / "highlight_words.json"
    assert load_custom_rules(filename) == []
    assert not filename.exists()
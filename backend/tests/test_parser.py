"""Tests for the transcript parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.parser import parse_transcripts

# Resolve the source file path relative to the repo root
_SOURCE_FILE = Path(__file__).resolve().parents[2] / "AI_in_AEC_2026_Snapsight_Summaries.txt"


@pytest.fixture(scope="module")
def sessions():
    """Parse sessions once for the whole test module."""
    if not _SOURCE_FILE.exists():
        pytest.skip(f"Source file not found: {_SOURCE_FILE}")
    return parse_transcripts(_SOURCE_FILE)


def test_parse_all_sessions(sessions):
    assert len(sessions) == 15


def test_first_session_title(sessions):
    assert sessions[0].title == "Opening of the AI in AEC 2026"
    assert sessions[0].session_number == 1


def test_second_session(sessions):
    s = sessions[1]
    assert s.session_number == 2
    assert "Keynote" in s.title or "Future" in s.title


def test_speakers_extracted(sessions):
    """At least some sessions should have speakers."""
    sessions_with_speakers = [s for s in sessions if len(s.speakers) > 0]
    assert len(sessions_with_speakers) > 5


def test_first_session_speaker(sessions):
    """First session should have Vesa Jarvinen as speaker."""
    speakers = sessions[0].speakers
    assert len(speakers) >= 1
    names = [s.name for s in speakers]
    assert any("Vesa" in n for n in names)


def test_live_text_present(sessions):
    """All sessions should have live text."""
    for s in sessions:
        assert len(s.live_text) > 0, f"Session {s.session_number} has no live text"


def test_summary_text_present(sessions):
    """Most sessions should have summary text."""
    sessions_with_summary = [s for s in sessions if len(s.summary_text) > 0]
    assert len(sessions_with_summary) >= 12


def test_session_numbers_sequential(sessions):
    """Session numbers should be 1 through 15."""
    numbers = sorted(s.session_number for s in sessions)
    assert numbers == list(range(1, 16))


def test_speaker_fields(sessions):
    """Speakers should have all fields populated."""
    for s in sessions:
        for speaker in s.speakers:
            assert speaker.initials, f"Missing initials in session {s.session_number}"
            assert speaker.name, f"Missing name in session {s.session_number}"
            # title and organization can be "-" but should exist
            assert speaker.title is not None
            assert speaker.organization is not None


def test_closing_session(sessions):
    """Last session should be the closing session."""
    last = sessions[-1]
    assert last.session_number == 15
    assert "Closing" in last.title


def test_to_dict_roundtrip(sessions):
    """Test serialization roundtrip."""
    from pipeline.parser import SessionChunk

    for s in sessions[:3]:
        d = s.to_dict()
        restored = SessionChunk.from_dict(d)
        assert restored.session_number == s.session_number
        assert restored.title == s.title
        assert len(restored.speakers) == len(s.speakers)

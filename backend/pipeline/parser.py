"""Parse the Snapsight AI Summaries transcript file into structured session objects."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class SpeakerInfo:
    initials: str
    name: str
    title: str
    organization: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionChunk:
    session_number: int
    title: str
    live_text: str
    summary_text: str
    speakers: list[SpeakerInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_number": self.session_number,
            "title": self.title,
            "live_text": self.live_text,
            "summary_text": self.summary_text,
            "speakers": [s.to_dict() for s in self.speakers],
        }

    @classmethod
    def from_dict(cls, d: dict) -> SessionChunk:
        speakers = [SpeakerInfo(**s) for s in d.get("speakers", [])]
        return cls(
            session_number=d["session_number"],
            title=d["title"],
            live_text=d["live_text"],
            summary_text=d["summary_text"],
            speakers=speakers,
        )


def _parse_speakers(text: str) -> list[SpeakerInfo]:
    """Parse the Speakers section into SpeakerInfo objects.

    In the source file each field is on its own line separated by blank lines:
        VJ                          <- initials
        (blank)
        Vesa Järvinen               <- name
        (blank)
        chair of the programme ...  <- title (or "-")
        (blank)
        AINS Group                  <- organization

    Strategy: collect all non-empty lines, then walk through looking for
    initials (2-4 uppercase letters) and consume the next 3 lines as
    name / title / organization.
    """
    speakers: list[SpeakerInfo] = []
    # Collect all non-empty, stripped lines
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

    i = 0
    while i < len(lines):
        # Look for an initials line
        if re.match(r"^[A-Z]{2,4}$", lines[i]):
            initials = lines[i]
            name = lines[i + 1] if i + 1 < len(lines) else ""
            title = lines[i + 2] if i + 2 < len(lines) else "-"
            organization = lines[i + 3] if i + 3 < len(lines) else "-"

            # Validate: the name field should NOT look like another initials line.
            # If it does, we only have the initials and nothing else — skip.
            if re.match(r"^[A-Z]{2,4}$", name):
                i += 1
                continue

            # Guard: if title looks like initials for the next speaker,
            # the current speaker only had 2 fields (initials + name).
            if re.match(r"^[A-Z]{2,4}$", title):
                speakers.append(SpeakerInfo(
                    initials=initials, name=name, title="-", organization="-",
                ))
                i += 2
                continue

            # Guard: if organization looks like initials for the next speaker,
            # the current speaker only had 3 fields.
            if re.match(r"^[A-Z]{2,4}$", organization):
                speakers.append(SpeakerInfo(
                    initials=initials, name=name, title=title, organization="-",
                ))
                i += 3
                continue

            speakers.append(SpeakerInfo(
                initials=initials,
                name=name,
                title=title,
                organization=organization,
            ))
            i += 4
        else:
            i += 1

    return speakers


def parse_transcripts(source_path: str | Path) -> list[SessionChunk]:
    """Parse the Snapsight transcript file into a list of SessionChunk objects."""
    source_path = Path(source_path)
    content = source_path.read_text(encoding="utf-8")

    # Split on separator lines (80 or more = signs on a line by themselves)
    separator = re.compile(r"^={10,}$", re.MULTILINE)
    parts = separator.split(content)

    sessions: list[SessionChunk] = []

    # Walk through parts looking for SESSION headers.
    # The structure is:  ... | separator | SESSION N: Title | separator | body | separator ...
    # After the first separator split, SESSION headers appear as parts containing "SESSION \d+:"
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        match = re.match(r"^SESSION\s+(\d+):\s*(.+)$", part, re.DOTALL)
        if match:
            session_number = int(match.group(1))
            title = match.group(2).strip()

            # The body is the next part (between the closing separator and the next separator)
            body = parts[i + 1] if i + 1 < len(parts) else ""

            # Parse live_text and summary_text from the body
            live_text = ""
            summary_text = ""
            speakers: list[SpeakerInfo] = []

            live_marker = "--- LIVE TEXT ---"
            summary_marker = "--- SUMMARY ---"

            live_idx = body.find(live_marker)
            summary_idx = body.find(summary_marker)

            if live_idx != -1 and summary_idx != -1:
                # Live text is between LIVE TEXT marker and SUMMARY marker
                live_text = body[live_idx + len(live_marker):summary_idx].strip()
                # Summary section is after SUMMARY marker
                summary_section = body[summary_idx + len(summary_marker):].strip()
            elif live_idx != -1:
                # No summary section
                live_text = body[live_idx + len(live_marker):].strip()
                summary_section = ""
            else:
                # Fallback: treat entire body as live text
                live_text = body.strip()
                summary_section = ""

            # Parse summary_section: split into Summary text and Speakers
            if summary_section:
                # The summary section starts with "Summary" header then text,
                # followed by "Speakers" section
                speakers_marker_match = re.search(
                    r"^Speakers\s*$", summary_section, re.MULTILINE
                )
                if speakers_marker_match:
                    # Summary text is between "Summary" header and "Speakers"
                    summary_body = summary_section[:speakers_marker_match.start()]
                    speakers_body = summary_section[speakers_marker_match.end():]

                    # Remove the "Summary" header line if present
                    summary_body = re.sub(
                        r"^\s*Summary\s*\n", "", summary_body, count=1
                    ).strip()
                    summary_text = summary_body

                    # Parse speakers
                    speakers = _parse_speakers(speakers_body)
                else:
                    # No speakers section, just summary
                    summary_body = re.sub(
                        r"^\s*Summary\s*\n", "", summary_section, count=1
                    ).strip()
                    summary_text = summary_body

            sessions.append(SessionChunk(
                session_number=session_number,
                title=title,
                live_text=live_text,
                summary_text=summary_text,
                speakers=speakers,
            ))

            # Skip ahead past the body part
            i += 2
        else:
            i += 1

    return sessions


if __name__ == "__main__":
    import json
    import sys

    source = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parents[2] / "AI_in_AEC_2026_Snapsight_Summaries.txt"
    )
    sessions = parse_transcripts(source)
    print(f"Parsed {len(sessions)} sessions")
    for s in sessions:
        print(
            f"  Session {s.session_number}: {s.title} "
            f"| speakers={len(s.speakers)} "
            f"| live_text={len(s.live_text)} chars "
            f"| summary={len(s.summary_text)} chars"
        )
    # Write JSON output
    out = Path(__file__).resolve().parents[1] / "data" / "pipeline_cache" / "parse_output.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([s.to_dict() for s in sessions], indent=2, ensure_ascii=False))
    print(f"Wrote {out}")

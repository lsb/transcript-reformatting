import argparse
import re
import textwrap
from pathlib import Path

TIMESTAMP_RE = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\s*$')
SPEAKER_RE = re.compile(r'^([A-Za-z][A-Za-z .\'-]{0,100}):\s*(.*)$')

def clean_lines(lines):
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            # remove blank lines
            continue
        if s.upper() == "WEBVTT":
            continue
        if TIMESTAMP_RE.match(s):
            continue
        out.append(s)
    return out

def group_utterances(lines):
    """
    Group consecutive lines by speaker. A line that starts with "Name:" begins a new utterance.
    Continuation lines are appended to the current speaker's text.
    Returns a list of utterance strings like "Name: text..." or plain text if no speaker detected.
    """
    utterances = []
    current_speaker = None
    current_text = None

    for s in lines:
        m = SPEAKER_RE.match(s)
        if m:
            # speaker line
            name = m.group(1)
            text = m.group(2) or ""
            if current_speaker is None:
                # first speaker encountered
                current_speaker = name
                current_text = text
            else:
                if name == current_speaker:
                    # same speaker repeated on a new "Name: ..." line -> append their text
                    if text:
                        # separate with a space to preserve sentence boundaries
                        current_text += " " + text
                else:
                    # different speaker -> flush previous and start new
                    if current_speaker:
                        utterances.append(f"{current_speaker}: {current_text.strip()}")
                    else:
                        utterances.append(current_text.strip())
                    current_speaker = name
                    current_text = text
        else:
            # continuation or narration
            if current_speaker is None:
                current_speaker = ""
                current_text = s
            else:
                current_text += " " + s

    # flush last
    if current_speaker is not None:
        if current_speaker:
            utterances.append(f"{current_speaker}: {current_text.strip()}")
        else:
            utterances.append(current_text.strip())

    return utterances

def reformat(text, width, subsequent_indent=""):
    """Collapse whitespace and wrap text to width.

    If `subsequent_indent` is provided, it will be used as the indentation
    for all lines after the first (via textwrap.fill's subsequent_indent).
    """
    # collapse any runs of whitespace to single space
    collapsed = re.sub(r'\s+', ' ', text).strip()
    # wrap text to width; preserve words and apply subsequent indent if requested
    return textwrap.fill(collapsed, width=width, subsequent_indent=subsequent_indent)

def main():
    p = argparse.ArgumentParser(description="Remove timestamps/blank lines and word-wrap a transcript.")
    p.add_argument("input", type=Path, help="input transcript file")
    p.add_argument("output", type=Path, help="output file")
    p.add_argument("width", type=int, help="target line length (characters) for wrapping")
    args = p.parse_args()

    if args.width <= 0:
        raise SystemExit("width must be a positive integer")

    raw = args.input.read_text(encoding="utf-8")
    lines = raw.splitlines()
    kept = clean_lines(lines)

    # Group by speaker so each speaker's block remains together and we can put a newline after each speaker.
    utterances = group_utterances(kept)

    # Wrap each utterance separately so speaker boundaries are preserved.
    wrapped_blocks = []
    for utt in utterances:
        # If this utterance starts with a speaker label ("Name: ..."),
        # indent all lines after the first by 10 spaces so subsequent
        # wrapped lines align as requested.
        if SPEAKER_RE.match(utt):
            wrapped_blocks.append(reformat(utt, args.width, subsequent_indent=' ' * 4))
        else:
            wrapped_blocks.append(reformat(utt, args.width))

    # Put a single newline between speakers (no blank/empty lines between blocks).
    output_text = "\n".join(wrapped_blocks) + "\n"
    args.output.write_text(output_text, encoding="utf-8")

if __name__ == "__main__":
    main()
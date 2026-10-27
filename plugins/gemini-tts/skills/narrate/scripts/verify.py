#!/usr/bin/env python3
"""Check a narration by transcribing it back and comparing it with the script.

Sends the audio to a Gemini model, then reports a character error rate (lower is
better) and the words that differ. It measures clarity and wrong words, not how
natural the voice sounds. Standard library only.

  python3 verify.py narration.wav script.txt --lang ta
  python3 verify.py narration.wav script.txt --lang en

Keep clips under about 5 minutes (the audio is sent inline); verify longer
narrations chunk by chunk.
"""
import argparse, base64, difflib, json, os, re, sys, urllib.error, urllib.request

URL = "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"
PROMPTS = {
    "ta": "Transcribe this Tamil audio exactly as spoken, in Tamil script. Write all numbers as Tamil words, not digits. Output only the transcript.",
    "en": "Transcribe this English audio exactly as spoken. Write all numbers as words, not digits. Output only the transcript.",
}


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def norm(s):
    return re.sub(r"[\s.,!?;:\-–—\"'()‌‍]", "", s.lower())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio")
    ap.add_argument("script")
    ap.add_argument("--lang", choices=sorted(PROMPTS), default="en")
    ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--key-env", default="GOOGLE_API_KEY", help="env var holding the API key (falls back to 'key')")
    a = ap.parse_args()

    api_key = os.environ.get(a.key_env) or os.environ.get("key")
    if not api_key:
        sys.exit(f"Set {a.key_env} to your Vertex AI API key.")
    mime = "audio/wav" if a.audio.lower().endswith(".wav") else "audio/mpeg"
    audio = base64.b64encode(open(a.audio, "rb").read()).decode()
    body = {"contents": [{"role": "user", "parts": [
        {"inlineData": {"mimeType": mime, "data": audio}},
        {"text": PROMPTS[a.lang]},
    ]}]}
    req = urllib.request.Request(URL.format(model=a.model), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    data = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 3:
                continue
            sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
        except (TimeoutError, urllib.error.URLError) as e:
            print(f"Attempt {attempt}/3 failed ({type(e).__name__}); retrying" if attempt < 3 else "", file=sys.stderr)
    if data is None:
        sys.exit("The transcription request kept timing out. Try again, or verify a shorter clip.")
    heard = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()

    script = open(a.script, encoding="utf-8").read()
    ref, hyp = norm(script), norm(heard)
    edits = lev(ref, hyp)
    print(f"Character error rate: {edits / max(1, len(ref)):.1%} ({edits} edits / {len(ref)} characters)")
    rw, hw = script.split(), heard.split()
    shown = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, rw, hw).get_opcodes():
        if tag != "equal" and norm(" ".join(rw[i1:i2])) != norm(" ".join(hw[j1:j2])):
            print(f"  script: {' '.join(rw[i1:i2])!r}  heard: {' '.join(hw[j1:j2])!r}")
            shown += 1
    if not shown:
        print("  No word differences beyond punctuation and spacing.")
    print("Note: the transcriber can make mistakes too, so re-listen to any flagged spots.")


if __name__ == "__main__":
    main()

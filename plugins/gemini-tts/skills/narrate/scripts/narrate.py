#!/usr/bin/env python3
"""Narrate a text file with Gemini TTS on Vertex AI (API-key auth).

Splits the script into chunks, calls the model once per chunk with the same
voice and style, and stitches the results into one WAV with short pauses.
Standard library only.

  export GOOGLE_API_KEY=...        # or set `key`, see --key-env
  python3 narrate.py script.txt -o narration.wav --voice Alnilam \
      --style "serious documentary narrator, natural pace, clear Tamil pronunciation"
"""
import argparse, base64, io, json, os, re, sys, time, urllib.error, urllib.request, wave

URL = "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"


def chunk_text(text, max_chars):
    """Paragraphs first; long paragraphs are split on sentence ends."""
    out, buf = [], ""
    for para in [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]:
        pieces = [para] if len(para) <= max_chars else re.split(r"(?<=[.!?])\s+", para)
        for piece in pieces:
            if buf and len(buf) + len(piece) + 1 > max_chars:
                out.append(buf)
                buf = ""
            buf = f"{buf} {piece}".strip() if buf else piece
        if buf:  # never merge across a paragraph break: keep natural pauses
            out.append(buf)
            buf = ""
    return out


def synth(api_key, model, text, voice, style, retries=4):
    part = {"text": text}
    if style:
        part["speechMetadata"] = {"style": style}
    body = {
        "contents": [{"role": "user", "parts": [part]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"voice": voice}},
        },
    }
    req = urllib.request.Request(
        URL.format(model=model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.load(r)
            raw = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            return raw
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 503) and attempt < retries - 1:
                time.sleep(4 * (attempt + 1))
                continue
            sys.exit(f"HTTP {e.code} from model '{model}': {detail}")
        except (KeyError, IndexError):
            sys.exit("Response had no audio (blocked or empty). Try rephrasing this chunk.")
    sys.exit("Retries exhausted")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default="narration.wav")
    ap.add_argument("--model", default="gemini-3.8-flash-tts")
    ap.add_argument("--voice", default="Alnilam")
    ap.add_argument("--style", default="natural, clear documentary narrator")
    ap.add_argument("--max-chars", type=int, default=1200, help="chunk size; keep well under the 8,192-token input limit")
    ap.add_argument("--pause", type=float, default=0.5, help="seconds of silence between chunks")
    ap.add_argument("--key-env", default="GOOGLE_API_KEY", help="env var holding the API key (falls back to 'key')")
    a = ap.parse_args()

    api_key = os.environ.get(a.key_env) or os.environ.get("key")
    if not api_key:
        sys.exit(f"Set {a.key_env} to your Vertex AI API key.")

    chunks = chunk_text(open(a.input, encoding="utf-8").read(), a.max_chars)
    print(f"{len(chunks)} chunk(s), model={a.model}, voice={a.voice}", file=sys.stderr)

    params, frames = None, []
    for i, c in enumerate(chunks, 1):
        raw = synth(api_key, a.model, c, a.voice, a.style)
        with wave.open(io.BytesIO(raw)) as w:
            p = (w.getnchannels(), w.getsampwidth(), w.getframerate())
            if params is None:
                params = p
            elif p != params:
                sys.exit(f"Chunk {i} has different audio format {p} vs {params}")
            pcm = w.readframes(w.getnframes())
        frames.append(pcm)
        print(f"  chunk {i}/{len(chunks)}: {len(pcm) / (params[1] * params[0] * params[2]):.1f}s", file=sys.stderr)

    silence = b"\x00" * (int(a.pause * params[2]) * params[1] * params[0])
    with wave.open(a.output, "wb") as w:
        w.setnchannels(params[0]); w.setsampwidth(params[1]); w.setframerate(params[2])
        w.writeframes(silence.join(frames))
    total = sum(len(f) for f in frames) / (params[1] * params[0] * params[2]) + a.pause * (len(frames) - 1)
    print(f"Wrote {a.output} ({total:.1f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()

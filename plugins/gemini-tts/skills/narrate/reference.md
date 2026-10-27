# Gemini TTS on Vertex AI: English and Tamil narration, setup guide

Last tested: 2026-10-27, with a Vertex AI **API key** on a Google Cloud free-trial project.

This guide is based on three things, and each claim says which one it comes from:

- **Tested**: I ran it with a real API key and checked the result (the audio was transcribed back or analysed by a Gemini model; nobody listened to it).
- **Docs**: stated on Google's pages (Gemini Enterprise Agent Platform docs, which is what Vertex AI is now called) but not tested by me.
- **Unverified**: from a search summary or a third party, or simply not tested.

Nobody has listened to the Tamil output for naturalness while writing this guide. Have a native Tamil speaker check anything you plan to publish.

---

## 1. Short version

| Question | Answer |
|---|---|
| Best model | `gemini-3.8-flash-tts` (flagship). `gemini-3.8-flash-lite-tts` is cheaper and faster and scored the same on clarity in my test. |
| Works with an API key? | **Yes** (tested), through `aiplatform.googleapis.com`. |
| English and Tamil? | **Yes**, both tested. The language is detected automatically. |
| Emotion control | `speechMetadata.style` for sustained delivery and inline tags such as `<laugh>`, `<sigh>`, `<short pause>` for moments. |
| Voices | 30 prebuilt voices. I tested 10 in Tamil, all clear. |
| Output | WAV, 24 kHz, 16-bit, mono. Convert to MP3 yourself. |
| Long scripts | Split into chunks of about 1,200 characters, same voice and style on each, then join the audio. |
| Status | **Preview.** It can change or be retired. |
| What does not work | The Cloud Text-to-Speech API with an API key, `gemini-4-argon`, `gemini-3.5-flash-tts`, system instructions, and some other model IDs. See section 13. |

---

## 2. What you need

1. A Google Cloud project with Vertex AI (now called **Gemini Enterprise Agent Platform**) available.
2. An **API key** for it. Create it in the Google Cloud console under *APIs & Services → Credentials*, or from the Vertex AI "Authenticate → API Key" panel on the welcome page.
3. Python 3 (the scripts here use only the standard library), `curl`, and optionally `ffmpeg` for converting and cleaning up audio.

Keep the key in an environment variable and never in code or in git:

```bash
export GOOGLE_API_KEY="paste-your-key-here"
```

In the environment this guide was tested in, the key was stored in a variable literally named `key`, so the test scripts read `os.environ["key"]`. `scripts/narrate.py` reads `GOOGLE_API_KEY` first and falls back to `key`.

### Restrict the key (do this first)

In the console, open the key and set **API restrictions** to the Vertex AI API only. Set a **budget alert** on the billing account. A leaked unrestricted key can be used by anyone to spend your credit.

---

## 3. Authentication options

### 3.1 API key (tested, the simplest)

Send the key in the `x-goog-api-key` header:

```
x-goog-api-key: <your key>
```

Tested alternatives:

| Method | Result |
|---|---|
| `x-goog-api-key` header | Works |
| `?key=<key>` in the URL | Works, but keys in URLs end up in logs, so prefer the header |
| No credential | `UNAUTHENTICATED: Request is missing required authentication credential. Expected OAuth 2 access token...` |

You do **not** put a project ID or location in the URL with an API key. The project is taken from the key. The documented examples with a project ID and `locations/global` are for bearer-token auth (below).

### 3.2 Application Default Credentials (docs-recommended, not tested)

ADC is Google's standard way for code to find credentials without a key string in the program. It checks, in order, a service-account key file (`GOOGLE_APPLICATION_CREDENTIALS`), then your own `gcloud auth application-default login`, then the identity of the Google Cloud service the code runs on. It produces short-lived tokens (about an hour).

The docs show REST calls using a bearer token:

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/global/publishers/google/models/gemini-3.8-flash-tts:generateContent" \
  -d @request.json
```

The docs also show the Google Gen AI SDK for Python (version 2.25.0 or later, created with `enterprise=True`, a `project` and a `location`). I did not test the SDK or bearer-token auth.

Safety note: on Google's own infrastructure ADC means there is no secret to leak. Outside it (a laptop, a CI job, a temporary cloud container) you must store either a service-account key file or a login token, and either can be more powerful than a restricted API key. Give a service account only the `Vertex AI User` role, and delete its key when done.

### 3.3 Which one for what

| Situation | Suggested |
|---|---|
| Quick narration jobs from your own computer | Restricted API key in an environment variable |
| Production on Google Cloud | ADC with an attached service account |
| Anything needing voice design or voice replication | ADC (these use the Voices API, which I did not test with a key) |

---

## 4. Models

| Model ID | English | Tamil | Notes |
|---|---|---|---|
| `gemini-3.8-flash-tts` | Tested | Tested | Flagship. Docs: 130 languages, best fidelity and acting. Launch stage: Preview. |
| `gemini-3.8-flash-lite-tts` | Tested | Tested | Docs: 101 languages, lower cost and latency. Same clarity score as the full model in my test (0.9%). Faster: 4.2 s versus about 6 s for the same paragraph. |
| `gemini-3.1-flash-tts-preview` | Tested | Tested | Previous generation. Uses the older request fields (see section 5.3). |
| `gemini-2.5-pro-preview-tts` | Tested | Tested | Older. Slowest (12.4 s) and slightly less accurate (2.6% versus 0.9%). |
| `gemini-2.5-flash-preview-tts`, `gemini-2.5-flash-tts` | Tested | Tested | Older. |

Both 3.8 models use the same request format, so switching is just a change of model ID (docs).

**Locations:** the 3.8 models are available in `global` only (docs). With an API key you use the plain endpoint `https://aiplatform.googleapis.com/v1/publishers/google/models/MODEL:generateContent`.

**Preview status:** Google can change or retire preview models. Do not build anything permanent on one without a fallback. Keep the model ID in a variable so you can change it in one place.

---

## 5. Making a request

### 5.1 Minimal curl (tested)

```bash
curl -s -X POST "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.8-flash-tts:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: $GOOGLE_API_KEY" \
  -d '{
    "contents": [{"role": "user", "parts": [{
      "text": "வணக்கம்! இது ஒரு சோதனை.",
      "speechMetadata": {"style": "warm, friendly"}
    }]}],
    "generationConfig": {
      "responseModalities": ["AUDIO"],
      "speechConfig": {"voiceConfig": {"voice": "Alnilam"}}
    }
  }' | python3 -c "import sys, json, base64; d = json.load(sys.stdin); open('out.wav', 'wb').write(base64.b64decode(d['candidates'][0]['content']['parts'][0]['inlineData']['data']))"
```

### 5.2 Minimal Python, standard library only (tested)

```python
import base64, json, os, urllib.request

URL = "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.8-flash-tts:generateContent"
body = {
    "contents": [{"role": "user", "parts": [{
        "text": "Hello! This is a test.",
        "speechMetadata": {"style": "warm, friendly"},
    }]}],
    "generationConfig": {
        "responseModalities": ["AUDIO"],
        "speechConfig": {"voiceConfig": {"voice": "Alnilam"}},
    },
}
req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
    "Content-Type": "application/json",
    "x-goog-api-key": os.environ["GOOGLE_API_KEY"],
})
audio = json.load(urllib.request.urlopen(req))["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
open("hello.wav", "wb").write(base64.b64decode(audio))
```

The response also contains `usageMetadata` (token counts) and `modelVersion`, which echoes the model that really served the request. Audio is about 25 output tokens per second in my tests.

### 5.3 Request fields

| Field | Purpose | Notes |
|---|---|---|
| `contents[].parts[].text` | The words to speak | Read as a **verbatim transcript** (docs). Do not write stage directions here, they may be spoken aloud. |
| `contents[].parts[].speechMetadata.style` | Emotion, pace, delivery | Short plain English works for Tamil text too (tested). |
| `contents[].parts[].speechMetadata.speaker` | Speaker label | For multi-speaker requests, on every turn. |
| `generationConfig.responseModalities` | `["AUDIO"]` | Required. |
| `generationConfig.speechConfig.voiceConfig.voice` | Voice name, such as `"Alnilam"` | The documented field for 3.8. |
| `generationConfig.speechConfig.languageCode` | Language hint, for example `ta-IN`, `en-US` | Optional. Accepted without error in my tests, and the language is auto-detected anyway. I did not test whether a wrong code changes the output. |
| `generationConfig.responseFormat[].audio.mimeType` | Output format | `AUDIO_WAV` (default), `AUDIO_L16`, `AUDIO_MULAW`, `AUDIO_ALAW` (section 11). |

The older voice field (`prebuiltVoiceConfig.voiceName`) still works on 3.8 (tested). I used only that older form on the 3.1 and 2.5 models, so I don't know whether they accept `voiceConfig.voice`.

---

## 6. Voices

### 6.1 The 30 prebuilt voices (from the docs)

| Voice | Character | Voice | Character |
|---|---|---|---|
| Achernar | Soft | Laomedeia | Upbeat |
| Achird | Friendly | Leda | Youthful |
| Algenib | Gravelly | Orus | Firm |
| Algieba | Smooth | Puck | Upbeat |
| Alnilam | Firm | Pulcherrima | Forward |
| Aoede | Breezy | Rasalgethi | Informative |
| Autonoe | Bright | Sadachbia | Lively |
| Callirrhoe | Easy-going | Sadaltager | Knowledgeable |
| Charon | Informative | Schedar | Even |
| Despina | Smooth | Sulafat | Warm |
| Enceladus | Breathy | Umbriel | Easy-going |
| Erinome | Clear | Vindemiatrix | Gentle |
| Fenrir | Excitable | Zephyr | Bright |
| Gacrux | Mature | Zubenelgenubi | Casual |
| Iapetus | Clear | Kore | Firm |

An invalid voice name returns a generic `INVALID_ARGUMENT: Request contains an invalid argument.` with no hint that the voice is the problem (tested), so check spelling and capitalisation first.

### 6.2 Tamil audition results (tested)

The same Tamil paragraph, same style line, 10 voices. Clarity was measured by transcribing each clip back and comparing it with the script (character error rate, lower is better). This measures clarity, not how pleasant the voice sounds.

| Voice | Error rate | Audio length |
|---|---|---|
| Puck | 0.0% | 16.8 s |
| Orus | 0.0% | 17.7 s |
| Kore, Sulafat, Gacrux, Alnilam, Achird | 0.9% | 18–19 s |
| Charon | 1.7% | 16.3 s |
| Fenrir, Algieba | 3.4% | 17–18 s |

The differences are 0 to 3 characters. Treat all ten as equally clear and choose by listening.

### 6.3 More voices (docs, not tested)

- **Extended Voice Library:** more than 2,000 preset voices, listed through the Voices API with `type` and `search` filters. It cannot filter by language or gender.
- **Voice design:** create a custom voice from a text description.
- **Voice replication:** clone a voice from reference and consent audio.
- Stored voices (`voice_...`) expire one year after last use. Replication keys (`voicekey_...`) expire after 7 days. I did not test any of these.

---

## 7. English and Tamil specifics

- **Language detection is automatic.** You do not need a language setting, but you can pass `speechConfig.languageCode` (`en-US`, `ta-IN`).
- **Tamil is listed as supported** on Google's pages. The docs page I read did not say which 3.8 model covers it, but both 3.8 models produced Tamil audio in my tests.
- **Write numbers as words.** Digits are read, but the model chooses how, and mixed digits and English words gave inconsistent choices. In my stress test, one voice read "2026" and "ChatGPT" in Tamil-style pronunciation and another read the English names in English. Spelling numbers out removes the guesswork. Example from the narration I generated: `ஆயிரத்து தொள்ளாயிரத்து நாற்பத்தைந்து` for 1945.
- **Brand names and English words inside Tamil text:** decide how you want them to sound, then write them in Tamil script (`யூடியூப்`) for Tamil-style pronunciation, or in Latin letters (`YouTube`) for English pronunciation. Listen and keep whichever your audience expects.
- **Inline tags stay in English** even in Tamil text (docs). Tested: `<laugh>` inside a Tamil sentence produced laughter and the word was not spoken.
- **Tamil words for large numbers:** in spoken Tamil, *lakh* (லட்சம்) and *crore* (கோடி) are common. The narration I generated used *million* and *trillion*, transliterated. Both are read correctly. Pick what your audience uses.
- **Quality is unproven.** No independent benchmark I found included Tamil. In an automated round-trip check, the generated Tamil narration came back with a 1.0% character error rate, and the differences were punctuation, spacing and spelling variants, not wrong words.

---

## 8. Controlling emotion and delivery

There are three levers: the `style` line, inline tags, and the text itself.

### 8.1 The `style` line

Put sustained emotion, pace and delivery in `speechMetadata.style`, in short plain English:

```json
"speechMetadata": {"style": "serious, authoritative documentary narrator, natural conversational pace"}
```

Docs guidance:
- Keep it short, or empty. Long "director's notes" blocks are linked to voice drift across calls.
- Reuse the same string on every chunk of a long script to keep a consistent baseline.
- Do not put age, gender, names or permanent accent changes in `style`. Choose a voice for that.
- For an emotion shift inside a script, split the script into separate parts and give each its own `style`.

**Pace is the strongest effect I measured.** The same short Tamil paragraph, same voice (Orus):

| Style line | Audio length |
|---|---|
| "energetic, upbeat YouTube host, fast and enthusiastic" | 12.2 s |
| "warm, confident documentary narrator, natural conversational pace" | about 17.7 s |
| "dramatic storyteller, expressive, with suspense and emphasis" | 21.1 s |
| "calm, soothing documentary narrator, slow and measured" | 23.1 s |

To make a script longer or shorter, change the style words, not the text. "Calm" slows Tamil by roughly 30%, so a script I wanted at two minutes came out at 2:28 with a calm style and 2:07 with "natural conversational pace".

### 8.2 Emotion: what worked and what did not (tested, with caveats)

I generated one neutral sentence ("The meeting is tomorrow at three o'clock in the main hall.") with six style lines, then asked a Gemini model to label the emotion it heard. That labeller is itself an imperfect model, so treat this as a rough guide, not proof.

| Style line | What the labeller heard | Audio length |
|---|---|---|
| "whispering, secretive" | whispering, slow | 4.6 s |
| "bored and tired" | bored, slow | 4.2 s |
| "sad and heartbroken, voice cracking" | whispering, slow (soft and slow, so partly right) | 5.1 s |
| "cold, formal newsreader" | neutral/formal, medium | 4.2 s |
| "cheerful and excited" | neutral/formal, medium (**not** detected) | 4.4 s |
| "angry and furious" | neutral/formal, medium (**not** detected) | 4.0 s |

Takeaways:
- Soft, slow, quiet styles (whisper, bored, sad) clearly register.
- High-energy styles (excited, angry) did **not** register strongly on a neutral sentence.
- Content matters. A sentence that already expresses an emotion ("I never thought we would actually win this") was heard as amazed and reflective in every style I tried, including "sad" and "joyful", though joyful got a laughing tone. If you want strong emotion, write words that carry it, add inline tags, and use `style` to push further.

### 8.3 Inline tags (tested)

Put short human sounds directly in the text with **angle brackets**. The docs say angle brackets give the highest audio quality, and the 3.1 model used square brackets.

| Tag | Result in my test |
|---|---|
| `<laugh>` | Laughter, word not spoken |
| `<sigh>` | Sigh and pause, word not spoken |
| `<short pause>` | Added a pause. The same sentence went from 2.6 s to 4.5 s |
| `<long pause>` | The same sentence went to 5.1 s |
| `[laughs]` and `(laughs)` | Also produced laughter without being spoken |

The pause tags added about 2 to 2.5 seconds each in this single test, which is longer than a natural beat, so for a short beat use a comma, a dash (`--`) or an ellipsis (`...`) instead.

Other tags the docs list: `<gasp>`, `<throat-clearing>`, `<argh>`, `<breath>`, `<cough>`, `<laughter>`, `<sob>`, `<whispers>` or `<whispering>`, `<yawn>`. I only tested the ones in the table. Use human vocalisations, not sound effects (docs).

### 8.4 Pacing and emphasis in the text (docs, not tested separately)

- Commas, dashes and ellipses shape pauses and hesitation.
- Capitalising a word stresses it.
- A rate in the style line ("speaking slowly", "speaking rapidly") sets the pace for the whole part.
- Natural transcripts with small disfluencies ("Oh uh yeah I think... hm") sound less robotic.

### 8.5 Style recipes to start from

| Use | Style line |
|---|---|
| Documentary narration | `serious, authoritative documentary narrator, natural conversational pace, clear Tamil pronunciation` |
| Energetic YouTube intro | `energetic, upbeat YouTube host, fast and enthusiastic` |
| Calm explainer | `calm, soothing narrator, slow and measured` |
| Dramatic story | `dramatic storyteller, expressive, with suspense and emphasis` |
| Quiet, serious moment | `whispering, secretive` |

---

## 9. Multi-speaker dialogue (tested)

Docs: exactly **two** speakers per request. For more speakers, or to mix custom voices, generate each turn separately and join the audio.

```json
{
  "contents": [{"role": "user", "parts": [
    {"text": "Did you see the numbers?", "speechMetadata": {"speaker": "Anna"}},
    {"text": "Yes, they are staggering.", "speechMetadata": {"speaker": "Ben"}}
  ]}],
  "generationConfig": {
    "responseModalities": ["AUDIO"],
    "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
      {"speaker": "Anna", "voiceConfig": {"voice": "Kore"}},
      {"speaker": "Ben",  "voiceConfig": {"voice": "Puck"}}
    ]}}
  }
}
```

Tested: it returned 4.4 s of audio, and a Gemini model reported two distinct speakers of different genders. The `speaker` on each part must match a speaker in `speakerVoiceConfigs`. The older `prebuiltVoiceConfig` form also worked.

Docs (not tested): wrap short listener reactions in pipes inside the current speaker's turn, such as `|oh hmm|`, to create back-channel sounds without a separate turn. Overlapping speech is said to work best on `gemini-3.8-flash-tts`.

---

## 10. Long narration (YouTube-length scripts)

### 10.1 Limits

- Docs (Gemini API page): input 8,192 tokens, output 16,384 tokens.
- In a test, a single request with **12,000 characters** of English returned about 916 seconds (15 minutes) of audio in 91 seconds, so the real limits on this endpoint are higher than documented. I did **not** check whether the full text was spoken or whether quality held up across 15 minutes, so do not rely on it.
- Tamil text tends to use more tokens than the same sentence in English, but I did not measure by how much.

### 10.2 Recommended approach

1. Split the script into paragraphs of roughly 1,200 characters or fewer, never splitting mid-sentence.
2. Use the **same voice and the same short style line** for every chunk.
3. Generate each chunk, then join the audio with a short silence (about 0.5 s) between chunks.
4. Listen, and re-generate only the chunks that need it.
5. Normalise loudness and convert to MP3 or whatever your editor needs.

`scripts/narrate.py` in this skill does steps 1 to 3 (tested on a Tamil script: 5 chunks, 131 seconds):

```bash
export GOOGLE_API_KEY="..."
python3 scripts/narrate.py script.txt -o narration.wav \
  --voice Alnilam \
  --style "serious, authoritative documentary narrator, natural conversational pace, clear Tamil pronunciation" \
  --max-chars 1200 --pause 0.5
```

It retries on HTTP 429, 500 and 503, stops with a clear message on other errors, and checks that every chunk comes back in the same audio format.

### 10.3 Post-processing with ffmpeg (tested)

```bash
# WAV to MP3
ffmpeg -i narration.wav -codec:a libmp3lame -q:a 2 narration.mp3

# Even out loudness (about -16 LUFS, common for online video) and resample to 48 kHz for video editors
ffmpeg -i narration.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 narration_48k.wav
```

### 10.4 Timing and cost planning

- Generation took about 6 seconds for about 17 seconds of Tamil audio (single request), so a 10-minute narration takes a few minutes if generated chunk by chunk. A single large request was faster per second of audio.
- Audio is about 25 output tokens per second, so 10 minutes is about 15,000 tokens.
- Natural-pace Tamil speech ran at about 13 characters per second (without spaces and punctuation).

---

## 11. Output formats and streaming

### 11.1 Formats (tested)

| `responseFormat` mime type | Result in my test |
|---|---|
| (default) | `audio/wav` with a RIFF header, 24 kHz, 16-bit, mono |
| `AUDIO_L16` | `audio/l16; rate=24000; channels=1`, raw PCM, no header |
| `AUDIO_MULAW` | `audio/mulaw; rate=8000; channels=1` (telephone quality) |
| `AUDIO_ALAW` | Listed in the docs, not tested |

Not supported (docs): MP3, Ogg Opus, and choosing a sample rate. Convert on your side with ffmpeg. Example of the request field:

```json
"generationConfig": {"responseFormat": [{"audio": {"mimeType": "AUDIO_L16"}}]}
```

### 11.2 Streaming (tested)

Both of these returned HTTP 200 with audio data:

```
POST .../models/gemini-3.8-flash-tts:streamGenerateContent
POST .../models/gemini-3.8-flash-tts:streamGenerateContent?alt=sse
```

Docs: streaming returns raw 16-bit PCM chunks by default. I did not play or reassemble the streamed audio, so check chunk handling before relying on it.

---

## 12. Cost and quotas

All unverified. I did not see Google's pricing page.

- A search summary of Google Cloud's page says the 3.8 TTS models are **free during Preview through December 31, 2026**, then **$1.00 per million input text tokens and $18.00 per million output audio tokens** from January 1, 2027.
- A third-party listing (OpenRouter) shows $0.50 and $9.00 for the same two prices. The two disagree, so check Google's pricing page.
- Using the audio rate of about 25 tokens per second, 10 minutes of narration is about 15,000 output tokens, which is roughly $0.27 at the higher listed price. Text input is small by comparison.
- Quotas and rate limits: not found in the pages I could read. Voice creation has a per-project, per-minute quota (docs). In my tests I hit no rate limits, but I ran only a few dozen requests.
- Whether trial credit applies the same way as a paid account is something to check in your billing console.

---

## 13. What does not work (tested)

| Attempt | Result | Why or what to do |
|---|---|---|
| Cloud Text-to-Speech API (`texttospeech.googleapis.com`) with an API key | `401 UNAUTHENTICATED: API keys are not supported by this API` | That API needs OAuth or a service account. The 3.8 models are not on it anyway (docs). Use the `aiplatform.googleapis.com` route. |
| `gemini-4-argon`, `-preview`, `-001`, `gemini-4.0-argon`, `gemini-argon-4` | 404 on every variant | Listed in the console and on Google's pages, but not reachable with this key and project. May be gated by billing, allowlist or key type. |
| `gemini-3.5-flash-tts` | 404 | Not a TTS model ID I could reach. |
| `gemini-3.8-flash-tts-20260922`, `gemini-3.8-flash-tts-preview` | 404 | Not valid IDs. Use `gemini-3.8-flash-tts`. |
| `systemInstruction` in the request | `400 INVALID_ARGUMENT` | Docs: not supported. Put directions in `speechMetadata.style` instead. |
| Stage directions inside `text` (docs) | May be spoken aloud | 3.8 reads `text` as a verbatim transcript. Use `style` and tags. |
| Wrong voice name | Generic `INVALID_ARGUMENT` | The message does not name the voice. |
| No key | `UNAUTHENTICATED` | Add the `x-goog-api-key` header. |
| MP3 or Ogg output, custom sample rate | Not supported (docs) | Convert with ffmpeg. |
| More than 2 speakers in one request | Not supported (docs) | Generate each turn separately and join. |
| Strong excited or angry delivery from `style` alone on neutral text | Weak in my test (section 8.2) | Write emotional wording and add tags. |
| Regional endpoints (docs) | The 3.8 models are `global` only | Use the plain `aiplatform.googleapis.com` endpoint. |

**Inconsistent with the docs:** the docs say `temperature`, `topP` and `topK` are rejected with `INVALID_ARGUMENT`, and that `candidateCount` should be removed. In my tests with an API key, `temperature`, `topP` and `candidateCount` were accepted with no error. Do not rely on either behaviour. Leave them out.

**A 404 does not tell you why.** The message reads "was not found or your project does not have access to it", so a typo, a retired model and a gated model look identical. The region named in the message (for example `us-central1`) is chosen by the server, not by you.

Models other than TTS, tested with the same key, for reference:

| Works | Does not work (404) |
|---|---|
| `gemini-3.8-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview`, `gemini-3-flash-preview`, `gemini-2.5-flash-image` | `gemini-4-argon`, `gemini-3-pro-preview`, `gemini-3-pro`, `gemini-3-flash`, `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-3.1-flash-lite-preview`, `gemini-3-pro-image-preview` |

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 UNAUTHENTICATED ... API keys are not supported` | You called the Cloud Text-to-Speech API | Call `aiplatform.googleapis.com/.../publishers/google/models/...:generateContent` instead. |
| `404 NOT_FOUND ... not found or your project does not have access` | Wrong model ID, retired model, or no access | Check spelling against section 4. Try the same call with `gemini-3.8-flash-tts`. If that works, the other model is gated or retired for you. |
| `400 INVALID_ARGUMENT` with no detail | Bad voice name, `systemInstruction`, or a malformed field | Simplify to the minimal request in 5.1, then add fields back one at a time. |
| Response has no `inlineData` | Request blocked or empty | Print the whole response, shorten the text, and try again. |
| Timeout on long text | Large request | Chunk the script (section 10). Set a client timeout of at least 300 seconds. |
| A tag or direction is read aloud | The words were in `text` as plain words | Use angle brackets for tags and move directions into `style`. |
| Voice or tone drifts between chunks | Style line changed, or too much prompt text | Reuse one short style string on every chunk. |
| Numbers or brand names sound wrong | Digits or mixed scripts | Spell numbers as words and write names the way you want them said. |
| Output sounds too slow | Style such as "calm" slows speech by about 30% | Use "natural conversational pace". |

---

## 15. Before you publish

- **Have a Tamil speaker listen.** My checks measure clarity, not naturalness.
- **Check Google's terms** for commercial use of generated audio, and whether the audio carries an audio watermark. The pages I read did not cover either.
- **Check YouTube's policy** on synthetic voices and disclosure of AI-generated content. I did not verify it.
- **Check the facts in your script.** The sample World War II narration used ranges because sources disagree.
- **Treat Preview as unstable.** Keep the generated WAV files, not just the script.

---

## 16. Not tested

- Application Default Credentials and bearer-token requests
- The Google Gen AI SDK
- Voice design, voice replication and the Extended Voice Library
- `AUDIO_ALAW`
- Multi-speaker `|backchannel|` syntax
- The tags in the docs list other than `<laugh>`, `<sigh>`, `<short pause>` and `<long pause>`
- Whether `speechConfig.languageCode` changes the result
- Playback quality of streamed audio
- Rate limits and quotas
- Pricing and billing

---

## 17. Sources

- [Gemini 3.8 Flash TTS (Google Cloud docs)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash-tts)
- [Generate speech with Gemini TTS (Agent Platform overview)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/text-to-speech/overview)
- [Gemini TTS prompting guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/text-to-speech/prompting-guide)
- [Migrate to Gemini 3.8 TTS](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/text-to-speech/migration-guide)
- [Gemini 3.8 Flash TTS (Gemini API docs)](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts)
- [Vertex AI in express mode overview](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/express-mode/overview)
- [Gemini 3.8 Flash TTS review (eesel.ai)](https://www.eesel.ai/blog/gemini-3-8-flash-tts-review)
- [Gemini 3.8 Flash TTS listing (OpenRouter)](https://openrouter.ai/google/gemini-3.8-flash-tts)

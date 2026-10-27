---
name: narrate
description: Generate English or Tamil voice narration audio from a script using Gemini TTS on Vertex AI with an API key. Use when the user asks to narrate or voice over a script, make a text-to-speech audio file, compare voices or styles, add emotion or pauses to narration, or set up or debug Gemini/Vertex TTS.
---

# Narrate with Gemini TTS (Vertex AI)

Turns a script into a WAV or MP3 narration in English or Tamil. The full tested guide
is in `reference.md` (same folder as this file). Read the section you need rather than
the whole file. Scripts are in `scripts/`.

## Before you start

1. The Vertex AI API key must be in the environment as `GOOGLE_API_KEY`, or as `key`.
   Check that it exists without printing it:
   `[ -n "${GOOGLE_API_KEY:-$key}" ] && echo set || echo missing`
2. Never print, echo, log, or commit the key. If it is missing, tell the user how to set it
   (`reference.md` section 2) and stop. Do not ask them to paste it into chat.
3. Default model is `gemini-3.8-flash-tts` (Preview, so it can change). If it returns 404,
   try `gemini-3.8-flash-lite-tts`, then see `reference.md` sections 4 and 13.

## Workflow

1. **Get the script, the language, and the delivery.** If the user gave no voice or style,
   use voice `Alnilam` and style
   `serious, authoritative documentary narrator, natural conversational pace`
   (add `, clear Tamil pronunciation` for Tamil). Offer to audition other voices
   (`reference.md` section 6).
2. **Prepare the text.**
   - Write numbers as words, in the script's language.
   - Write brand names the way they should be pronounced (Tamil script for Tamil-style,
     Latin letters for English-style).
   - Put short sounds in angle brackets in English: `<laugh>`, `<sigh>`, `<short pause>`.
     Keep stage directions out of the text, because the model reads text word for word.
   - If the user wants facts in the script, use ranges and "roughly" where sources differ.
3. **Generate.** Save the script to a UTF-8 text file, then:
   ```bash
   python3 scripts/narrate.py script.txt -o narration.wav \
     --voice Alnilam --style "<style line>" --max-chars 1200 --pause 0.5
   ```
   Use the same voice and the same style line for every chunk. To change pace, change the
   style words ("calm" is about 30% slower, "energetic" about 30% faster).
4. **Verify.** Transcribe the audio back and compare with the script:
   ```bash
   python3 scripts/verify.py narration.wav script.txt --lang ta   # or --lang en
   ```
   A rate under about 2% with only spelling or spacing differences is good. Regenerate any
   chunk with wrong or missing words. The transcriber can also be wrong, so report it as
   a clarity check only.
5. **Deliver.** Give the user the audio file. Convert if asked:
   `ffmpeg -i narration.wav -codec:a libmp3lame -q:a 2 narration.mp3`
   Loudness and 48 kHz resample: see `reference.md` section 10.3.

## Rules that save time

- Call `aiplatform.googleapis.com/v1/publishers/google/models/<model>:generateContent`
  with the `x-goog-api-key` header. The Cloud Text-to-Speech API rejects API keys.
- Voice field: `speechConfig.voiceConfig.voice`. Delivery: `parts[].speechMetadata.style`.
  Do not send `systemInstruction` (400 error). Do not send `temperature`, `topP`, `topK`.
- Strong emotion needs emotional wording plus tags. `style` alone is weak for excited or
  angry on a neutral sentence, but whisper, bored and sad register clearly.
- Pause tags add about 2 seconds. For a short beat use a comma, a dash, or an ellipsis.
- Multi-speaker allows exactly two speakers per request (`reference.md` section 9).
- `gemini-4-argon` and `gemini-3.5-flash-tts` returned 404 with this kind of key. Do not
  retry them unless the user says their access changed.

## Always tell the user

- Tamil naturalness has not been judged by a native speaker, so ask them to listen.
- The model is in Preview, so keep the generated audio and not just the script.
- Check Google's terms and YouTube's synthetic-voice disclosure rules before publishing.

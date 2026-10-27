# narration-tools

A Claude Code plugin marketplace with one plugin, **gemini-tts**, containing a skill
(`/gemini-tts:narrate`) that narrates English and Tamil scripts with Gemini TTS on Vertex AI.

## Install on any device

Needs Claude Code, `git`, and read access to this repository from that device.

```bash
claude plugin marketplace add karikala-chozhan-the-great/first-repo
claude plugin install gemini-tts@narration-tools
```

Then ask for what you want ("narrate this script in Tamil") or run `/gemini-tts:narrate`.

Each device or cloud environment also needs your Vertex AI API key as an environment
variable (`GOOGLE_API_KEY`). The key is never stored in this repository.

## Updates

After you push changes here, other devices get them with:

```bash
claude plugin marketplace update narration-tools
claude plugin update gemini-tts@narration-tools
```

Or turn on auto-update for the marketplace under **Marketplaces** in `/plugin`.

## If the repository is private

Claude Code uses the git credentials already on the device. On GitHub run
`gh auth login` and then `gh auth setup-git`. If the device has no GitHub SSH key,
set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`.

## Contents

```
.claude-plugin/marketplace.json
plugins/gemini-tts/
├── .claude-plugin/plugin.json
└── skills/narrate/
    ├── SKILL.md            short workflow and rules
    ├── reference.md        full tested guide
    └── scripts/
        ├── narrate.py      chunk a script, call the model, stitch the audio
        └── verify.py       transcribe the result and compare with the script
```

`tamil-tts-auditions.zip` holds sample audio from the voice, style and model benchmark.

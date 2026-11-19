"""Voiceover. ElevenLabs when a key and voice are set (human-sounding), otherwise free edge-tts.
If ElevenLabs fails for any reason (quota, outage), it falls back to edge-tts so a day is never lost.
Returns the mp3 path, or None if no voice could be made (the video is then text only)."""
import asyncio, json, os, ssl, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    VCFG = json.load(open(os.path.join(ROOT, "config.json"))).get("voice", {})
except Exception:
    VCFG = {}
EDGE_VOICE = os.environ.get("LM_VOICE", VCFG.get("edge_voice", "en-US-AvaNeural"))
EDGE_RATE = os.environ.get("LM_VOICE_RATE", "-6%")

if os.environ.get("LOCAL_CA"):  # only for testing behind a proxy; not needed on GitHub
    _orig = ssl.create_default_context

    def _ctx(*a, **k):
        k.pop("cafile", None)
        c = _orig(*a, **k)
        c.load_verify_locations(os.environ["LOCAL_CA"])
        return c
    ssl.create_default_context = _ctx


def _eleven(text, out_mp3, hook=False):
    key, vid = os.environ.get("ELEVENLABS_API_KEY"), VCFG.get("eleven_voice_id")
    if not key or not vid:
        return None
    body = json.dumps({"text": text, "model_id": VCFG.get("eleven_model", "eleven_multilingual_v2"),
                       "voice_settings": (VCFG.get("hook_settings", {"stability": 0.30, "similarity_boost": 0.8,
                                                                      "style": 0.60, "use_speaker_boost": True}) if hook else
                                          VCFG.get("eleven_settings", {"stability": 0.45, "similarity_boost": 0.8,
                                                                        "style": 0.25, "use_speaker_boost": True}))}).encode()
    # with-timestamps returns the audio plus when each character is spoken, so words can pop in as they are said
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps"
                                 f"?output_format=mp3_44100_128",
                                 data=body, headers={"xi-api-key": key, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        res = json.load(r)
    import base64
    open(out_mp3, "wb").write(base64.b64decode(res["audio_base64"]))
    al = res.get("alignment") or res.get("normalized_alignment") or {}
    words, cur, t0 = [], "", None
    for ch, st in zip(al.get("characters", []), al.get("character_start_times_seconds", [])):
        if ch.isspace():
            if cur:
                words.append([cur, t0])
            cur, t0 = "", None
        else:
            if not cur:
                t0 = st
            cur += ch
    if cur:
        words.append([cur, t0])
    json.dump(words, open(out_mp3 + ".words.json", "w"))
    return out_mp3 if os.path.getsize(out_mp3) > 1000 else None


def _edge(text, out_mp3):
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE).save(out_mp3))
    return out_mp3 if os.path.getsize(out_mp3) > 1000 else None


def speak(text, out_mp3, hook=False):
    """hook=True: the cold open line, read with more feeling (less stable, more style)."""
    try:
        got = _eleven(text, out_mp3, hook)
        if got:
            return got
    except Exception as e:
        print("ElevenLabs failed, using the free voice for this line:", str(e)[:160])
    try:
        return _edge(text, out_mp3)
    except Exception as e:
        print("voice failed, continuing without it:", str(e)[:120])
        return None

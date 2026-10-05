#!/usr/bin/env python3
"""Makes short ElevenLabs voice samples so we can pick a voice for the game.

Reads the API key from the ELEVENLABS_API_KEY environment variable, or from
~/.config/elevenlabs/key. Writes MP3s and a list of samples to the output folder.
Costs about 1,400 credits per run (12 samples; flash samples cost half).
"""
import json, os, pathlib, ssl, sys, urllib.error, urllib.request

# Homebrew Python may not find certificates; use the system's own
CTX = ssl.create_default_context(cafile='/etc/ssl/cert.pem' if os.path.exists('/etc/ssl/cert.pem') else None)

def key():
    k = os.environ.get('ELEVENLABS_API_KEY')
    if not k:
        p = pathlib.Path.home() / '.config/elevenlabs/key'
        if p.exists():
            k = p.read_text().strip()
    if not k:
        sys.exit('No API key: set ELEVENLABS_API_KEY or put it in ~/.config/elevenlabs/key')
    return k

API = 'https://api.elevenlabs.io/v1'
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'voice-demo')

# what the game would actually say: a question with its blanks, then the answer
SAMPLE = ("What is the chief end of man? ... To glorify God, and to enjoy Him forever. "
          "... Christian ran from the City of Destruction toward the Celestial City.")

MODELS = {
    'eleven_v3': 'v3 (most expressive) - 1 credit/char',
    'eleven_multilingual_v2': 'Multilingual v2 (rich) - 1 credit/char',
    'eleven_flash_v2_5': 'Flash v2.5 (cheap, fast) - 0.5 credit/char',
}
# warm storytellers, a mix of men and women, US and British
WANT = ['George', 'Brian', 'Alice', 'Matilda', 'Charlotte', 'Bill', 'Lily', 'Daniel', 'Jessica', 'Chris']

def req(path, body=None):
    r = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                               headers={'xi-api-key': key(), 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, context=CTX) as f:
            return f.read()
    except urllib.error.HTTPError as e:
        sys.exit(f'{path.split("?")[0]} -> {e.code}: {e.read().decode()[:400]}')

def main():
    voices = json.loads(req('/voices'))['voices']
    by_name = {v['name'].split(' ')[0]: v for v in voices}
    pick = [by_name[n] for n in WANT if n in by_name][:5]
    OUT.mkdir(parents=True, exist_ok=True)
    plan = []
    for v in pick:
        plan.append((v, 'eleven_multilingual_v2'))
        plan.append((v, 'eleven_flash_v2_5'))
    plan.append((pick[0], 'eleven_v3'))
    plan.append((pick[2] if len(pick) > 2 else pick[0], 'eleven_v3'))
    out = []
    for v, m in plan:
        f = OUT / f"{v['name'].split(' ')[0].lower()}-{m}.mp3"
        if not f.exists():
            audio = req(f"/text-to-speech/{v['voice_id']}?output_format=mp3_44100_64",
                        {'text': SAMPLE, 'model_id': m,
                         'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}})
            f.write_bytes(audio)
        lab = v.get('labels') or {}
        out.append({'voice': v['name'], 'model': m, 'modelLabel': MODELS[m], 'file': f.name,
                    'desc': ', '.join(x for x in [lab.get('gender'), lab.get('accent'), lab.get('age'),
                                                   lab.get('descriptive') or lab.get('description')] if x)})
        print('made', f.name)
    (OUT / 'samples.json').write_text(json.dumps(out, indent=1))
    print('chars per sample', len(SAMPLE), 'samples', len(out))

main()

#!/usr/bin/env python3
"""Records the game's narration with ElevenLabs (George, Flash v2.5).

For each question it makes three clips: the question (audio/q/N.mp3), the
answer with "blank" in each gap (audio/f/N.mp3), and the full answer
(audio/a/N.mp3). It also records every word that can appear in a word bank
(audio/w/<word>.mp3), and writes audio/manifest.json.

Reads the API key from ELEVENLABS_API_KEY or ~/.config/elevenlabs/key.
Clips that already exist are skipped, so it is safe to run again; delete a
clip to record it again. Usage: python3 tools/voice_build.py [--dry]
"""
import concurrent.futures, json, os, pathlib, re, ssl, subprocess, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIO = ROOT / 'audio'
VOICE = 'JBFqnCBsd6RMkjVDRZzb'  # George - Warm, Captivating Storyteller
MODEL = 'eleven_flash_v2_5'
CTX = ssl.create_default_context(cafile='/etc/ssl/cert.pem' if os.path.exists('/etc/ssl/cert.pem') else None)

def key():
    k = os.environ.get('ELEVENLABS_API_KEY')
    p = pathlib.Path.home() / '.config/elevenlabs/key'
    if not k and p.exists():
        k = p.read_text().strip()
    if not k:
        sys.exit('No API key: set ELEVENLABS_API_KEY or put it in ~/.config/elevenlabs/key')
    return k

def game_text():
    """Pulls the questions and the distractor words out of index.html with node."""
    js = r"""
    const h=require('fs').readFileSync(process.argv[1],'utf8');
    const QS=eval('['+h.match(/const QS=\[([\s\S]*?)\n\];/)[1]+']');
    const i=h.indexOf('DISTRACTOR_POOL'),s=h.indexOf('{',i);let d=0,j=s;
    for(;j<h.length;j++){if(h[j]=='{')d++;if(h[j]=='}'){d--;if(!d)break;}}
    const P=eval('('+h.slice(s,j+1)+')');
    console.log(JSON.stringify({QS,words:Object.values(P).flat()}));"""
    out = subprocess.run(['node', '-e', js, str(ROOT / 'index.html')], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)

def slug(w):
    return re.sub(r'[^a-z0-9]+', '-', w.lower()).strip('-')

def spoken(t):
    t = re.sub(r'_{2,}', 'blank', t)
    return t.replace('LORD', 'Lord')

def jobs():
    data = game_text()
    out = []
    for i, q in enumerate(data['QS']):
        out.append((AUDIO / 'q' / f'{i}.mp3', spoken(q['q'])))
        out.append((AUDIO / 'f' / f'{i}.mp3', spoken(q['dp'])))
        out.append((AUDIO / 'a' / f'{i}.mp3', spoken(q['full'])))
    words = {}
    for q in data['QS']:
        for b in q['blanks']:
            words.setdefault(slug(b), b)
    for w in data['words']:
        words.setdefault(slug(w), w)
    for s, w in sorted(words.items()):
        out.append((AUDIO / 'w' / f'{s}.mp3', spoken(w)))
    return out, len(data['QS']), sorted(words)

def tts(text):
    body = json.dumps({'text': text, 'model_id': MODEL,
                       'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}}).encode()
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_64'
    for attempt in range(6):
        r = urllib.request.Request(url, data=body, headers={'xi-api-key': key(), 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(r, context=CTX, timeout=60) as f:
                return f.read()
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:300]
            if e.code in (429, 500, 502, 503) and attempt < 5:
                time.sleep(2 * (attempt + 1))
                continue
            raise SystemExit(f'ElevenLabs {e.code}: {msg}')

def main():
    todo, nq, words = jobs()
    need = [(p, t) for p, t in todo if not p.exists()]
    chars = sum(len(t) for _, t in need)
    print(f'{len(todo)} clips, {len(need)} to record, {chars} characters (~{chars // 2} credits on Flash)')
    if '--dry' in sys.argv:
        return
    def one(job):
        p, t = job
        p.parent.mkdir(parents=True, exist_ok=True)
        data = tts(t)
        tmp = p.with_suffix('.part')
        tmp.write_bytes(data)
        tmp.rename(p)
        return p
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for _ in ex.map(one, need):
            done += 1
            if done % 50 == 0:
                print(f'  {done}/{len(need)}')
    (AUDIO / 'manifest.json').write_text(json.dumps({'voice': 'George', 'model': MODEL, 'questions': nq, 'words': words}))
    print('done')

main()

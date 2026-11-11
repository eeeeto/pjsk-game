#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 PJSK 补充曲库（lz_pack2）转码并合并进 songs/ 与 manifest.js"""
import json, os, re, subprocess, glob

OUT = '/root/.codebuddy/artifact/lz_pack2'
SONG_DIR = '/workspace/pjsk-game/songs'
MANIFEST = os.path.join(SONG_DIR, 'manifest.js')

UNIT_RE = ['MORE MORE JUMP！', 'MORE MORE JUMP', 'Vivid BAD SQUAD',
           'ワンダーランズ×ショウタイム', '25時、ナイトコードで。', 'Leo need', 'Leo/need']
VO = ['初音ミク', '重音テト', '歌愛ユキ', '鏡音リン', '鏡音レン', '巡音ルカ', 'MEIKO', 'KAITO', 'flower']

# 归类关键词
UNIT_OF = [
    ('ももいろの鍵', 'mmj'), ('月光', 'vbs'), ('ULTRA C', 'vbs'), ('Ready Steady', 'vbs'),
    ('KING', 'wxs'), ('神のまにまに', 'wxs'), ('needLe', 'leoneed'),
    ('25時の情熱', 'n25'), ('Bad Apple', 'n25'), ('携帯恋話', 'n25'),
]
COVER1 = {k: f'assets/covers/{k}1.jpg' for k in ['leoneed', 'mmj', 'vbs', 'wxs', 'n25']}
LABEL = {'leoneed': 'Leo/need', 'mmj': 'MORE MORE JUMP！', 'vbs': 'Vivid BAD SQUAD',
         'wxs': 'ワンダーランズ×ショウタイム', 'n25': '25時、ナイトコードで。'}

raw = json.load(open(os.path.join(OUT, 'raw_list.json'), encoding='utf-8'))

def convert(src, dest):
    r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src,
                        '-codec:a', 'libmp3lame', '-b:a', '192k', dest],
                       capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(dest)

def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                          '-of', 'json', path], capture_output=True, text=True).stdout
    try:
        return float(json.loads(out)['format']['duration'])
    except Exception:
        return 0.0

def parse(name):
    stem = re.sub(r'\.(mp3|flac|wav|m4a)$', '', name, flags=re.I).strip()
    if ' - ' in stem:
        left, title = stem.rsplit(' - ', 1)
    else:
        left, title = '', stem
    left = re.sub(r'\s+', ' ', left).strip(' -　')
    unit = next((u for kw, u in UNIT_OF if kw.lower() in title.lower()), None)
    if unit is None:
        unit = 'other'
    # 歌手（feat 里的虚拟歌手）+ 创作者
    singers = []
    for v in VO:
        if re.search(re.escape(v), left, re.I):
            singers.append(v)
    creators = left
    for u in UNIT_RE:
        creators = re.sub(re.escape(u), ' ', creators)
    for v in VO:
        creators = re.sub(re.escape(v), ' ', creators, flags=re.I)
    creators = re.sub(r'\s+', ' ', creators).strip(' -　')
    artist = '、'.join(singers) if singers else (creators or LABEL.get(unit, ''))
    return title.strip(' -　'), artist, creators, unit

cur = open(MANIFEST, encoding='utf-8').read()
data = json.loads(cur[cur.index('['):cur.rindex(']') + 1])
have_titles = {e['title'].strip().lower() for e in data}

used = {int(re.search(r's(\d+)\.mp3', f).group(1)) for f in glob.glob(os.path.join(SONG_DIR, 's*.mp3'))}
nxt = max(used) + 1 if used else 1

added, skipped = [], []
seen_local = set()
for item in raw:
    src = item['file']
    if not os.path.exists(src) or os.path.getsize(src) < 100000:
        print('skip (missing/small):', item['name']); continue
    title, artist, creators, unit = parse(item['name'])
    if unit == 'other':
        print('!! no unit match:', title); continue
    key = title.strip().lower()
    if key in have_titles or key in seen_local:
        skipped.append(title); continue
    seen_local.add(key)
    dest = os.path.join(SONG_DIR, f's{nxt}.mp3')
    ok = True
    if src.lower().endswith('.flac'):
        ok = convert(src, dest)
    else:
        import shutil; shutil.copy(src, dest)
    if not ok:
        print('skip broken:', title); continue
    dur = probe(dest)
    if not dur:
        print('skip no-duration:', title); os.remove(dest); continue
    credit = f'プロデュース：{creators}' if creators else ''
    data.append({'title': title, 'artist': artist, 'credit': credit, 'unit': unit,
                 'game': True, 'duration': round(dur, 2), 'file': f'songs/s{nxt}.mp3',
                 'full': dur > 120, 'cover': COVER1[unit]})
    added.append((unit, title, artist))
    nxt += 1

order = {k: i for i, k in enumerate(['leoneed', 'mmj', 'vbs', 'wxs', 'n25', 'vocaloid', 'other', 'zijiang', 'egirls'])}
data.sort(key=lambda e: (order.get(e['unit'], 9), e['title']))
js = 'window.SONGS = ' + json.dumps(data, ensure_ascii=False, indent=1) + ';\n'
open(MANIFEST, 'w', encoding='utf-8').write(js)
print(f'added {len(added)}; skipped {len(skipped)}; total {len(data)}')
for u, t, a in added: print(f' + [{u}] {t} | {a}')
for t in skipped: print(' dup:', t)

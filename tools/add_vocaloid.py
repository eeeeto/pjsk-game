#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把下载好的ボカロ曲目合并进 songs/ 与 manifest.js"""
import json, os, re, shutil, subprocess, glob

OUT = '/root/.codebuddy/artifact/lz_vocaloid'
SONG_DIR = '/workspace/pjsk-game/songs'
MANIFEST = os.path.join(SONG_DIR, 'manifest.js')

raw = json.load(open(os.path.join(OUT, 'raw_list.json'), encoding='utf-8'))

def parse(name):
    s = re.sub(r'\.mp3$', '', name, flags=re.I).strip()
    if ' - ' in s:
        left, title = s.rsplit(' - ', 1)
    else:
        left, title = '', s
    # feat 信息保留在标题里即可；左侧为创作者 + 演唱虚拟歌手
    left = re.sub(r'[\s　]+', ' ', left).strip(' -　')
    # 识别演唱者（虚拟歌手）
    VO = ['初音ミク', '重音テト', '歌愛ユキ', '鏡音リン', '鏡音レン', '巡音ルカ', 'MEIKO', 'KAITO',
          'v flower', 'flower']
    singers = [v for v in VO if re.search(re.escape(v), left, re.I)]
    seen, ss = set(), []
    for n in singers:
        if n.lower() not in seen:
            seen.add(n.lower()); ss.append(n)
    creators = left
    for v in VO:
        creators = re.sub(re.escape(v), ' ', creators, flags=re.I)
    creators = re.sub(r'feat\.?\s*', ' ', creators, flags=re.I)
    creators = re.sub(r'[\s　]+', ' ', creators).strip(' -　')
    artist = ('、'.join(ss) if ss else (creators or 'ボカロ'))
    credit = f'作编曲：{creators}' if creators and ss else ''
    return title.strip(' -　'), artist, credit

def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                          '-of', 'json', path], capture_output=True, text=True).stdout
    try:
        return float(json.loads(out)['format']['duration'])
    except Exception:
        return 0.0

# 现有 manifest
cur = open(MANIFEST, encoding='utf-8').read()
data = json.loads(cur[cur.index('['):cur.rindex(']') + 1])
have_titles = {(e['title'], e['unit']) for e in data}

# 现有 sNN 编号
used = {int(re.search(r's(\d+)\.mp3', f).group(1)) for f in glob.glob(os.path.join(SONG_DIR, 's*.mp3'))}
nxt = max(used) + 1 if used else 1

added = []
for item in raw:
    src = item['file']
    if not os.path.exists(src) or os.path.getsize(src) < 100000:
        print('skip (missing/small):', item['name']); continue
    title, artist, credit = parse(item['name'])
    key = (title, 'vocaloid')
    if key in have_titles:
        print('skip dup:', title); continue
    dest = os.path.join(SONG_DIR, f's{nxt}.mp3')
    shutil.copy(src, dest)
    dur = probe(dest)
    if not dur:
        print('skip broken:', title); os.remove(dest); continue
    data.append({'title': title, 'artist': artist, 'credit': credit, 'unit': 'vocaloid',
                 'game': False, 'duration': round(dur, 2), 'file': f'songs/s{nxt}.mp3',
                 'full': dur > 120, 'cover': 'assets/covers/vocaloid1.jpg'})
    added.append(title)
    nxt += 1

order = {k: i for i, k in enumerate(['leoneed', 'mmj', 'vbs', 'wxs', 'n25', 'vocaloid', 'other', 'zijiang', 'egirls'])}
data.sort(key=lambda e: order.get(e['unit'], 9))
js = 'window.SONGS = ' + json.dumps(data, ensure_ascii=False, indent=1) + ';\n'
open(MANIFEST, 'w', encoding='utf-8').write(js)
print(f'added {len(added)} vocaloid songs; total {len(data)}')
for t in added: print(' +', t)

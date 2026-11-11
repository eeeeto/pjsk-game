#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 songs/ 目录，解析曲名/歌手/组合，转码，生成 songs/manifest.js"""
import os, re, json, subprocess, glob

ROOT = os.path.dirname(os.path.abspath(__file__))
SONG_DIR = os.path.join(ROOT, 'songs')
RAW = json.load(open('/root/.codebuddy/artifact/lz/raw_list.json', encoding='utf-8'))

UNITS = [
    ('leoneed', ['Leo/need', 'Leo-need', 'レオニード', 'Leo_need']),
    ('mmj', ['MORE MORE JUMP！', 'MORE MORE JUMP!', 'MORE MORE JUMP', 'モアモアジャンプ']),
    ('vbs', ['Vivid BAD SQUAD', 'VividBAD SQUAD', 'ビビッドバッドスクワッド']),
    ('wxs', ['ワンダーランズ×ショウタイム', 'ワンダーランズｘショウタイム', 'Wonderlands×Showtime']),
    ('n25', ['25時、ナイトコードで。', '25时、ナイトコードで。', '25時', 'ニーゴ']),
]
UNIT_LABEL = {'leoneed': 'Leo/need', 'mmj': 'MORE MORE JUMP！', 'vbs': 'Vivid BAD SQUAD',
              'wxs': 'ワンダーランズ×ショウタイム', 'n25': '25時、ナイトコードで。', 'other': '其他'}

CHARS = ['星乃一歌', '天馬咲希', '望月穂波', '日野森志歩', '花里みのり', '桐谷遥', '桃井愛莉', '日野森雫',
         '小豆沢こはね', '白石杏', '東雲彰人', '青柳冬弥', '天馬司', '鳳えむ', '草薙寧々', '神代類',
         '宵崎奏', '朝比奈まふゆ', '東雲絵名', '暁山瑞希', '初音ミク', '鏡音リン', '鏡音レン', '巡音ルカ', 'MEIKO', 'KAITO']

# 角色 -> 所属组合（虚拟歌手不归属任何组合）
CHAR_UNIT = {}
for _u, _names in {
    'leoneed': ['星乃一歌', '天馬咲希', '望月穂波', '日野森志歩'],
    'mmj': ['花里みのり', '桐谷遥', '桃井愛莉', '日野森雫'],
    'vbs': ['小豆沢こはね', '白石杏', '東雲彰人', '青柳冬弥'],
    'wxs': ['天馬司', '鳳えむ', '草薙寧々', '神代類'],
    'n25': ['宵崎奏', '朝比奈まふゆ', '東雲絵名', '暁山瑞希'],
}.items():
    for _n in _names:
        CHAR_UNIT[_n] = _u


def detect_unit(chars):
    """按登场角色的所属组合判定；跨组合混编判为其他"""
    cnt = {}
    for c in chars:
        u = CHAR_UNIT.get(c)
        if u:
            cnt[u] = cnt.get(u, 0) + 1
    if not cnt:
        return 'other'
    ranked = sorted(cnt.items(), key=lambda kv: -kv[1])
    top, n = ranked[0]
    if len(ranked) == 1:
        return top
    if n >= 2 and n > sum(v for _, v in ranked[1:]):
        return top
    return 'other'


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_name',
                          '-of', 'json', path], capture_output=True, text=True).stdout
    try:
        j = json.loads(out)
        dur = float(j.get('format', {}).get('duration', 0))
        codec = (j.get('streams') or [{}])[0].get('codec_name', '')
        return dur, codec
    except Exception:
        return 0.0, ''


# 人工校正表：曲名 -> (组合, 演唱角色)。用于文件名无法判断归属的翻唱曲
MANUAL = {
    '強風オールバック': ('leoneed', ['星乃一歌', '天馬咲希', '望月穂波', '日野森志歩']),
    'ロキ': ('leoneed', ['初音ミク']),
    '六兆年と一夜物語': ('leoneed', ['初音ミク']),
    '威風堂々': ('vbs', ['KAITO']),
}


def parse(name):    s = re.sub(r'\.(mp3|flac|wav|m4a)(\.{1,3})?$', '', name, flags=re.I).strip().rstrip('.')
    s = s.replace('世界补充计划', '').strip(' -　')

    # “… 歌：Leo need” 形式
    song_credit = ''
    m = re.search(r'歌\s*[：:]\s*(.+)$', s)
    if m:
        song_credit = m.group(1).strip()
        s = s[:m.start()].strip()

    if ' - ' in s:
        left, right = s.rsplit(' - ', 1)
    else:
        left, right = '', s
    if song_credit:
        left = (left + ' ' + song_credit).strip()

    feat = ''
    m = re.search(r'[\(（]\s*feat\.?\s*(.*?)\s*[\)）]', right, re.I)
    if m:
        feat = m.group(1)
        right = right[:m.start()] + right[m.end():]
    game = bool(re.search(r'game\s*size', right, re.I))
    right = re.sub(r'[\(（]\s*Game\s*size\.?\s*[\)）]', '', right, flags=re.I)
    title = re.sub(r'\s+', ' ', right).strip(' -　')
    title = re.sub(r'[（(]\s*\d+\s*[)）]$', '', title).strip()
    if not title:
        title, left = left, ''

    # 记录 feat 里的歌手名
    feat_names = [p.strip() for p in re.split(r'[&、,，/]', feat) if p.strip()] if feat else []
    # 用于判定的角色（前缀 + feat）
    all_chars = [c for c in CHARS if (c in left) or (c in feat)]
    unit = detect_unit(all_chars)
    if unit == 'other':
        for _k, aliases in UNITS:
            if any(a in left for a in aliases):
                unit = _k
                break

    # 前缀里移除角色名和组合名，剩下的就是编曲/创作者
    rest = left
    for c in CHARS:
        rest = rest.replace(c, ' ')
    for _k, aliases in UNITS:
        for a in aliases:
            rest = rest.replace(a, ' ')
    rest = re.sub(r'[\s　]+', ' ', rest).strip(' -　')

    singers = feat_names if feat_names else [c for c in CHARS if c in left]
    seen, singers2 = set(), []
    for n in singers:
        if n not in seen:
            seen.add(n)
            singers2.append(n)
    singers = singers2

    if unit == 'other':
        artist = '、'.join(singers) if singers else rest
        credit = ''
    else:
        artist = UNIT_LABEL[unit] + ('｜' + '、'.join(singers) if singers else '')
        credit = f'作编曲：{rest}' if rest else ''

    # 人工校正：个别翻唱曲的收录组合与演唱角色
    if title in MANUAL:
        _u, _ss = MANUAL[title]
        unit = _u
        artist = UNIT_LABEL[_u] + ('｜' + '、'.join(_ss) if _ss else '')

    return dict(title=title, artist=artist, credit=credit, unit=unit, game=game)


def main():
    files = sorted(glob.glob(os.path.join(SONG_DIR, 's*.mp3')))
    entries, used = [], set()
    for path in files:
        m = re.search(r's(\d+)\.mp3$', path)
        idx = int(m.group(1)) - 1 if m else -1
        if not (0 <= idx < len(RAW)):
            continue
        meta = parse(RAW[idx]['name'])
        key = (meta['title'], meta['unit'])
        if key in used:
            print(f'skip duplicate: {meta["title"]}')
            os.remove(path)
            continue

        dur, codec = probe(path)
        if not dur:
            print('skip broken', path)
            os.remove(path)
            continue
        if codec != 'mp3':
            tmp = path + '.conv.mp3'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', path,
                            '-codec:a', 'libmp3lame', '-b:a', '192k', '-ar', '44100', tmp])
            if os.path.exists(tmp) and os.path.getsize(tmp) > 10000:
                os.replace(tmp, path)
                dur, codec = probe(path)
                print(f'converted {os.path.basename(path)} -> mp3 ({dur:.1f}s)')

        used.add(key)
        meta['duration'] = round(dur, 2)
        meta['file'] = 'songs/' + os.path.basename(path)
        meta['full'] = dur > 120
        entries.append(meta)

    order = {k: i for i, k in enumerate(['leoneed', 'mmj', 'vbs', 'wxs', 'n25', 'other'])}
    entries.sort(key=lambda e: order.get(e['unit'], 9))

    cnt = {}
    for e in entries:
        k = e['unit']
        cnt[k] = cnt.get(k, 0) + 1
        e['cover'] = 'assets/covers/other1.jpg' if k == 'other' else f"assets/covers/{k}{((cnt[k] - 1) % 5) + 1}.jpg"

    js = 'window.SONGS = ' + json.dumps(entries, ensure_ascii=False, indent=1) + ';\n'
    with open(os.path.join(SONG_DIR, 'manifest.js'), 'w', encoding='utf-8') as f:
        f.write(js)
    print(f'written {len(entries)} songs')
    for e in entries:
        print(f"  [{e['unit']:8}] {e['title']} | {e['artist']} | {e['duration']}s {'FULL' if e['full'] else ''} | {e['credit']}")


if __name__ == '__main__':
    main()

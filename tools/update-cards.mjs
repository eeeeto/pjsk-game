#!/usr/bin/env node
/* 自动跟进新卡：
 *  1. 拉取 sekai-master-db-diff 的 cards.json / gachas.json（GitHub Actions 内网速度快）
 *  2. 对比本地 assets/gacha-index.json 找出新卡 / 新卡池
 *  3. 新卡：下载 特训前/特训后 卡面 + 透明抠像（404 自动跳过），生成 480px 缩略图
 *  4. 更新 gacha-index.json（cards / gachas / 版本号 v）
 *  由 .github/workflows/update-cards.yml 每 6 小时定时执行；发现更新后自动 commit & push
 */
import fs from 'node:fs';
import path from 'node:path';
import https from 'node:https';
import sharp from 'sharp';

const ROOT = path.resolve(new URL('.', import.meta.url).pathname, '..');
const MASTER = 'https://sekai-world.github.io/sekai-master-db-diff/';
const ASSET = 'https://storage.sekai.best/sekai-jp-assets/character/member/';
const CUTOUT = 'https://storage.sekai.best/sekai-jp-assets/character/member_cutout_trm/';
const IDX_PATH = path.join(ROOT, 'assets/gacha-index.json');
const IMG = path.join(ROOT, 'assets/cardimg');
const CONC = 8;
/* 调试用：MASTER_DIR=/path/to/dir 时从本地读 cards.json/gachas.json，不联网 */
const LOCAL_MASTER = process.env.MASTER_DIR || null;

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'pjsk-game-updater' } }, (r) => {
      if (r.statusCode !== 200) { r.resume(); return reject(new Error(url + ' -> HTTP ' + r.statusCode)); }
      const chunks = [];
      r.on('data', (c) => chunks.push(c));
      r.on('end', () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf-8'))); } catch (e) { reject(e); } });
      r.on('error', reject);
    }).on('error', reject);
  });
}

function dl(url, dest, tries = 3) {
  return new Promise((resolve) => {
    (function attempt(n) {
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      const tmp = dest + '.part';
      const file = fs.createWriteStream(tmp);
      let settled = false;
      const finish = (ok) => {
        if (settled) return;
        settled = true;
        try { file.close(); } catch (e) {}
        if (ok === true && fs.existsSync(tmp)) { fs.renameSync(tmp, dest); return resolve(true); }
        if (ok === 'skip') return resolve('skip');
        try { fs.unlinkSync(tmp); } catch (e) {}
        if (n < tries) return attempt(n + 1);
        resolve(false);
      };
      const timer = setTimeout(() => { req.destroy(); finish(false); }, 45000);
      const req = https.get(url, { headers: { 'User-Agent': 'pjsk-game-updater' } }, (r) => {
        if (r.statusCode === 404) { clearTimeout(timer); r.resume(); return finish('skip'); }
        if (r.statusCode !== 200) { clearTimeout(timer); r.resume(); return finish(false); }
        r.pipe(file);
        file.on('finish', () => { clearTimeout(timer); finish(true); });
        file.on('error', () => { clearTimeout(timer); finish(false); });
      });
      req.on('error', () => { clearTimeout(timer); finish(false); });
    })(0);
  });
}

async function mapLimit(items, limit, fn) {
  const out = []; let i = 0, active = 0;
  return new Promise((res) => {
    const pump = () => {
      while (active < limit && i < items.length) {
        const idx = i++;
        active++;
        fn(items[idx]).then((v) => { out[idx] = v; active--; pump(); });
      }
      if (active === 0 && i >= items.length) res(out);
    };
    pump();
  });
}

async function genThumb(src, dest) {
  const orig = fs.statSync(src).size;
  const buf = await sharp(src, { limitInputPixels: false }).resize({ width: 480, withoutEnlargement: true }).webp({ quality: 82 }).toBuffer();
  if (buf.length < orig) {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, buf);
  }
}

async function main() {
  const idx = JSON.parse(fs.readFileSync(IDX_PATH, 'utf-8'));
  console.log('local: cards', Object.keys(idx.cards).length, 'gachas', idx.gachas.length, 'v', idx.v);

  console.log('fetching master cards.json …');
  const cards = LOCAL_MASTER ? JSON.parse(fs.readFileSync(path.join(LOCAL_MASTER, 'cards.json'), 'utf-8')) : await fetchJson(MASTER + 'cards.json');
  console.log('fetching master gachas.json …');
  const gachas = LOCAL_MASTER ? JSON.parse(fs.readFileSync(path.join(LOCAL_MASTER, 'gachas.json'), 'utf-8')) : await fetchJson(MASTER + 'gachas.json');
  console.log('remote: cards', cards.length, 'gachas', gachas.length);

  // ---- 新卡 ----
  const newCards = cards.filter((c) => c.assetbundleName && !idx.cards[c.id]);
  // 已知卡缺文件（上次中断等）→ 补齐
  const needRepair = cards.filter((c) => {
    const e = idx.cards[c.id];
    if (!e || !c.assetbundleName) return false;
    const n = path.join(IMG, 'full', e[0], 'card_normal.webp');
    return !fs.existsSync(n);
  });
  console.log('new cards:', newCards.length, 'need repair:', needRepair.length);

  let okNew = 0;
  for (const c of [...newCards, ...needRepair]) {
    const abn = c.assetbundleName;
    const tasks = [
      [ASSET + abn + '/card_normal.webp', path.join(IMG, 'full', abn, 'card_normal.webp')],
      [ASSET + abn + '/card_after_training.webp', path.join(IMG, 'full', abn, 'card_after_training.webp')],
      [CUTOUT + abn + '/normal.webp', path.join(IMG, 'cutout', abn, 'normal.webp')],
      [CUTOUT + abn + '/after_training.webp', path.join(IMG, 'cutout', abn, 'after_training.webp')],
    ];
    const rs = await mapLimit(tasks, CONC, async ([u, d]) => (fs.existsSync(d) ? true : dl(u, d)));
    const hasFull = fs.existsSync(tasks[0][1]);
    if (hasFull) {
      for (const f of [tasks[0][1], tasks[1][1]]) {
        if (fs.existsSync(f)) await genThumb(f, f.replace('/full/', '/thumb/'));
      }
    }
    if (newCards.includes(c) && hasFull) {
      idx.cards[c.id] = [abn, c.cardRarityType || '', c.characterId ?? 0, c.releaseAt ?? 0, c.prefix || ''];
      okNew++;
      console.log('new card:', c.id, abn, c.cardRarityType, c.prefix);
    } else if (!hasFull) {
      console.log('WARN card', c.id, abn, 'normal.webp missing', JSON.stringify(rs));
    }
  }

  // ---- 新卡池 ----
  const haveG = new Set(idx.gachas.map((g) => g.id));
  let gAdd = 0;
  for (const g of gachas) {
    if (haveG.has(g.id)) continue;
    const rates = (g.gachaCardRarityRates || [])
      .filter((r) => r.lotteryType === 'normal')
      .map((r) => ({ r: r.cardRarityType, rate: r.rate }));
    idx.gachas.push({ id: g.id, name: g.name || '', abn: g.assetbundleName || '', type: g.gachaType || 'normal', s: g.startAt ?? 0, e: g.endAt ?? 0, rates });
    gAdd++;
  }
  if (gAdd) console.log('new gachas:', gAdd);

  /* 只有真正新增卡/卡池（或 repair 成功补齐缺失文件）才写索引，避免每 6 小时空提交 */
  if (okNew || gAdd) {
    const day = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    idx.v = Number(day + (idx.v % 100 === 0 ? '01' : String(Math.min(99, (idx.v % 100) + 1)).padStart(2, '0')));
    fs.writeFileSync(IDX_PATH, JSON.stringify(idx));
    console.log('gacha-index.json updated, v =', idx.v);
  } else {
    console.log('no updates');
  }
}

main().catch((e) => { console.error(e); process.exit(1); });

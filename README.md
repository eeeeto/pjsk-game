# PROJECT SEKAI · FAN STAGE

一个基于网页的同人节奏游戏（非官方作品），单文件实现，适配平板 / 手机横屏，也可以直接在电脑浏览器里玩。

## 玩法

- 六轨下落式，音符到达判定线时点击对应轨道（触屏或键盘 `D F J K` / 方向键区）
- 判定窗口：PERFECT ±110ms / GREAT ±190ms / GOOD ±270ms / BAD ±360ms
- COMBO 只累计 PERFECT 与 GREAT，GOOD / BAD / MISS 都会断连
- 生命值 1000，MISS −80 / BAD −50 / GOOD −20，归零即失败
- 长条需要按住，松手时还有尾判（绿色条）

## 曲库

62 首，分 9 个分类：Leo/need、MORE MORE JUMP!、Vivid BAD SQUAD、Wonderlands×Showtime、
25 时、Nightcord。、ボカロ、其他、枝江娱乐、E-girls。

## 本地运行

直接双击 `index.html` 即可（音频通过相对路径加载，无需服务器）。
如果浏览器拦截本地文件，可用任意静态服务器：

```bash
python3 -m http.server 8000
# 打开 http://localhost:8000
```

## 部署到 GitHub Pages

1. 把本仓库推到 GitHub（建议 public）；
2. Settings → Pages → Source 选择 `Deploy from a branch`，分支 `main`、目录 `/ (root)`；
3. 稍等一分钟，访问 `https://<你的用户名>.github.io/<仓库名>/` 即可在线游玩。

> 仓库约 248MB（主要是音频），首次 `git push` 需要几分钟。单个文件最大 6.3MB，
> 远低于 GitHub 的 100MB 单文件上限，**不需要 Git LFS**，也不需要拆分。

## 目录结构

```
index.html            全部界面与游戏逻辑（单文件）
songs/manifest.js     曲库清单（标题 / 歌手 / 分类 / 时长 / 封面）
songs/*.mp3           62 首音频
assets/covers/        专辑封面
assets/cards/         卡面（背景「卡面模式」用）
assets/keys/          按键图案皮肤
assets/sfx/           按键音效
```

## 版权

非官方同人作品，仅用于交流学习。曲目、角色、卡面等版权归 SEGA / Colorful Palette 及各原作者所有。

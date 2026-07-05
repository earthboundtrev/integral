# GitHub launch checklist

Copy-paste values when creating the public repository.

---

## Repository name

```
integral
```

(or `integral-app` if `integral` is taken)

---

## Description (GitHub About field)

```
Tend every area of your life. One honest day at a time. Local-first desktop app for holistic daily logging, activity tracking, and intelligent guidance.
```

Short variant (if character limit):

```
Local-first life tracking — ratings, journals, guidance, fitness programs. No cloud.
```

---

## Topics (GitHub tags)

```
personal-development
journaling
habit-tracker
wheel-of-life
desktop-app
local-first
open-source
python
tkinter
wellness
burnout-prevention
life-tracking
```

---

## Website

Leave blank until you have a landing page, or point to README.

---

## Social preview image

GitHub → **Settings** → **General** → **Social preview**

Upload: `assets/integral-icon-source.png` (1280×640 crop or a banner you design later)

For now the square icon works as a placeholder on the Releases page via the attached zip.

---

## First release

1. Run `.\build.ps1`
2. Zip `dist\Integral\` → `Integral-v0.1.0-windows.zip`
3. Create release **v0.1.0** with title: `Integral v0.1.0 — first public release`
4. Release notes template:

```markdown
## Integral v0.1.0

**Tend every area of your life. One honest day at a time.**

### What's included
- Daily logging across 18 life areas — holistic development plus food, art, reading, and content
- GitHub-style activity grid + day explorer
- Intelligent guidance (trends, maintenance gaps, burnout signals)
- Fitness Hub: Convict Conditioning, Tibetan Rites, Explosive Calisthenics
- Dark mode, graphs, weekly summary, category editor

### Install (Windows)
1. Download `Integral-v0.1.0-windows.zip`
2. Unzip
3. Double-click `Integral.exe`

Data saves to `%APPDATA%\Integral\data.json`.

### License
MIT
```

---

## README badge URL

After publishing, replace `YOUR_USERNAME/integral` in README with your actual repo path: `earthboundtrev/integral`.

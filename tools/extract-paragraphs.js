#!/usr/bin/env node
/**
 * 从论文 PDF 抽出段落框和英文原文，供手写译文对照。
 * 用法：node tools/extract-paragraphs.js 2106.09685 [页码]
 * 双栏按中间空隙拆开，通栏标题单独成段。只输出正文段落，丢掉图中短标签。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const pdfjs = require('/tmp/pdfjs-extract/node_modules/pdfjs-dist/legacy/build/pdf.js');

function glyphsOf(items) {
  return items.filter((it) => it.str && it.str.trim()).map((it) => {
    const [, , , d, e, f] = it.transform;
    return { x: e, y: f, w: it.width, h: it.height || Math.abs(d) || 10, s: it.str };
  });
}

/** 同一基线的字拼成行，行内大空隙再切开，避免左右栏粘在一起。 */
function lineFragments(glyphs, pageH) {
  const lines = [];
  const sorted = [...glyphs].sort((a, b) => b.y - a.y || a.x - b.x);
  for (const g of sorted) {
    let line = null;
    for (const cand of lines) {
      if (Math.abs(cand.y - g.y) < Math.max(2.2, Math.min(cand.h, g.h) * 0.45)) {
        line = cand;
        break;
      }
    }
    if (line) {
      line.glyphs.push(g);
      line.y = (line.y * line.n + g.y) / (line.n + 1);
      line.h = Math.max(line.h, g.h);
      line.n += 1;
    } else {
      lines.push({ y: g.y, h: g.h, n: 1, glyphs: [g] });
    }
  }
  const frags = [];
  for (const line of lines) {
    line.glyphs.sort((a, b) => a.x - b.x);
    let run = [];
    const flush = () => {
      if (!run.length) return;
      let text = '';
      let prev = null;
      let x0 = Infinity;
      let x1 = 0;
      let y0 = Infinity;
      let y1 = 0;
      for (const g of run) {
        if (prev) {
          const gap = g.x - (prev.x + prev.w);
          if (gap > Math.max(1.5, prev.h * 0.16)) text += ' ';
        }
        text += g.s;
        prev = g;
        x0 = Math.min(x0, g.x);
        x1 = Math.max(x1, g.x + g.w);
        y0 = Math.min(y0, g.y);
        y1 = Math.max(y1, g.y + g.h);
      }
      text = text.replace(/\s+/g, ' ').trim();
      if (text && y0 > 42 && y1 < pageH - 30) {
        frags.push({ text, x: x0, y: y0, w: x1 - x0, h: y1 - y0, size: line.h, top: y1 });
      }
      run = [];
    };
    for (const g of line.glyphs) {
      if (run.length) {
        const prev = run[run.length - 1];
        if (g.x - (prev.x + prev.w) > 8) flush();
      }
      run.push(g);
    }
    flush();
  }
  return frags;
}

/** 在版心中部找一条竖向空白，当作双栏分界。找不到就整页单栏。 */
function findGutter(frags, pageW) {
  const body = frags.filter((f) => f.w < pageW * 0.62);
  if (body.length < 8) return null;
  const bins = new Map();
  for (const f of body) {
    const end = Math.min(pageW, f.x + f.w);
    for (let x = Math.floor(f.x); x < end; x += 2) {
      bins.set(x, (bins.get(x) || 0) + 1);
    }
  }
  const left = pageW * 0.32;
  const right = pageW * 0.68;
  let best = null;
  let runStart = null;
  for (let x = Math.floor(left); x <= right; x += 2) {
    const empty = (bins.get(x) || 0) < 2;
    if (empty && runStart == null) runStart = x;
    if ((!empty || x + 2 > right) && runStart != null) {
      const end = empty ? x + 2 : x;
      const width = end - runStart;
      if (width >= 10 && (!best || width > best.width)) best = { x: (runStart + end) / 2, width };
      runStart = null;
    }
  }
  return best;
}

function joinLines(lines) {
  let text = '';
  for (const line of lines) {
    if (text.endsWith('-') && /^[A-Za-z]/.test(line.text)) text = text.slice(0, -1) + line.text;
    else text += (text ? ' ' : '') + line.text;
  }
  return text.replace(/\s+/g, ' ').trim();
}

function groupColumn(frags) {
  const lines = [...frags].sort((a, b) => b.top - a.top);
  const paras = [];
  let cur = null;
  for (const line of lines) {
    const gap = cur ? cur.y0 - line.top : 0;
    const sizeJump = cur && (line.size > cur.size * 1.35 || cur.size > line.size * 1.45);
    const bigGap = cur && gap > Math.max(line.size * 0.85, 7);
    const heading = /^(ABSTRACT|\d+(\.\d+)*\s+[A-Z][A-Z ]{3,}|[A-Z][A-Z \-]{6,})$/.test(line.text);
    // 同一行右侧的图注、公式不要并进左栏正文
    const farX = cur && line.x > cur.x0 + 36;
    if (!cur || sizeJump || bigGap || heading || farX) {
      cur = {
        lines: [line],
        x0: line.x,
        x1: line.x + line.w,
        y0: line.y,
        y1: line.top,
        size: line.size,
      };
      paras.push(cur);
    } else {
      cur.lines.push(line);
      cur.x0 = Math.min(cur.x0, line.x);
      cur.x1 = Math.max(cur.x1, line.x + line.w);
      cur.y0 = Math.min(cur.y0, line.y);
      cur.y1 = Math.max(cur.y1, line.top);
    }
  }
  return paras.map((p) => ({
    text: joinLines(p.lines),
    x: +p.x0.toFixed(1),
    y: +p.y0.toFixed(1),
    w: +(p.x1 - p.x0).toFixed(1),
    h: +(p.y1 - p.y0).toFixed(1),
    top: p.y1,
  }));
}

function isBody(p) {
  if (p.text.length < 40 || p.w < 90 || p.h < 9) return false;
  if (/^arXiv:/i.test(p.text)) return false;
  if (/^figure\s+\d+/i.test(p.text) && p.text.length < 80) return false;
  return true;
}

function paragraphsOf(frags, pageW) {
  const gutter = findGutter(frags, pageW);
  const full = [];
  const left = [];
  const right = [];
  for (const f of frags) {
    if (!gutter || f.w > pageW * 0.62 || (f.x < gutter.x && f.x + f.w > gutter.x + 8)) full.push(f);
    else if (f.x + f.w / 2 < gutter.x) left.push(f);
    else right.push(f);
  }
  const keep = (list) => list.filter((f) => f.w >= 70 && f.text.length >= 20);
  const blocks = [
    ...groupColumn(keep(full)),
    ...groupColumn(keep(left)),
    ...groupColumn(keep(right)),
  ].filter(isBody);
  blocks.sort((a, b) => b.top - a.top || a.x - b.x);
  return blocks.map(({ top, ...rest }) => rest);
}

function carryTranslations(previous, pages) {
  const old = [];
  if (previous && previous.pages) {
    for (const paras of Object.values(previous.pages)) {
      for (const para of paras) {
        if (para.zh) old.push(para);
      }
    }
  }
  for (const paras of Object.values(pages)) {
    for (const para of paras) {
      const hit = old.find((item) => item.text === para.text);
      para.zh = hit ? hit.zh : '';
    }
  }
}

async function extractOne(aid) {
  const pdfPath = path.join(__dirname, '..', '论文', `${aid}.pdf`);
  const data = new Uint8Array(fs.readFileSync(pdfPath));
  const doc = await pdfjs.getDocument({ data, disableWorker: true }).promise;
  const pages = {};
  for (let n = 1; n <= doc.numPages; n += 1) {
    const page = await doc.getPage(n);
    const vp = page.getViewport({ scale: 1 });
    const tc = await page.getTextContent();
    pages[String(n)] = paragraphsOf(lineFragments(glyphsOf(tc.items), vp.height), vp.width);
  }
  return { id: aid, pages, numPages: doc.numPages };
}

async function main() {
  console.warn = () => {};
  const aid = process.argv[2];
  const onlyPage = process.argv[3] ? Number(process.argv[3]) : 0;
  if (!aid) {
    console.error('用法: node tools/extract-paragraphs.js <arxiv-id> [page] | all');
    process.exit(1);
  }
  if (aid === 'all') {
    const paperDir = path.join(__dirname, '..', '论文');
    const outDir = path.join(paperDir, '译文');
    fs.mkdirSync(outDir, { recursive: true });
    const ids = fs.readdirSync(paperDir).filter((name) => name.endsWith('.pdf')).map((name) => name.slice(0, -4));
    for (const id of ids) {
      const extracted = await extractOne(id);
      const outPath = path.join(outDir, `${id}.json`);
      let previous = null;
      if (fs.existsSync(outPath)) previous = JSON.parse(fs.readFileSync(outPath, 'utf8'));
      carryTranslations(previous, extracted.pages);
      const payload = {
        id,
        title: (previous && previous.title) || id,
        note: '手写译文。空的 zh 表示这段还没译，阅读器里不会出现高亮。',
        pages: extracted.pages,
      };
      fs.writeFileSync(outPath, JSON.stringify(payload, null, 2));
      const total = Object.values(extracted.pages).reduce((sum, list) => sum + list.length, 0);
      const done = Object.values(extracted.pages).reduce((sum, list) => sum + list.filter((item) => item.zh).length, 0);
      console.log(`${id}\tpages=${extracted.numPages}\tparas=${total}\tdone=${done}`);
    }
    return;
  }
  const pdfPath = path.join(__dirname, '..', '论文', `${aid}.pdf`);
  const data = new Uint8Array(fs.readFileSync(pdfPath));
  const doc = await pdfjs.getDocument({ data, disableWorker: true }).promise;
  const pages = {};
  const from = onlyPage || 1;
  const to = onlyPage || doc.numPages;
  for (let n = from; n <= to; n += 1) {
    const page = await doc.getPage(n);
    const vp = page.getViewport({ scale: 1 });
    const tc = await page.getTextContent();
    pages[String(n)] = paragraphsOf(lineFragments(glyphsOf(tc.items), vp.height), vp.width);
  }
  process.stdout.write(JSON.stringify({ id: aid, pages }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

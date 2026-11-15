#!/usr/bin/env node
/**
 * Verifica el contraste WCAG 2.1 de los pares texto/fondo del design system.
 *
 * Lee los custom properties reales de `src/styles/tokens.css`, resuelve `var()`
 * y compone colores con alfa sobre su fondo. Sale con código 1 si algún par no
 * alcanza el mínimo (AA: 4.5 texto normal, 3 texto grande y componentes UI).
 *
 * Uso: node scripts/check-contrast.mjs
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const TOKENS_PATH = resolve(here, '../src/styles/tokens.css');

/** [primer plano, fondo, mínimo, base opaca sobre la que se compone el fondo] */
const PAIRS = [
  ['--color-text', '--color-canvas', 4.5],
  ['--color-text', '--color-panel', 4.5],
  ['--color-text', '--color-card', 4.5],
  ['--color-text', '--color-card-raised', 4.5],
  ['--color-text-secondary', '--color-canvas', 4.5],
  ['--color-text-secondary', '--color-panel', 4.5],
  ['--color-text-secondary', '--color-card', 4.5],
  ['--color-text-secondary', '--color-card-raised', 4.5],
  ['--color-text-tertiary', '--color-canvas', 4.5],
  ['--color-text-tertiary', '--color-panel', 4.5],
  ['--color-text-tertiary', '--color-card', 4.5],
  ['--color-text', '--color-field', 4.5],
  ['--color-text-tertiary', '--color-field', 4.5],
  ['--color-accent-text', '--color-canvas', 4.5],
  ['--color-accent-text', '--color-panel', 4.5],
  ['--color-accent-text', '--color-card', 4.5],
  ['--color-on-accent', '--color-accent', 4.5],
  ['--color-on-accent', '--color-accent-hover', 4.5],
  ['--color-on-danger', '--color-danger', 4.5],
  ['--color-positive', '--color-card', 4.5],
  ['--color-warning', '--color-card', 4.5],
  ['--color-danger', '--color-card', 4.5],
  ['--color-info', '--color-card', 4.5],
  ['--color-positive', '--color-positive-soft', 4.5, '--color-card'],
  ['--color-warning', '--color-warning-soft', 4.5, '--color-card'],
  ['--color-danger', '--color-danger-soft', 4.5, '--color-card'],
  ['--color-info', '--color-info-soft', 4.5, '--color-card'],
  ['--color-accent-text', '--color-accent-soft', 4.5, '--color-card'],
  ['--color-text-secondary', '--color-neutral-soft', 4.5, '--color-card'],
  ['--color-field-border', '--color-card', 3],
  ['--color-field-border', '--color-panel', 3],
  ['--color-focus', '--color-canvas', 3],
  ['--color-focus', '--color-card', 3],
];

function parseTokens(css) {
  const tokens = new Map();
  const rootBlock = css.match(/:root\s*\{([\s\S]*?)\n\}/);
  if (!rootBlock) throw new Error('No se encontró el bloque :root en tokens.css');
  for (const match of rootBlock[1].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    tokens.set(match[1], match[2].trim());
  }
  return tokens;
}

function resolveValue(tokens, name, depth = 0) {
  if (depth > 10) throw new Error(`Referencia circular en ${name}`);
  const raw = tokens.get(name);
  if (raw === undefined) throw new Error(`Token inexistente: ${name}`);
  const ref = raw.match(/^var\((--[\w-]+)\)$/);
  return ref ? resolveValue(tokens, ref[1], depth + 1) : raw;
}

function parseColor(value) {
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 };
  }
  const rgba = value.match(/^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)(?:[\s,/]+([\d.]+))?\s*\)$/i);
  if (rgba) {
    return { r: +rgba[1], g: +rgba[2], b: +rgba[3], a: rgba[4] === undefined ? 1 : +rgba[4] };
  }
  throw new Error(`Formato de color no soportado: ${value}`);
}

function composite(top, base) {
  const a = top.a;
  return {
    r: top.r * a + base.r * (1 - a),
    g: top.g * a + base.g * (1 - a),
    b: top.b * a + base.b * (1 - a),
    a: 1,
  };
}

function luminance({ r, g, b }) {
  const channel = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(fg, bg) {
  const l1 = luminance(fg);
  const l2 = luminance(bg);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

const tokens = parseTokens(readFileSync(TOKENS_PATH, 'utf8'));
let failures = 0;

for (const [fgName, bgName, min, baseName] of PAIRS) {
  let bg = parseColor(resolveValue(tokens, bgName));
  if (bg.a < 1) {
    if (!baseName) throw new Error(`${bgName} tiene alfa; declara la base opaca del par`);
    bg = composite(bg, parseColor(resolveValue(tokens, baseName)));
  }
  let fg = parseColor(resolveValue(tokens, fgName));
  if (fg.a < 1) fg = composite(fg, bg);
  const ratio = contrast(fg, bg);
  const ok = ratio >= min;
  if (!ok) failures++;
  const where = baseName ? `${bgName} sobre ${baseName}` : bgName;
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${ratio.toFixed(2).padStart(5)} ≥ ${min}  ${fgName} / ${where}`);
}

if (failures > 0) {
  console.error(`\n${failures} par(es) por debajo del mínimo WCAG.`);
  process.exit(1);
}
console.log(`\n${PAIRS.length} pares cumplen WCAG 2.1 AA.`);

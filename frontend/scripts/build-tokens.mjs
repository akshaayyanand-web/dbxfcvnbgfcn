// Generates src/styles/tokens.css from src/design-system/tokens.json (the design system's single source of truth).
import { readFileSync, writeFileSync } from "node:fs";
const t = JSON.parse(readFileSync(new URL("../src/design-system/tokens.json", import.meta.url)));
const themes = t.color.themes.map((x) => x.id);
const first = themes[0];
const val = (v, th) => (typeof v === "string" ? v : v[th] ?? v[first]);
const ref = (v) => (/^\{(.+)\}$/.test(v) ? `var(--${v.slice(1, -1)})` : v);
const block = (th) => [...t.color.tokens, ...(t.shadow?.tokens ?? [])].map((tok) => `  --${tok.name}: ${ref(val(tok.value, th))};`).join("\n");
const lengths = [...t.spacing.tokens, ...t.radius.tokens].map((tok) => `  --${tok.name}: ${tok.value};`).join("\n");
const fams = Object.entries(t.type.families).map(([k, v]) => `  --font-${k}: ${v};`).join("\n");
const styles = t.type.groups.flatMap((g) => g.styles.map((s) => {
  const fam = s.family ?? g.family;
  return `.${s.name} { font-family: var(--font-${fam}); font-size: ${s.fontSize}; line-height: ${s.lineHeight}; font-weight: ${s.fontWeight};${s.letterSpacing ? ` letter-spacing: ${s.letterSpacing};` : ""}${s.name === "label" ? " text-transform: uppercase;" : ""} }`;
})).join("\n");
const dark = themes[1];
const css = `/* ${t.name} — generated from tokens.json by scripts/build-tokens.mjs. Do not edit. */
:root {
${block(first)}
${lengths}
${fams}
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
${block(dark)}
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
${block(dark)}
  color-scheme: dark;
}
${styles}
`;
writeFileSync(new URL("../src/styles/tokens.css", import.meta.url), css);
console.log("tokens.css written:", t.color.tokens.length, "colors,", themes.length, "themes");

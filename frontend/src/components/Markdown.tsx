// Minimal Markdown renderer for the project documents: headings, paragraphs, lists, fenced code, tables and inline
// code/bold. Builds React elements (no HTML injection), which is enough for reading the docs in the app.
import type { ReactNode } from "react";

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
  let last = 0, m: RegExpExecArray | null, k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("`")) out.push(<code key={k++}>{t.slice(1, -1)}</code>);
    else if (t.startsWith("**")) out.push(<strong key={k++}>{t.slice(2, -2)}</strong>);
    else { const [, label, href] = /\[([^\]]+)\]\(([^)]+)\)/.exec(t)!; out.push(/^https?:/.test(href) ? <a key={k++} href={href} target="_blank" rel="noreferrer">{label}</a> : <span key={k++}>{label}</span>); }
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function Markdown({ source }: { source: string }) {
  const lines = source.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0, k = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) body.push(lines[i++]);
      i++;
      blocks.push(<pre key={k++} className="code">{body.join("\n")}</pre>);
    } else if (/^#{1,6} /.test(line)) {
      const level = line.match(/^#+/)![0].length;
      const text = inline(line.replace(/^#+ /, ""));
      blocks.push(level === 1 ? <h1 key={k++}>{text}</h1> : level === 2 ? <h2 key={k++}>{text}</h2> : <h3 key={k++}>{text}</h3>);
      i++;
    } else if (/^\s*([-*]|\d+\.) /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.) /.test(lines[i])) {
        let item = lines[i++].replace(/^\s*([-*]|\d+\.) /, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.) /.test(lines[i])) item += ` ${lines[i++].trim()}`;
        items.push(item);
      }
      blocks.push(<ul key={k++}>{items.map((t, j) => <li key={j}>{inline(t)}</li>)}</ul>);
    } else if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        if (!/^\|[\s:|-]+\|$/.test(lines[i].trim())) rows.push(lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
        i++;
      }
      blocks.push(<table key={k++}><thead><tr>{rows[0]?.map((c, j) => <th key={j}>{inline(c)}</th>)}</tr></thead><tbody>{rows.slice(1).map((r, j) => <tr key={j}>{r.map((c, x) => <td key={x}>{inline(c)}</td>)}</tr>)}</tbody></table>);
    } else if (line.trim() === "") {
      i++;
    } else {
      const para: string[] = [];
      while (i < lines.length && lines[i].trim() !== "" && !/^(#{1,6} |```|\||\s*([-*]|\d+\.) )/.test(lines[i])) para.push(lines[i++]);
      blocks.push(<p key={k++}>{inline(para.join(" "))}</p>);
    }
  }
  return <div className="prose">{blocks}</div>;
}

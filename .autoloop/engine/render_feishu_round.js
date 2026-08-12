const fs = require("fs");

const [inputPath, journalPath, outputPath, metaPath] = process.argv.slice(2);
if (!journalPath || !outputPath || !metaPath) {
  throw new Error("usage: render_feishu_round.js <input> <journal> <output> <meta-json>");
}

const input = fs.existsSync(inputPath) ? fs.readFileSync(inputPath, "utf8") : "";
const journal = fs.readFileSync(journalPath, "utf8");
const meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
const schema = meta.report_schema || "AutoLoopReportSchema:v1";

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function section(markdown, title) {
  const lines = markdown.split(/\r?\n/);
  const start = lines.findIndex((line) => line.trim() === `## ${title}`);
  if (start < 0) return "";
  const body = [];
  for (let index = start + 1; index < lines.length; index += 1) {
    if (/^##\s+/.test(lines[index])) break;
    body.push(lines[index]);
  }
  return body.join("\n").trim();
}

function plain(markdown) {
  return markdown
    .replace(/^Commit:.*$/gim, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^\s*[-*]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function clip(value, limit) {
  const normalized = plain(value);
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit - 1)}…`;
}

function candidates(markdown) {
  const lines = markdown.split(/\r?\n/);
  const result = [];
  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index].match(/^##\s+候选\s*\d+[：:]\s*(.+)$/);
    if (!match) continue;
    let url = "";
    for (let cursor = index + 1; cursor < lines.length && !/^##\s+/.test(lines[cursor]); cursor += 1) {
      const urlMatch = lines[cursor].match(/URL[：:]\s*(https?:\/\/\S+)/);
      if (urlMatch) {
        url = urlMatch[1];
        break;
      }
    }
    result.push({ title: match[1].replaceAll("`", "").trim(), url });
  }
  return result;
}

function sourceLinks(items) {
  if (!items.length) return "本轮未形成有效外部输入卡。";
  return items
    .map((item) =>
      item.url
        ? `<a href="${escapeXml(item.url)}">${escapeXml(item.title)}</a>`
        : escapeXml(item.title),
    )
    .join("；");
}

const sources = candidates(input);
const digestion = section(input, "消化与选择");
const currentState = section(journal, "现状分析");
const idea = section(journal, "今天的想法");
const rationale = section(journal, "为什么这么做");
const changes = section(journal, "做了哪些事");
const result = section(journal, "最终效果");
const requiredSections = {
  "输入卡/消化与选择": digestion,
  "现状分析": currentState,
  "今天的想法": idea,
  "为什么这么做": rationale,
  "做了哪些事": changes,
  "最终效果": result,
};
const missingSections = Object.entries(requiredSections)
  .filter(([, value]) => !value.trim())
  .map(([name]) => name);
if (sources.length < 2) {
  throw new Error(`input card must contain at least 2 public candidates, got ${sources.length}`);
}
if (missingSections.length) {
  throw new Error(`missing required report sections: ${missingSections.join(", ")}`);
}

const xml = [
  "<hr/>",
  `<h2>第 ${escapeXml(meta.round)} 轮｜${escapeXml(meta.date)}｜${escapeXml(meta.subject)}</h2>`,
  "<table>",
  "<colgroup><col width=\"130\"/><col width=\"600\"/></colgroup>",
  "<thead><tr><th>项目</th><th>本轮记录</th></tr></thead>",
  "<tbody>",
  `<tr><td>外部输入</td><td>${sourceLinks(sources)}<br/><b>消化：</b>${escapeXml(clip(digestion, 240))}</td></tr>`,
  `<tr><td>现状与判断</td><td>${escapeXml(clip(currentState, 280))}</td></tr>`,
  `<tr><td>本轮方案</td><td>${escapeXml(clip(idea, 200))}<br/><b>原因：</b>${escapeXml(clip(rationale, 220))}</td></tr>`,
  `<tr><td>改动</td><td>${escapeXml(clip(changes, 300))}<br/><b>作品 commit：</b><a href="${escapeXml(meta.commit_url)}"><code>${escapeXml(meta.commit)}</code></a></td></tr>`,
  `<tr><td>验证与效果</td><td>${escapeXml(clip(result, 320))}</td></tr>`,
  `<tr><td>原始证据</td><td><a href="${escapeXml(meta.input_url)}">输入卡</a> · <a href="${escapeXml(meta.journal_url)}">Agent 手记</a> · <a href="${escapeXml(meta.run_url)}">运行记录</a></td></tr>`,
  "</tbody>",
  "</table>",
  `<p><code>${escapeXml(schema)}</code> · <code>${escapeXml(meta.marker)}</code></p>`,
].join("\n");

fs.writeFileSync(outputPath, `${xml}\n`);

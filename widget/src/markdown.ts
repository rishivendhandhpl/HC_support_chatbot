// Minimal, dependency-free markdown -> safe HTML renderer.
// Supports: escaping, **bold**, *italic*, links, headings, unordered/ordered
// lists, line breaks. Everything is HTML-escaped first so model output cannot
// inject markup into the Shopify page.

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inline(text: string): string {
  let out = escapeHtml(text);
  // Links: [label](http...)
  out = out.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  );
  // Bold then italic.
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  return out;
}

// Which list a line opens/continues, if any.
function listKind(line: string): "ul" | "ol" | null {
  if (/^\s*[-*]\s+/.test(line)) return "ul";
  if (/^\s*\d+\.\s+/.test(line)) return "ol";
  return null;
}

export function renderMarkdown(md: string): string {
  const lines = md.split("\n");
  const html: string[] = [];
  let listType: "ul" | "ol" | null = null;

  const closeList = (): void => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();
    // Headings (# .. ######): render as a styled subheading, never as literal
    // "###" text. Requires whitespace after the hashes so "#tag" stays prose.
    const headingMatch = /^\s*#{1,6}\s+(.+?)(?:\s+#+)?\s*$/.exec(line);
    const ulMatch = /^\s*[-*]\s+(.*)$/.exec(line);
    const olMatch = /^\s*\d+\.\s+(.*)$/.exec(line);

    if (headingMatch) {
      closeList();
      html.push(`<p class="hc-md-heading">${inline(headingMatch[1])}</p>`);
    } else if (ulMatch) {
      if (listType !== "ul") {
        closeList();
        html.push("<ul>");
        listType = "ul";
      }
      html.push(`<li>${inline(ulMatch[1])}</li>`);
    } else if (olMatch) {
      if (listType !== "ol") {
        closeList();
        html.push("<ol>");
        listType = "ol";
      }
      html.push(`<li>${inline(olMatch[1])}</li>`);
    } else if (line.trim() === "") {
      // Don't reset numbering when a list is merely spaced out: keep the list
      // open across blank line(s) if the next content continues the same list.
      if (listType) {
        let j = i + 1;
        while (j < lines.length && lines[j].trim() === "") j++;
        const next = j < lines.length ? listKind(lines[j]) : null;
        if (next !== listType) closeList();
      }
    } else {
      closeList();
      html.push(`<p>${inline(line)}</p>`);
    }
  }
  closeList();
  return html.join("");
}

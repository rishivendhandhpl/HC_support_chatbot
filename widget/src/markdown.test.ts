import { describe, expect, it } from "vitest";

import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
  it("renders headings as styled subheadings, not literal hashtags", () => {
    const html = renderMarkdown("### Installation Process:");
    expect(html).toBe('<p class="hc-md-heading">Installation Process:</p>');
    expect(html).not.toContain("#");
  });

  it("handles all heading levels and trailing hashes", () => {
    expect(renderMarkdown("# Title")).toContain('class="hc-md-heading">Title<');
    expect(renderMarkdown("###### Deep")).toContain(">Deep<");
    expect(renderMarkdown("## Heading ##")).toContain(">Heading<");
  });

  it("keeps '#tag' (no space) as prose, not a heading", () => {
    expect(renderMarkdown("#tag stays text")).toBe("<p>#tag stays text</p>");
  });

  it("numbers ordered-list items sequentially when separated by blank lines", () => {
    // The model often emits '1.' for every step with blank lines between them.
    const md = "1. Prepare\n\n1. Section\n\n1. Position";
    const html = renderMarkdown(md);
    // One single list -> the browser renders 1, 2, 3 (no reset to 1,1,1).
    expect(html).toBe("<ol><li>Prepare</li><li>Section</li><li>Position</li></ol>");
    expect((html.match(/<ol>/g) ?? []).length).toBe(1);
  });

  it("closes the list when a heading or paragraph follows", () => {
    const html = renderMarkdown("1. Step one\n\n### Tips\n\nPlain text");
    expect(html).toBe(
      "<ol><li>Step one</li></ol>" +
        '<p class="hc-md-heading">Tips</p>' +
        "<p>Plain text</p>",
    );
  });

  it("does not merge a ul into an ol across a blank line", () => {
    const html = renderMarkdown("1. Num\n\n- Bullet");
    expect(html).toBe("<ol><li>Num</li></ol><ul><li>Bullet</li></ul>");
  });

  it("still renders bold, italic, and links and escapes HTML", () => {
    expect(renderMarkdown("**bold**")).toBe("<p><strong>bold</strong></p>");
    expect(renderMarkdown("[H&C](https://x.io)")).toBe(
      '<p><a href="https://x.io" target="_blank" rel="noopener noreferrer">H&amp;C</a></p>',
    );
    expect(renderMarkdown("<script>")).toBe("<p>&lt;script&gt;</p>");
  });
});

#!/usr/bin/env python3
"""
md_to_body.py — render a docs/*.md into a docs/*.body.html for build_report.py.

The first two HTML pages in docs/ were hand-authored against docs/base.css. A
1200-line reference is too long to port by hand without losing content, so this
maps Markdown onto the same class vocabulary instead of inventing a third look:

    # H1 + following blockquote   -> header.top (slug, lede)
    ## H2                          -> <section> with a numbered .s-head
    tables                         -> wrapped in .tw so wide ones scroll alone
    > blockquote                   -> .note, severity read from a leading glyph
    ```mermaid                     -> <pre class="mermaid"> (artifacts render it)
    ``` other                      -> .term with the language in its title bar

Heading ids use GitHub's slug rules so the in-document §-links keep resolving.

Requires `markdown` (pip install markdown). Not part of either pinned venv —
this is a docs tool, not a pipeline stage.

    python md_to_body.py docs/07-agent-pc-design.md docs/agent-pc.body.html \
        --title "..." --slug "07 · AGENT PC" --nav
"""

from __future__ import annotations

import argparse
import html
import re
import unicodedata
from pathlib import Path

import markdown

# A fenced block is pulled out before Markdown ever sees it, so its contents
# survive verbatim. The longest fence wins, which is what lets a ````markdown
# block quote a ``` block inside itself.
FENCE = re.compile(r"^(`{3,})([^\n`]*)\n(.*?)\n\1[ \t]*$", re.S | re.M)


def slugify(text: str) -> str:
    """GitHub's heading-anchor rules: strip markup, drop punctuation, space->dash.

    Non-ASCII is kept (Hangul anchors are legal and this document is Korean),
    so normalise to NFC first or the same visible heading can produce two ids.
    """
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)                 # inline code
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)      # links
    text = re.sub(r"[*_~]", "", text)                         # emphasis
    text = text.lower().strip()
    # \w is Unicode-aware, so Hangul survives while em dashes, '·' and emoji do
    # not — which is what GitHub does, and the §-links were written to match.
    text = re.sub(r"[^\w\s-]", "", text)
    # One hyphen per whitespace character, not per run: dropping the em dash in
    # "스키마 — 환각" leaves two spaces, and GitHub's anchor keeps both as '--'.
    return re.sub(r"\s", "-", text)


def render_fence(lang: str, code: str) -> str:
    lang = lang.strip().split()[0] if lang.strip() else ""
    if lang == "mermaid":
        # Artifacts render this natively — leave the source alone.
        return f'<pre class="mermaid">{html.escape(code)}</pre>'
    label = lang or "text"
    return (
        '<div class="term">'
        f'<div class="term-bar"><span class="dot"></span>{html.escape(label)}</div>'
        f"<pre>{html.escape(code)}</pre>"
        "</div>"
    )


def note_class(inner_html: str) -> str:
    """Severity comes from the glyph the author already used in the prose."""
    head = re.sub(r"<[^>]+>", "", inner_html)[:220]
    if "⚠" in head or "금지" in head or "주의" in head:
        return "note warn"
    if "❌" in head:
        return "note fail"
    if "✅" in head:
        return "note pass"
    return "note"


def stash_fences(md_text: str, stash: list[str]) -> str:
    """Replace every fenced block with a placeholder.

    This has to happen across the whole document *before* it is split into
    sections: a fenced block can legitimately contain a line starting with
    '## ' (this document quotes a CLAUDE.md that does), and splitting first
    turns those into phantom sections.
    """
    def hold(m: re.Match) -> str:
        stash.append(render_fence(m.group(2), m.group(3)))
        return f"\n\x00FENCE{len(stash) - 1}\x00\n"

    return FENCE.sub(hold, md_text)


def convert(md_text: str, stash: list[str]) -> str:
    """Markdown -> HTML fragment, reinstating the stashed fences at the end."""
    out = markdown.markdown(
        md_text,
        extensions=["tables", "sane_lists", "attr_list", "md_in_html"],
        output_format="html5",
    )

    # A fence that sat inside a blockquote comes back wrapped in <p>; unwrap it
    # so the .term div is not nested in a paragraph (invalid, and it collapses).
    def drop(m: re.Match) -> str:
        return stash[int(m.group(1))]

    out = re.sub(r"<p>\s*\x00FENCE(\d+)\x00\s*</p>", drop, out)
    out = re.sub(r"\x00FENCE(\d+)\x00", drop, out)

    out = re.sub(r"<table>", '<div class="tw"><table>', out)
    out = re.sub(r"</table>", "</table></div>", out)

    def as_note(m: re.Match) -> str:
        inner = m.group(1)
        return f'<div class="{note_class(inner)}">{inner}</div>'

    out = re.sub(r"<blockquote>\s*(.*?)\s*</blockquote>", as_note, out, flags=re.S)

    # h3/h4 get ids too — the §-links in this document point at both levels.
    def head_id(m: re.Match) -> str:
        lvl, text = m.group(1), m.group(2)
        plain = re.sub(r"<[^>]+>", "", text)
        return f'<h{lvl} id="{slugify(plain)}">{text}</h{lvl}>'

    return re.sub(r"<h([34])>(.*?)</h\1>", head_id, out, flags=re.S)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--slug", default="", help="uppercase kicker in the header")
    ap.add_argument("--nav", action="store_true", help="emit a section table of contents")
    args = ap.parse_args()

    stash: list[str] = []
    raw = stash_fences(Path(args.src).read_text(encoding="utf-8"), stash)

    m = re.match(r"^#\s+(.+?)\n(.*?)(?=^##\s)", raw, re.S | re.M)
    if not m:
        raise SystemExit("ERROR: expected '# Title' followed by '## ' sections")
    title, preamble = m.group(1).strip(), m.group(2)
    body_md = raw[m.end():]

    # The lede is the intro blockquote, one line per '>' — rendered as a list of
    # framing statements rather than a paragraph, because that is what it is.
    lede_lines = [ln.lstrip("> ").strip()
                  for ln in preamble.splitlines() if ln.startswith(">")]
    lede = "<br>".join(
        re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(x)) for x in lede_lines if x)

    parts = re.split(r"^##\s+(.+?)$", body_md, flags=re.M)[1:]
    sections = list(zip(parts[0::2], parts[1::2]))

    chunks: list[str] = []
    toc: list[str] = []
    for heading, content in sections:
        heading = heading.strip()
        sid = slugify(heading)
        num = heading.split(".")[0].strip() if re.match(r"^\d+\.", heading) else ""
        shown = heading[len(num) + 1:].strip() if num else heading
        toc.append(f'<li><a href="#{sid}"><span class="n">{html.escape(num or "—")}'
                   f"</span>{html.escape(shown)}</a></li>")
        chunks.append(
            f'<section id="{sid}"><div class="wrap">'
            f'<div class="s-head"><span class="n">{html.escape(num)}</span>'
            f"<h2>{html.escape(shown)}</h2></div>"
            f'<div class="col-wide">{convert(content, stash)}</div>'
            "</div></section>"
        )

    nav = ""
    if args.nav:
        nav = ('<nav class="toc"><ol>' + "".join(toc) + "</ol></nav>")

    page = f"""<title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
{{{{CSS:base}}}}

  /* This page is reference material, not an essay: tables and diagrams carry
     most of the load, so it runs wider than the 68ch measure the report uses.
     Prose inside it is still clamped, otherwise long lines get unreadable. */
  .col-wide {{ max-width: 100%; }}
  .col-wide > p, .col-wide > ul, .col-wide > ol {{ max-width: var(--measure); }}
  .col-wide h3 {{ padding-top: .2em; border-top: 1px solid var(--rule-soft); }}
  .col-wide h3:first-child {{ border-top: 0; padding-top: 0; margin-top: 0; }}
  pre.mermaid {{ background: var(--card); border: 1px solid var(--rule);
                border-radius: 6px; padding: 18px; margin: 1.8em 0;
                overflow-x: auto; text-align: center; }}
  .s-head .n {{ min-width: 1.6em; }}
  nav.toc a {{ text-decoration: none; color: var(--ink-soft); }}
  nav.toc a:hover {{ color: var(--accent-ink); text-decoration: underline; }}
  .tw table {{ font-size: .82rem; }}
  .term pre {{ white-space: pre; }}
</style>

<header class="top"><div class="wrap"><div class="top-in">
  <div class="slug"><b>{html.escape(args.slug)}</b></div>
  <h1>{html.escape(title)}</h1>
  <p class="lede">{lede}</p>
  {nav}
</div></div></header>

{"".join(chunks)}
"""
    Path(args.out).write_text(page, encoding="utf-8")
    print(f"{args.out}  ·  {len(sections)} sections  ·  {len(page)//1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

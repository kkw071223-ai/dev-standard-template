#!/usr/bin/env python3
"""Pull role / inputs / outputs / CLI out of every NVIDIA skill doc."""
import json, re, sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def section(text, *names):
    """Return the body of the first '## <name>' section found."""
    for n in names:
        m = re.search(rf"^## {re.escape(n)}\s*$(.*?)(?=^## |\Z)", text,
                      re.M | re.S)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return ""


def frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    fm, key = {}, None
    for line in m.group(1).splitlines():
        km = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if km:
            key = km.group(1)
            fm[key] = km.group(2).strip().strip('"\'')
        elif key and line.strip():
            fm[key] = (fm.get(key, "") + " " + line.strip()).strip()
    return fm


def first_para(text):
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.S)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if p and not p.startswith(("#", "|", "```", ">", "-", "*")):
            return re.sub(r"\s+", " ", p)
    return ""


def cli_first(text):
    m = re.search(r"^## (?:CLI Pattern|Command Patterns)\s*$(.*?)(?=^## |\Z)",
                  text, re.M | re.S)
    if not m:
        return ""
    b = re.search(r"```(?:bash|shell|powershell)?\s*\n(.*?)```", m.group(1), re.S)
    return b.group(1).strip() if b else ""


def io_table(body):
    """Parse a markdown 2-col table into [(field, meaning)]."""
    rows = []
    for line in body.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: "):
            continue
        if cells[0].lower() in ("input", "field", "name"):
            continue
        rows.append((re.sub(r"`", "", cells[0]), cells[1]))
    return rows


def scan(skill_dir, kind):
    md = skill_dir / "SKILL.md"
    if not md.exists():
        md = skill_dir / "README.md"
    if not md.exists():
        return None
    text = md.read_text(encoding="utf-8", errors="replace")
    fm = frontmatter(text)
    rec = {
        "name": fm.get("name") or skill_dir.name,
        "kind": kind,
        "dir": skill_dir.name,
        "description": re.sub(r"\s+", " ", fm.get("description", "")),
        "when": re.sub(r"\s+", " ", section(text, "When to Use", "When to Use This Skill", "Purpose"))[:600],
        "summary": first_para(text)[:400],
        "cli": cli_first(text),
        "inputs": io_table(section(text, "Inputs")),
        "outputs": io_table(section(text, "Output Format", "Outputs")),
        "policy": re.sub(r"\s+", " ", section(text, "Pass/Fail Policy"))[:400],
        "compat": re.sub(r"\s+", " ", fm.get("compatibility", ""))[:300],
        "has_run": (skill_dir / "scripts" / "run.py").exists(),
        "n_refs": len(list((skill_dir / "references").glob("*/README.md")))
                  if (skill_dir / "references").is_dir() else 0,
    }
    return rec


out = []
base = ROOT / "nvidia-skills" / "skills"
for name in ("omniverse-cad-to-simready", "omniverse-usd-performance-tuning",
             "omniverse-realtime-viewer", "physical-ai-neural-reconstruction",
             "physical-ai-defect-image-generation", "physical-ai-video-data-augmentation",
             "physical-ai-people-attribute-search",
             "physical-ai-infrastructure-setup-and-resilient-scaling"):
    d = base / name
    if not d.exists():
        continue
    r = scan(d, "router")
    if r:
        out.append(r)
    for ref in sorted((d / "references").glob("*/README.md")):
        rr = scan(ref.parent, f"ref:{name}")
        if rr:
            out.append(rr)

print(json.dumps(out, ensure_ascii=False, indent=1))

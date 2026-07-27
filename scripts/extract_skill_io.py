#!/usr/bin/env python3
"""
extract_skill_io.py — read the real I/O contract out of NVIDIA skill scripts.

For every `scripts/run.py` under a skill, this parses the argparse calls with
AST (never importing or executing the file) to get its inputs, and reads the
sibling `scripts/report_schema.json` to get its outputs. That pairing is the
skill's actual contract — far more reliable than prose.

Usage:
    python extract_skill_io.py <path-containing-nvidia-skills/> out.json
"""

import ast, json, re, sys
from pathlib import Path
ROOT = Path(sys.argv[1])
base = ROOT/"nvidia-skills/skills"

def args_of(run_py):
    """Read argparse calls without executing the file."""
    try: tree = ast.parse(run_py.read_text(encoding="utf-8", errors="replace"))
    except Exception: return []
    out=[]
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            names=[a.value for a in node.args if isinstance(a, ast.Constant)]
            if not names: continue
            help_=""; req=None; default=None
            for kw in node.keywords:
                if kw.arg=="help" and isinstance(kw.value, ast.Constant): help_=kw.value.value
                if kw.arg=="required" and isinstance(kw.value, ast.Constant): req=kw.value.value
                if kw.arg=="default" and isinstance(kw.value, ast.Constant): default=kw.value.value
            positional = not names[0].startswith("-")
            out.append({"flag":" ".join(names), "help":help_,
                        "required": positional or bool(req), "default":default})
    return out

def schema_of(p):
    try: d=json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception: return []
    props=d.get("properties",{})
    req=set(d.get("required",[]))
    rows=[]
    for k,v in props.items():
        t=v.get("type","")
        if isinstance(t,list): t="|".join(t)
        desc=v.get("description","")
        if not desc and "enum" in v: desc="one of: "+", ".join(map(str,v["enum"]))
        rows.append({"field":k,"type":t,"required":k in req,"desc":desc[:180]})
    return rows

res={}
for skill in sorted(base.glob("omniverse-*"))+sorted(base.glob("physical-ai-*")):
    for run in sorted(skill.rglob("scripts/run.py")):
        unit = run.parent.parent
        key = str(unit.relative_to(base))
        res[key]={"args":args_of(run),
                  "schema":schema_of(unit/"scripts"/"report_schema.json")
                            if (unit/"scripts"/"report_schema.json").exists() else []}
json.dump(res, open(sys.argv[2],"w"), ensure_ascii=False, indent=1)
print("units with run.py:", len(res))
print("with schema      :", sum(1 for v in res.values() if v["schema"]))

#!/usr/bin/env bash
# End-to-end Omniverse asset pipeline. Exits non-zero if any stage regresses,
# so it works as a CI gate as-is.
#
#   robot source (URDF/MuJoCo)
#     -> USD                     urdf_usd_converter / mujoco_usd_converter
#     -> USD validation          nvidia_usd_validate
#     -> SimReady baseline       simready-validate      (expected: FAIL)
#     -> conformance             simready_conform.py
#     -> SimReady re-validate    simready-validate      (required: PASS)
#     -> physics smoke           ovphysx, 120 steps
#
# 2D drawings enter the same pipeline through scripts/drawing_to_usd.py, which
# extrudes a closed DXF profile into a solid. A single extruded part has one
# rigid body, so it cannot satisfy any stock Prop-* profile (they all require
# FET004 / RB.MB.001, "at least two rigid bodies") — it defaults to the local
# Prop-Static-Neutral instead. See profiles/prop-static.toml.
#
# Usage:  ./scripts/run_pipeline.sh examples/urdf/arm2.urdf [profile] [version]
#         ./scripts/run_pipeline.sh examples/drawing/bracket.dxf
#         DXF_THICKNESS=0.012 ./scripts/run_pipeline.sh part.dxf

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[ -f "$ROOT/.env.ov" ] || { echo "Run ./scripts/bootstrap_env.sh first."; exit 1; }
# shellcheck disable=SC1091
source "$ROOT/.env.ov"

SRC="${1:?usage: run_pipeline.sh <asset.urdf|asset.xml|asset.dxf> [profile] [version]}"
case "$SRC" in
  *.dxf) DEFAULT_PROFILE="Prop-Static-Neutral" ;;
  *)     DEFAULT_PROFILE="Prop-Robotics-Neutral" ;;
esac
PROFILE="${2:-$DEFAULT_PROFILE}"
PROFILE_VERSION="${3:-1.0.0}"
# DXF knobs. Run scripts/inspect_dxf.py on a drawing first — it reports which
# layers hold geometry and whether the profile needs chaining.
DXF_THICKNESS="${DXF_THICKNESS:-0.012}"   # metres
DXF_DENSITY="${DXF_DENSITY:-7850}"        # kg/m3, steel
DXF_LAYERS="${DXF_LAYERS:-}"              # e.g. OUTLINE,HOLES
DXF_UNITS="${DXF_UNITS:-}"                # e.g. mm, when the file declares none
DXF_CHAIN_TOL="${DXF_CHAIN_TOL:-}"        # drawing units, joins open segments

NAME="$(basename "${SRC%.*}")"
OUT="$ROOT/.out/$NAME"
SPECS="$SIMREADY_FOUNDATION_SPEC_ROOT"
rm -rf "$OUT"; mkdir -p "$OUT"

STAGE=0
FAILED=0
stage() { STAGE=$((STAGE+1)); printf '\n\033[1m[%d] %s\033[0m\n' "$STAGE" "$*"; }
ok()    { printf '    \033[32m✓\033[0m %s\n' "$*"; }
bad()   { printf '    \033[31m✗\033[0m %s\n' "$*"; FAILED=1; }
note()  { printf '      %s\n' "$*"; }

sr_validate() {  # $1=asset  $2=json out  -> exit status of simready-validate
  # --profiles-path is repeatable; the local file adds profiles without
  # shadowing the stock set.
  local extra=()
  [ -f "$ROOT/profiles/prop-static.toml" ] && extra=(--profiles-path "$ROOT/profiles/prop-static.toml")
  "$SR_VENV/bin/simready-validate" "$1" \
      --profile "$PROFILE" --version "$PROFILE_VERSION" \
      --rules-path    "$SPECS/capabilities" \
      --features-path "$SPECS/features" \
      --profiles-path "$SPECS/profiles/profiles.toml" \
      "${extra[@]}" \
      --output "$2" >"$2.log" 2>&1
}

feature_summary() {  # $1=json
  "$SR_VENV/bin/python" - "$1" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print("      (no report: %s)" % e); raise SystemExit
for asset, r in d.items():
    for f, v in sorted(r.get("features_summary", {}).items()):
        mark = "PASS" if v.get("passed") else "FAIL"
        fails = v.get("failing requirements", "")
        print("      %-4s %-24s %s" % (mark, f, fails))
PY
}

echo "asset   : $SRC"
echo "profile : $PROFILE v$PROFILE_VERSION"
echo "output  : $OUT"

# ---------------------------------------------------------------- 1. convert
stage "Convert to USD"
CONV=""; DRAWING=0
case "$SRC" in
  *.urdf) CONV="$OV_VENV/bin/urdf_usd_converter" ;;
  *.xml)  CONV="$OV_VENV/bin/mujoco_usd_converter" ;;
  *.dxf)  DRAWING=1 ;;
  *.usd|*.usda|*.usdc) ;;
  *) echo "unsupported input: $SRC"; exit 2 ;;
esac

if [ "$DRAWING" = 1 ]; then
  dxf_opts=()
  [ -n "$DXF_LAYERS" ]    && dxf_opts+=(--layers "$DXF_LAYERS")
  [ -n "$DXF_UNITS" ]     && dxf_opts+=(--units "$DXF_UNITS")
  [ -n "$DXF_CHAIN_TOL" ] && dxf_opts+=(--chain-tolerance "$DXF_CHAIN_TOL")
  if "$OV_VENV/bin/python" "$ROOT/scripts/drawing_to_usd.py" "$SRC" "$OUT/converted" \
        --name "$NAME" --thickness "$DXF_THICKNESS" --density "$DXF_DENSITY" \
        "${dxf_opts[@]}" \
        --report "$OUT/drawing.json" >"$OUT/convert.log" 2>&1; then
    ASSET="$OUT/converted/$NAME.usdc"
    ok "drawing_to_usd -> extruded solid (${DXF_THICKNESS} m thick)"
    "$OV_VENV/bin/python" - "$OUT/drawing.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print("      units %s (x%g to m) · %d loops, %d holes"
      % (d["units"], d["unit_scale_to_m"], d["loops"], d["holes"]))
print("      %d points / %d faces · %.1f cm3 · %.3f kg"
      % (d["points"], d["faces"], d["volume_m3"] * 1e6, d["mass_kg"]))
PY
  else
    bad "drawing conversion failed — see $OUT/convert.log"
    tail -5 "$OUT/convert.log" | sed 's/^/      /'; exit 1
  fi
elif [ -n "$CONV" ]; then
  if "$CONV" "$SRC" "$OUT/converted" >"$OUT/convert.log" 2>&1; then
    ASSET="$OUT/converted/$NAME.usda"
    [ -f "$ASSET" ] || ASSET="$(find "$OUT/converted" -maxdepth 1 -name '*.usda' | head -1)"
    ok "$(basename "$CONV") -> $(find "$OUT/converted" -name '*.usd*' | wc -l) layers"
    note "$ASSET"
  else
    bad "conversion failed — see $OUT/convert.log"; exit 1
  fi
else
  ASSET="$SRC"; ok "using existing USD"
fi

# --------------------------------------------------------------- 2. USD valid
stage "USD validation (nvidia_usd_validate)"
if "$OV_VENV/bin/nvidia_usd_validate" "$ASSET" \
      --json-output "$OUT/usd-validate.json" >"$OUT/usd-validate.log" 2>&1; then
  ok "no issues"
else
  bad "USD validation failed"
  grep -E "^ERROR" "$OUT/usd-validate.log" | head -8 | sed 's/^/      /'
fi

# ---------------------------------------------------------- 3. SimReady before
stage "SimReady baseline ($PROFILE)"
sr_validate "$ASSET" "$OUT/simready-before.json"
BEFORE=$?
if [ $BEFORE -eq 0 ]; then
  ok "already conformant"
else
  note "not yet conformant (expected for freshly converted assets)"
  grep -E "^\s+Rule:|^\s+Message:" "$OUT/simready-before.json.log" 2>/dev/null \
    | head -12 | sed 's/^/    /'
fi
feature_summary "$OUT/simready-before.json"

# ------------------------------------------------------------- 4. conformance
stage "Apply conformance fixes"
if "$SR_VENV/bin/python" "$ROOT/scripts/simready_conform.py" \
      "$ASSET" "$OUT/conformed" --name "$NAME" \
      --profile "$PROFILE" --profile-version "$PROFILE_VERSION" \
      --report "$OUT/conform.json" >"$OUT/conform.log" 2>&1; then
  # the container is chosen by simready_conform (.usd for mesh-heavy stages,
  # .usda otherwise), so read the path it reports rather than assuming
  CONFORMED="$("$SR_VENV/bin/python" -c "
import json,sys; print(json.load(open(sys.argv[1]))['fixes']['NP.005_flattened_to'])
" "$OUT/conform.json")"
  ok "wrote $CONFORMED"
  "$SR_VENV/bin/python" - "$OUT/conform.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))["fixes"]
for k, v in d.items():
    if isinstance(v, list): v = ", ".join(v) or "(none)"
    elif isinstance(v, dict): v = json.dumps(v)[:90]
    print("      %-26s %s" % (k, v))
PY
else
  bad "conformance step failed — see $OUT/conform.log"; exit 1
fi

# ----------------------------------------------------------- 5. SimReady after
stage "SimReady re-validation"
sr_validate "$CONFORMED" "$OUT/simready-after.json"
AFTER=$?
feature_summary "$OUT/simready-after.json"
if [ $AFTER -eq 0 ]; then
  ok "[PASSED] $PROFILE v$PROFILE_VERSION"
else
  bad "[FAILED] $PROFILE v$PROFILE_VERSION — residual requirements need an agent"
  grep -E "^\s+Message:" "$OUT/simready-after.json.log" 2>/dev/null | head -8 | sed 's/^/    /'
fi

# -------------------------------------------------------------- 6. physics
stage "Physics smoke test (ovphysx, 120 steps)"
if "$OV_VENV/bin/python" "$ROOT/scripts/sim_check.py" "$CONFORMED" \
      >"$OUT/sim.log" 2>&1; then
  ok "$(grep SIMULATED "$OUT/sim.log" | tail -1)"
else
  bad "conformed asset no longer simulates — conformance broke dynamics"
  tail -5 "$OUT/sim.log" | sed 's/^/      /'
fi

# ------------------------------------------------------------------ summary
printf '\n\033[1m── summary ──\033[0m\n'
printf '  SimReady before : %s\n' "$([ $BEFORE -eq 0 ] && echo PASS || echo FAIL)"
printf '  SimReady after  : %s\n' "$([ $AFTER  -eq 0 ] && echo PASS || echo FAIL)"
printf '  reports         : %s\n' "$OUT"
if [ $FAILED -eq 0 ]; then
  printf '\n\033[32mpipeline OK\033[0m\n'; exit 0
else
  printf '\n\033[31mpipeline FAILED\033[0m\n'; exit 1
fi

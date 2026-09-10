#!/usr/bin/env bash
set -euo pipefail
visuals_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workshop_root="$(cd -- "$visuals_dir/../.." && pwd)"
python3 "$visuals_dir/build_architecture.py"
python3 "$visuals_dir/build_diagrams.py"
node "$visuals_dir/build_viewer.mjs"
node "$visuals_dir/build_concept_viewer.mjs"
node "$visuals_dir/build_teaching_figures.mjs"
drawio -x -f png -s 2 -b 40 -o "$workshop_root/static/images/aws-architecture.png" "$workshop_root/static/images/aws-architecture.drawio"
drawio -x -f svg -b 40 -o "$workshop_root/static/images/aws-architecture.svg" "$workshop_root/static/images/aws-architecture.drawio"
python3 "$visuals_dir/finalize_architecture_svg.py"

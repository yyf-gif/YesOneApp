#!/bin/sh
# Rebuild art/ from the sheets in art_src/ (1 = skater sheet, 2 = vintage sheet, 3/4 = full fits, 5 = background)
cd "$(dirname "$0")/.."
rm -f art/*.png
python3 tools/make_art.py .
python3 tools/align.py . sk_top sk_top_pose_raw sk_top_pose 0.45
python3 tools/align.py . vt_top vt_top_pose_raw vt_top_pose 0.45
rm -f art/*_raw.png
python3 tools/neck.py .
# cuffs.json (where hands come out of the sleeves) is kept as is

# The Street Stylist — 9:16 video source

Built on the stick-figure style (`rig.py`, `fx.py`). Everything is drawn in code with pycairo; audio is synthesized.

| File | What it is |
|---|---|
| `street_stylist.py` | Main script: story timeline, shots/cuts, stylist + walkers, clothes, palettes, text, post FX, soundtrack |
| `rig.py`, `fx.py` | Original style source (figure rig + comic FX) |
| `garments.py` | Fabric grain textures and shoe/beret helpers |
| `pixel_emoji.py` | 3D pixel-art emoji (😕😳😍😐😮💅😩🤑) and voxel colour chips |
| `render_par.py` | Renders a quarter of the frames per process (fast parallel render) |

## Requirements
`pip install pycairo numpy scipy pillow`, `ffmpeg`, fonts **Silkscreen** (Google Fonts) and **Noto Color Emoji** not needed (emoji are pixel-drawn).

## Render
```bash
python3 street_stylist.py --preview 2.2,10.8      # still frames
python3 street_stylist.py --audio-only            # audio.wav
for k in 0 1 2 3; do python3 render_par.py $k 4 & done; wait
printf "file 'part0.mp4'\nfile 'part1.mp4'\nfile 'part2.mp4'\nfile 'part3.mp4'\n" > parts.txt
ffmpeg -f concat -safe 0 -i parts.txt -i audio.wav -c:v copy -c:a aac -shortest street_stylist.mp4
```
Timing, colours, positions and shots are constants near the top of `street_stylist.py` (`SN`, `CUTS`, `SHOTS`, `WOMEN`, colour hex values).

# Skater vs Vintage (Round 1) — source

Same video as Streetwear vs Preppy (same timeline + sound), new outfits:
- LEFT  SKATER : racing jacket, crossbody bag, cargo jeans, skate shoes, skateboard, navy beanie
- RIGHT VINTAGE: floral shirt, suede jacket, pleated trousers (belted), leather boots, saddle bag, sunglasses
- Final pose tops come from the full-fit images: skater = left hand in pocket, right hand on the board;
  vintage = both hands in the jacket pockets, belt showing between the jacket fronts.
- Necks: like the original art, the inside of each collar is painted as the grey stick-figure neck (tools/neck.py).
- Glow: a soft colour glow around each fit (GLOW_L neon pink / GLOW_R warm amber), it builds up as pieces go on.
- Background: art_src/5.webp mirrored so the skate park is on the left -> bg_left.png / bg_right.png.

Render:
    pip install skia-python numpy pillow scipy        # ffmpeg on PATH
    python animate.py stills 6.5 11.5                 # preview frames
    python animate.py chunk 0 870                     # all frames -> frames/
    ffmpeg -framerate 60 -i frames/f%04d.png -i sfx.wav -c:v libx264 -crf 16 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest skater_vs_vintage.mp4
Rebuild the art from art_src/:  sh tools/build_art.sh
Names/colours: NAME_L/NAME_R, ITEM_L/ITEM_R, ACC_TXT_*, GLOW_* at the top of animate.py; outfit() places the pieces.

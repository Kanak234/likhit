"""
Store icon set for Likhit from its own 512 px app icon (assets/icon/likhit-icon-512.png).
WHY Pillow: Likhit's only image library — no extra tool on the CI machine.
FLOW: build_msix.ps1 → python make_icons.py <png> <out_dir> → Assets\\*.png
"""
import os, sys
from PIL import Image
SIZES = {"Square44x44Logo": (44, 44), "StoreLogo": (50, 50), "Square150x150Logo": (150, 150),
         "Wide310x150Logo": (310, 150), "Square310x310Logo": (310, 310)}
src = Image.open(sys.argv[1]).convert("RGBA")
os.makedirs(sys.argv[2], exist_ok=True)
for name, (w, h) in SIZES.items():
    for scale in (1, 2):
        W, H = w * scale, h * scale
        side = int(min(W, H) * 0.85)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.paste(src.resize((side, side), Image.LANCZOS), ((W - side) // 2, (H - side) // 2))
        canvas.save(os.path.join(sys.argv[2], name + ("" if scale == 1 else ".scale-200") + ".png"))
print("icons written to", sys.argv[2])

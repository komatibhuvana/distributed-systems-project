"""Crop the embedded figures from the page images of 273_paper1.docx.

Each page image is 1241x1754 (A4 @150dpi). Boxes are (left, upper, right, lower)
in pixels, chosen to sit inside the whitespace band around each figure so no
body text or caption is captured.
"""
from PIL import Image
import os

MEDIA = "/tmp/docx_extract/word/media"
OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

# figure_name: (page_image, (left, upper, right, lower))
CROPS = {
    "fig1_tandem_arch":   ("image4.png",  (150, 248, 1095, 880)),
    "fig2_mmn_line":      ("image5.png",  (175, 590, 1075, 1095)),
    "fig3_delivery_thr":  ("image6.png",  (205, 150, 1070, 735)),
    "fig4_heavytail_4p":  ("image9.png",  (170, 150, 1090, 968)),
    "fig5_reality_gap":   ("image10.png", (185, 578, 1070, 1108)),
    "fig6_tail_risk":     ("image11.png", (190, 762, 1060, 1298)),
    "fig7_mmn_bars":      ("image13.png", (170, 378, 1080, 690)),
    "fig8_util_thr":      ("image14.png", (170, 150, 1090, 590)),
    "fig9_convergence":   ("image15.png", (190, 155, 1060, 675)),
    "fig10_load_test":    ("image15.png", (190, 1058, 1080, 1495)),
}

for name, (img, box) in CROPS.items():
    src = Image.open(os.path.join(MEDIA, img))
    crop = src.crop(box)
    path = os.path.join(OUT, name + ".png")
    crop.save(path)
    print(f"{name:22} <- {img} {box}  -> {crop.size}")
print("done")

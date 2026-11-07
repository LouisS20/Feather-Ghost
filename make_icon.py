"""Génère feather_ghost.ico et feather_ghost.png (nécessite Pillow)."""
from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Fond arrondi dégradé violet
grad = Image.new("RGBA", (S, S))
gp = grad.load()
for y in range(S):
    for x in range(S):
        t = (x + y) / (2 * S)
        gp[x, y] = (int(40 + 90 * t), int(24 + 50 * t), int(90 + 140 * t), 255)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([40, 40, S - 40, S - 40], radius=220, fill=255)
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)

# Plume
feather = [(250, 780), (330, 520), (520, 300), (760, 200), (800, 250),
           (740, 480), (560, 680), (330, 800)]
d.polygon(feather, fill=(245, 240, 255, 255))
# Nervure
d.line([(250, 800), (780, 225)], fill=(120, 90, 220, 255), width=22)
# Barbes
for k in range(6):
    t = 0.2 + k * 0.13
    x = 250 + (780 - 250) * t
    y = 800 + (225 - 800) * t
    d.line([(x, y), (x - 90, y + 20)], fill=(160, 130, 240, 255), width=10)

# Pointillés fantômes (le texte qui s'écrit)
for i, x in enumerate(range(230, 760, 70)):
    a = max(60, 255 - i * 25)
    d.ellipse([x, 850, x + 34, 884], fill=(255, 255, 255, a))

img.save("feather_ghost.png")
img.resize((256, 256), Image.LANCZOS).save(
    "feather_ghost.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("Icône générée.")

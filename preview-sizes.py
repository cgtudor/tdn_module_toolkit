from PIL import Image

img = Image.open('resources/tdn_toolkit.png')
print(f'Source image: {img.size[0]}x{img.size[1]}')

# Create preview of small sizes
sizes = [16, 32, 48, 64]
preview = Image.new('RGBA', (sum(sizes) + len(sizes) * 10 + 10, 80), (40, 40, 40, 255))

x = 10
for s in sizes:
    resized = img.resize((s, s), Image.Resampling.LANCZOS)
    y = (80 - s) // 2
    preview.paste(resized, (x, y))
    x += s + 10

preview.save('resources/icon_sizes_preview.png')
print('Preview saved: resources/icon_sizes_preview.png')

import os
from PIL import Image, ImageDraw, ImageFont

def generate_bmfont(output_prefix, font_size, line_height, is_bold=False):
    if is_bold and os.path.exists("C:\\Windows\\Fonts\\segoeuib.ttf"):
        font_path = "C:\\Windows\\Fonts\\segoeuib.ttf"
    elif os.path.exists("C:\\Windows\\Fonts\\segoeui.ttf"):
        font_path = "C:\\Windows\\Fonts\\segoeui.ttf"
    elif is_bold and os.path.exists("C:\\Windows\\Fonts\\arialbd.ttf"):
        font_path = "C:\\Windows\\Fonts\\arialbd.ttf"
    else:
        font_path = "C:\\Windows\\Fonts\\arial.ttf"

    font = ImageFont.truetype(font_path, font_size)

    # Characters to include:
    # 1. ASCII printable 32 to 126
    chars = [chr(i) for i in range(32, 127)]
    # 2. Hebrew block 0x05D0 to 0x05EA
    for i in range(0x05D0, 0x05EB):
        chars.append(chr(i))
    # 3. Common symbols: bullet, geresh, gershayim, shekel, degree, slash
    extra = ['•', '״', '׳', '₪', '°', '/', '-', '(', ')', '[', ']', '+', ':']
    for c in extra:
        if c not in chars:
            chars.append(c)

    # Compact 256x256 texture for ultra-low RAM footprint on real Garmin watches
    tex_w, tex_h = 256, 256
    img = Image.new("RGBA", (tex_w, tex_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cur_x, cur_y = 2, 2
    max_row_h = 0
    char_records = []

    ascent, descent = font.getmetrics()
    base = ascent

    for ch in chars:
        cid = ord(ch)
        bbox = font.getbbox(ch)
        if ch == ' ':
            w = font.getlength(ch)
            char_records.append((cid, 0, 0, 0, 0, 0, 0, int(w)))
            continue

        left, top, right, bottom = bbox
        glyph_w = right - left
        glyph_h = bottom - top
        adv = int(font.getlength(ch))

        if cur_x + glyph_w + 3 >= tex_w:
            cur_x = 2
            cur_y += max_row_h + 3
            max_row_h = 0

        if cur_y + glyph_h + 3 >= tex_h:
            print(f"Warning: font texture overflow for {ch} at y={cur_y}")
            break

        draw.text((cur_x - left, cur_y - top), ch, font=font, fill=(255, 255, 255, 255))

        xoffset = left
        yoffset = top + base

        char_records.append((cid, cur_x, cur_y, glyph_w, glyph_h, xoffset, top, adv))

        cur_x += glyph_w + 3
        if glyph_h > max_row_h:
            max_row_h = glyph_h

    png_filename = f"{output_prefix}_0.png"
    img.save(png_filename)

    fnt_filename = f"{output_prefix}.fnt"
    base_png = os.path.basename(png_filename)
    with open(fnt_filename, "w", encoding="utf-8") as f:
        # Standard Garmin-compatible BMFont format (no spaces in face name, exact standard common line)
        f.write(f'info face="Arial" size={font_size} bold={1 if is_bold else 0} italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing=1,1\n')
        f.write(f'common lineHeight={line_height} base={base} scaleW={tex_w} scaleH={tex_h} pages=1 packed=0\n')
        f.write(f'page id=0 file="{base_png}"\n')
        f.write(f'chars count={len(char_records)}\n')
        for rec in char_records:
            cid, x, y, gw, gh, xo, yo, adv = rec
            f.write(f'char id={cid:<5} x={x:<5} y={y:<5} width={gw:<5} height={gh:<5} xoffset={xo:<5} yoffset={yo:<5} xadvance={adv:<5} page=0 chnl=15\n')

    print(f"Generated {fnt_filename} and {png_filename} with {len(char_records)} characters ({font_size}px, 256x256).")

if __name__ == "__main__":
    out_dir = "c:\\Users\\razie\\Development\\Grocery list\\garmin\\resources\\fonts"
    os.makedirs(out_dir, exist_ok=True)
    # Main font: 26px
    generate_bmfont(os.path.join(out_dir, "hebrew_font"), 26, 32, is_bold=False)
    # Small font: 19px
    generate_bmfont(os.path.join(out_dir, "hebrew_small"), 19, 24, is_bold=False)

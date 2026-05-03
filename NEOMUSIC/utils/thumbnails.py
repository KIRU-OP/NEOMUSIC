import os
import aiofiles
import aiohttp
import logging
import re
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL
from NEOMUSIC import app

logging.basicConfig(level=logging.ERROR)

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Helper to keep Title clean for rendering
def clean_title(text):
    return re.sub(r'[^\x00-\x7f\u0900-\u097F\s]+', '', text)

async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_dynamic_pro.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        results_data = await results.next()
        data = results_data["result"][0]
        title = data.get("title", "Music Track")
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
    except:
        title, thumbnail = "Music Track", YOUTUBE_IMG_URL

    temp_path = os.path.join(CACHE_DIR, f"temp_{videoid}.jpg")
    async with aiohttp.ClientSession() as session:
        async with session.get(thumbnail) as resp:
            if resp.status == 200:
                async with aiofiles.open(temp_path, mode="wb") as f:
                    await f.write(await resp.read())

    try:
        # 1. BASE CANVAS
        width, height = 1280, 720
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        
        # 2. IMAGE PROCESSING
        yt_img = Image.open(temp_path).convert("RGBA")
        yt_img = ImageEnhance.Contrast(yt_img).enhance(1.2)
        
        img_w = 900
        portrait = ImageOps.fit(yt_img, (img_w, height), method=Image.Resampling.LANCZOS)
        
        # Blend Mask
        mask = Image.new("L", (img_w, height), 255)
        for x in range(img_w):
            if x < 450:
                alpha = int((x / 450) * 255)
                for y in range(height):
                    mask.putpixel((x, y), alpha)
        
        canvas.paste(portrait, (width - img_w, 0), mask)
        draw = ImageDraw.Draw(canvas)

        # 3. FONTS (Ensure 'font.ttf' supports both English & Marathi)
        font_p = "NEOMUSIC/assets/thumb/font.ttf"
        cursive_p = "NEOMUSIC/assets/thumb/cursive.ttf"
        
        try:
            full_song_f = ImageFont.truetype(cursive_p, 40)
            main_title_f = ImageFont.truetype(font_p, 140) # Large for first part
            sub_title_f = ImageFont.truetype(font_p, 70)   # Medium for second part
            small_f = ImageFont.truetype(font_p, 25)
        except:
            full_song_f = main_title_f = sub_title_f = small_f = ImageFont.load_default()

        # 4. DYNAMIC TEXT LOGIC
        raw_title = clean_title(title)
        words = raw_title.split()
        
        # Split title into two lines like the original "Fulala / Sugandh Maticha"
        if len(words) > 2:
            line1 = " ".join(words[:2]).upper()
            line2 = " ".join(words[2:5]).upper()
        else:
            line1 = raw_title.upper()
            line2 = ""

        # 5. DRAWING TEXT
        text_color = (30, 30, 30)
        
        draw.text((100, 230), "full song", fill=text_color, font=full_song_f)
        
        # First line (Big)
        draw.text((80, 260), line1[:15], fill=text_color, font=main_title_f)
        
        # Second line (Indented & Smaller)
        if line2:
            draw.text((300, 470), line2[:20], fill=text_color, font=sub_title_f)

        # 6. BRANDING
        draw.text((360, 600), "f  ", fill=(80, 80, 80), font=small_f)
        draw.text((315, 625), "DH EDITING CLUB", fill=(50, 50, 50), font=small_f)
        draw.text((20, 685), "www.Marathi.com", fill=(150, 150, 150), font=small_f)

        # 7. ARTISTIC GLOW
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        o_draw = ImageDraw.Draw(overlay)
        o_draw.ellipse([650, 50, 1100, 500], fill=(0, 200, 255, 20))
        canvas = Image.alpha_composite(canvas, overlay)

        if os.path.exists(temp_path): os.remove(temp_path)
        canvas.convert("RGB").save(cache_path, "PNG", quality=100)
        return cache_path

    except Exception as e:
        logging.error(f"Thumbnail Pro Error: {e}")
        return YOUTUBE_IMG_URL

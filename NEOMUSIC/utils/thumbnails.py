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

def clean_title(text):
    return re.sub(r'[^\x00-\x7f\u0900-\u097F\u00A0-\u00FF]+', '', text)

async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_premium_kiru.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        results_data = await results.next()
        data = results_data["result"][0]
        title = data.get("title", "Unknown Track")
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        artist = data.get("channel", {}).get("name", "Neo Music")
    except:
        title, thumbnail, artist = "Music Track", YOUTUBE_IMG_URL, "Neo Music"

    temp_path = os.path.join(CACHE_DIR, f"temp_{videoid}.jpg")
    async with aiohttp.ClientSession() as session:
        async with session.get(thumbnail) as resp:
            if resp.status == 200:
                async with aiofiles.open(temp_path, mode="wb") as f:
                    await f.write(await resp.read())

    try:
        # 1. BASE CANVAS
        width, height = 1280, 720
        yt_img = Image.open(temp_path).convert("RGBA")
        
        # 2. FUTURISTIC BACKGROUND (Deep Blur + Dark Overlay)
        bg = yt_img.resize((width, height))
        bg = bg.filter(ImageFilter.GaussianBlur(70))
        bg = ImageEnhance.Brightness(bg).enhance(0.2)
        
        # Create a bottom dark gradient for UI clarity
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        o_draw = ImageDraw.Draw(overlay)
        o_draw.rectangle([0, 550, 1280, 720], fill=(0, 0, 0, 100)) # Bottom shadow
        bg = Image.alpha_composite(bg, overlay)
        draw = ImageDraw.Draw(bg)

        # 3. GLOWING CIRCULAR DISK (Left)
        c_size = 420
        # Multi-layer Glow
        for i in range(20, 0, -2):
            alpha = int(80 * (1 - i/20))
            draw.ellipse([135-i, 145-i, 135+c_size+i, 145+c_size+i], outline=(0, 255, 255, alpha), width=2)
        
        # Smooth Image Masking
        mask = Image.new("L", (c_size*2, c_size*2), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, c_size*2, c_size*2), fill=255)
        mask = mask.resize((c_size, c_size), Image.Resampling.LANCZOS)
        
        disk_img = ImageOps.fit(yt_img, (c_size, c_size), method=Image.Resampling.LANCZOS)
        bg.paste(disk_img, (135, 145), mask)
        
        # White Sharp Border
        draw.ellipse([135, 145, 135+c_size, 145+c_size], outline=(255, 255, 255, 180), width=4)

        # 4. FONTS
        font_p = "NEOMUSIC/assets/thumb/font.ttf"
        try:
            title_f = ImageFont.truetype(font_p, 58)
            artist_f = ImageFont.truetype(font_p, 32)
            status_f = ImageFont.truetype(font_p, 24)
            brand_f = ImageFont.truetype(font_p, 28)
        except:
            title_f = artist_f = status_f = brand_f = ImageFont.load_default()

    # 5. TEXT (Right Side)
        x_text = 620
        # Song Title (Hard White)
        t_clean = clean_title(title[:32] + ".." if len(title) > 32 else title)
        draw.text((x_text, 190), t_clean.upper(), fill=(255, 255, 255), font=title_f)
        
        # Artist (Greyish)
        a_clean = clean_title(artist)
        draw.text((x_text, 270), a_clean.upper(), fill=(180, 180, 180), font=artist_f)

        # Status Info (Cyber Blue Glow)
        draw.text((x_text, 380), "● SYSTEM ONLINE", fill=(0, 255, 255), font=status_f)
        draw.text((x_text, 420), "PLAYING LOSSLESS AUDIO (320kbps)", fill=(140, 140, 140), font=status_f)
        draw.text((x_text, 460), f"CONTROLLED BY @{app.username.upper()}", fill=(140, 140, 140), font=status_f)

        # 6. REFINED UI ICONS (Manual Draw for Sharpness)
        def draw_premium_controls(x, y):
            # Previous Skip
            draw.polygon([(x, y+15), (x+25, y), (x+25, y+30)], fill="white")
            draw.rectangle([x-8, y, x-3, y+30], fill="white")
            # Play/Pause (Clean Bars)
            draw.rectangle([x+60, y, x+72, y+35], fill="white")
            draw.rectangle([x+82, y, x+94, y+35], fill="white")
            # Next Skip
            draw.polygon([(x+130, y), (x+130, y+30), (x+155, y+15)], fill="white")
            draw.rectangle([x+158, y, x+163, y+30], fill="white")

        draw_premium_controls(260, 610)

        # Bottom UI symbols
        draw.text((700, 615), "≡      ⇄      📂      ♥", fill="white", font=artist_f)

        # 7. TOP BRANDING (Hardcoded KIRU)
        draw.text((60, 40), "Hi, User", fill=(150, 150, 150), font=status_f)
        draw.text((width//2 - 60, 40), "KIRU PLAYER", fill=(255, 255, 255), font=status_f)
        draw.text((1120, 40), "KIRU", fill=(255, 255, 255), font=brand_f)
        
        # Bottom Details
        draw.text((150, 685), "< 21° >", fill="white", font=status_f)
        draw.text((1050, 685), "< 21° >", fill="white", font=status_f)
        
        # Futuristic Power Button
        draw.ellipse([width//2-25, 670, width//2+25, 715], outline=(0, 255, 255, 150), width=2)
        draw.rectangle([width//2-2, 675, width//2+2, 688], fill="white")

        # Save and Cleanup
        if os.path.exists(temp_path): os.remove(temp_path)
        bg.convert("RGB").save(cache_path, "PNG", quality=100)
        return cache_path

    except Exception as e:
        logging.error(f"Neo UI Error: {e}")
        return YOUTUBE_IMG_URL

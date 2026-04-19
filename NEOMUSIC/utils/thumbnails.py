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

# Title cleaning to avoid boxes
def clean_title(text):
    return re.sub(r'[^\x00-\x7f\u0900-\u097F\u00A0-\u00FF]+', '', text)

async def get_thumb(videoid: str) -> str:
    # Unique cache name
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_kiru_dashboard.png")
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
        title, thumbnail, artist = "Music Track", YOUTUBE_IMG_URL, "Kiru Music"

    temp_path = os.path.join(CACHE_DIR, f"temp_{videoid}.jpg")
    async with aiohttp.ClientSession() as session:
        async with session.get(thumbnail) as resp:
            if resp.status == 200:
                async with aiofiles.open(temp_path, mode="wb") as f:
                    await f.write(await resp.read())

    try:
        # 1. CANVAS SETUP
        width, height = 1280, 720
        yt_img = Image.open(temp_path).convert("RGBA")
        
        # 2. BLURRED DASHBOARD BACKGROUND
        bg = yt_img.resize((width, height))
        bg = bg.filter(ImageFilter.GaussianBlur(60))
        bg = ImageEnhance.Brightness(bg).enhance(0.25)
        draw = ImageDraw.Draw(bg)

        # 3. CIRCULAR MUSIC ART (Anti-aliased)
        circle_size = 400
        mask = Image.new("L", (circle_size * 2, circle_size * 2), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, circle_size * 2, circle_size * 2), fill=255)
        mask = mask.resize((circle_size, circle_size), Image.Resampling.LANCZOS)
        
        main_img = ImageOps.fit(yt_img, (circle_size, circle_size), method=Image.Resampling.LANCZOS)
        
        # Outer Glowing Ring
        draw.ellipse([145, 155, 145+circle_size+10, 155+circle_size+10], outline=(255, 255, 255, 40), width=10)
        bg.paste(main_img, (150, 160), mask)

        # 4. FONTS SETUP
        font_p = "NEOMUSIC/assets/thumb/font.ttf"
        try:
            title_f = ImageFont.truetype(font_p, 55)
            artist_f = ImageFont.truetype(font_p, 30)
            small_f = ImageFont.truetype(font_p, 22)
            brand_f = ImageFont.truetype(font_p, 25) # Slightly bigger for Kiru
        except:
            title_f = artist_f = small_f = brand_f = ImageFont.load_default()

        # 5. TEXT (Right Side)
        t_text = clean_title(title[:35] + ".." if len(title) > 35 else title)
        draw.text((650, 200), t_text.upper(), fill=(255, 255, 255), font=title_f)
        
        a_text = clean_title(artist)
        draw.text((650, 275), a_text.upper(), fill=(180, 180, 180), font=artist_f)

        # Dashboard Text Info
        draw.text((650, 400), "SYSTEM ONLINE", fill=(0, 200, 255), font=small_f)
        draw.text((650, 435), "PLAYING HIGH QUALITY AUDIO", fill=(150, 150, 150), font=small_f)
        draw.text((650, 470), f"CONTROLLED BY @{app.username.upper()}", fill=(150, 150, 150), font=small_f)

        # 6. FIXING BOXES (MANUAL ICON DRAWING)
        def draw_ui_icons(x, y):
            # Previous Skip
            draw.polygon([(x, y+15), (x+20, y), (x+20, y+30)], fill="white")
            draw.rectangle([x-5, y, x-2, y+30], fill="white")
            # Pause Button
            draw.rectangle([x+50, y, x+60, y+30], fill="white")
            draw.rectangle([x+70, y, x+80, y+30], fill="white")
            # Next Skip
            draw.polygon([(x+110, y), (x+110, y+30), (x+130, y+15)], fill="white")
            draw.rectangle([x+132, y, x+135, y+30], fill="white")

        draw_ui_icons(265, 620)

        # 7. TOP & BOTTOM BRANDING (Hardcoded KIRU)
        draw.text((50, 35), "Hi, User", fill=(150, 150, 150), font=small_f)
        draw.text((width//2 - 40, 35), "KIRU PLAYER", fill="white", font=small_f)
        
        # ---- KIRU HARDCODED HERE ----
        draw.text((1120, 35), "KIRU", fill=(255, 255, 255, 200), font=brand_f)
        
        # Bottom Details
        draw.text((150, 685), "< 21° >", fill="white", font=small_f)
        draw.text((1050, 685), "< 21° >", fill="white", font=small_f)
        
        # Center Power Button Draw
        draw.ellipse([width//2-20, 675, width//2+20, 715], outline="white", width=2)
        draw.rectangle([width//2-2, 680, width//2+2, 690], fill="white")

        # Cleanup & Save
        if os.path.exists(temp_path): os.remove(temp_path)
        bg.convert("RGB").save(cache_path, "PNG", quality=100)
        return cache_path

    except Exception as e:
        logging.error(f"Kiru Dashboard Error: {e}")
        return YOUTUBE_IMG_URL

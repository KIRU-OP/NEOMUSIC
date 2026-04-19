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

# Function to remove special characters that fonts can't read
def clean_text(text):
    return re.sub(r'[^\x00-\x7f\u0900-\u097F]+', '', text) # Supports English & Hindi

async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_final_neon.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        results_data = await results.next()
        data = results_data["result"][0]
        title = data.get("title", "Unknown Track")
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        artist = data.get("channel", {}).get("name", "Neo Music Bot")
    except:
        title, thumbnail, artist = "Music Track", YOUTUBE_IMG_URL, "Neo Music"

    temp_path = os.path.join(CACHE_DIR, f"temp_{videoid}.jpg")
    async with aiohttp.ClientSession() as session:
        async with session.get(thumbnail) as resp:
            if resp.status == 200:
                async with aiofiles.open(temp_path, mode="wb") as f:
                    await f.write(await resp.read())

    try:
        # 1. CANVAS & BACKGROUND
        img = Image.open(temp_path).convert("RGBA")
        bg = img.resize((1280, 720))
        bg = bg.filter(ImageFilter.GaussianBlur(50))
        bg = ImageEnhance.Brightness(bg).enhance(0.3)
        draw = ImageDraw.Draw(bg)

        # 2. MAIN SQUARE IMAGE (LEFT)
        sq_size = 450
        main_img = ImageOps.fit(img, (sq_size, sq_size), method=Image.Resampling.LANCZOS)
        
        # Purple Neon Glow Effect
        for i in range(12, 0, -1):
            alpha = int(255 * (1 - i/12) * 0.5)
            draw.rectangle([115-i, 135-i, 115+sq_size+i, 135+sq_size+i], outline=(191, 0, 255, alpha), width=2)
        
        bg.paste(main_img, (115, 135))
        draw.rectangle([115, 135, 115+sq_size, 135+sq_size], outline=(224, 0, 255, 255), width=6)

        # 3. FONTS SETUP (Important Fix for Boxes)
        # Tip: Use 'arial.ttf' or 'NotoSans-Bold.ttf' for better language support
        font_p = "NEOMUSIC/assets/thumb/font.ttf"
        try:
            # Agar aapke paas stylish font hai toh yahan naam badlein
            logo_font = ImageFont.truetype(font_p, 100) 
            title_font = ImageFont.truetype(font_p, 50)
            artist_font = ImageFont.truetype(font_p, 35)
            ui_font = ImageFont.truetype(font_p, 24)
        except:
            logo_font = title_font = artist_font = ui_font = ImageFont.load_default()

        # 4. TEXT RENDERING (RIGHT SIDE)
        x_pos = 650
        
        # Logo Text
        draw.text((x_pos, 80), "Music.", fill=(255, 255, 255, 255), font=logo_font)

        # Title Fix (Cleaning and Truncating)
        title_text = clean_text(title.upper())
        if len(title_text) > 25: title_text = title_text[:22] + "..."
        draw.text((x_pos, 220), title_text, fill=(255, 255, 255, 255), font=title_font)

        # Artist Fix
        artist_text = clean_text(artist.upper())
        if len(artist_text) > 30: artist_text = artist_text[:28] + ".."
        draw.text((x_pos, 300), artist_text, fill=(180, 180, 180, 255), font=artist_font)

        # "Available Now"
        draw.text((x_pos, 420), "AVAILABLE NOW", fill=(255, 255, 255, 255), font=artist_font)

        # 5. UI BUTTONS
        def draw_btn(x, y, txt):
            draw.rounded_rectangle([x, y, x+170, y+45], radius=22, outline=(255,255,255,150), width=2)
            draw.text((x+35, y+10), txt, fill="white", font=ui_font)

        draw_btn(x_pos, 480, "SPOTIFY")
        draw_btn(x_pos + 200, 480, "ITUNES")
        draw_btn(x_pos, 545, "AMAZON")
        draw_btn(x_pos + 200, 545, "YOUTUBE")

        # Footer
        footer = f"WWW.@{app.username.upper()}.COM"
        draw.text((x_pos, 640), footer, fill=(120, 120, 120, 255), font=artist_font)

        # Cleanup & Save
        if os.path.exists(temp_path): os.remove(temp_path)
        bg.convert("RGB").save(cache_path, "PNG", quality=100)
        return cache_path

    except Exception as e:
        logging.error(f"Error: {e}")
        return YOUTUBE_IMG_URL

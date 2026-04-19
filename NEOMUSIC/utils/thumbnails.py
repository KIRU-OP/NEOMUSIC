import os
import aiofiles
import aiohttp
import logging
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL
from NEOMUSIC import app

# Logging Setup
logging.basicConfig(level=logging.ERROR)

CACHE_DIR = "cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def truncate(text, length):
    if len(text) > length:
        return text[:length] + "..."
    return text

async def get_thumb(videoid: str) -> str:
    # 1. Check if thumbnail already exists in cache
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_neon_v2.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        # 2. Get Video Details from YouTube
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        results_data = await results.next()
        data = results_data["result"][0]
        title = data.get("title", "Unknown Track")
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        artist = data.get("channel", {}).get("name", "Neo Music")
    except Exception as e:
        logging.error(f"Search Error: {e}")
        title, thumbnail, artist = "Music Track", YOUTUBE_IMG_URL, "Various Artists"

    # 3. Download Thumbnail Image
    temp_path = os.path.join(CACHE_DIR, f"temp_{videoid}.jpg")
    async with aiohttp.ClientSession() as session:
        async with session.get(thumbnail) as resp:
            if resp.status == 200:
                f = await aiofiles.open(temp_path, mode="wb")
                await f.write(await resp.read())
                await f.close()
            else:
                return YOUTUBE_IMG_URL

    try:
        # --- START DESIGNING ---
        # 1. Create Base Canvas (1280x720)
        width, height = 1280, 720
        yt_img = Image.open(temp_path).convert("RGBA")
        
        # 2. Blurred Background (Full Screen)
        bg = yt_img.resize((width, height))
        bg = bg.filter(ImageFilter.GaussianBlur(60))
        enhancer = ImageEnhance.Brightness(bg)
        bg = enhancer.enhance(0.4) # Darken the background
        
        draw = ImageDraw.Draw(bg)

        # 3. Square Cover Image (Left Side)
        sq_size = 480
        main_img = ImageOps.fit(yt_img, (sq_size, sq_size), method=Image.Resampling.LANCZOS)
        
        # Draw Neon Glow behind the square
        for i in range(15, 0, -1):
            alpha = int(255 * (1 - i/15) * 0.4)
            draw.rectangle([100-i, 120-i, 100+sq_size+i, 120+sq_size+i], outline=(191, 0, 255, alpha), width=2)
        
        # Paste Main Square Image
        bg.paste(main_img, (100, 120))
        
        # Inner Solid Neon Border
        draw.rectangle([100, 120, 580, 600], outline=(224, 0, 255, 255), width=5)

        # 4. Typography (Right Side)
        font_path = "NEOMUSIC/assets/thumb/font.ttf"
        try:
            # Aap script.ttf bhi use kar sakte hain agar stylish logo chahiye
            font_logo = ImageFont.truetype(font_path, 90) 
            font_title = ImageFont.truetype(font_path, 55)
            font_artist = ImageFont.truetype(font_path, 30)
            font_small = ImageFont.truetype(font_path, 22)
        except:
            font_logo = font_title = font_artist = font_small = ImageFont.load_default()

        # Logo Text (Top Right)
        draw.text((680, 100), "Music.", fill=(255, 255, 255, 255), font=font_logo)

        # Title (All Caps)
        clean_title = truncate(title.upper(), 25)
        draw.text((680, 230), clean_title, fill=(255, 255, 255, 255), font=font_title)

        # Artist (Spaced Text)
        artist_text = "  ".join(list(artist[:20].upper()))
        draw.text((680, 310), artist_text, fill=(200, 200, 200, 255), font=font_artist)

        # "Available Now"
        draw.text((680, 420), "AVAILABLE NOW", fill=(255, 255, 255, 255), font=font_artist)

        # 5. Fake Streaming UI (Buttons style)
        def draw_ui(x, y, text):
            draw.rounded_rectangle([x, y, x+180, y+45], radius=20, outline=(255,255,255,100), width=2)
            draw.text((x+35, y+10), text, fill="white", font=font_small)

        draw_ui(680, 480, "SPOTIFY")
        draw_ui(880, 480, "ITUNES")
        draw_ui(680, 540, "AMAZON")
        draw_ui(880, 540, "YOUTUBE")

        # Bottom Website/Username
        draw.text((680, 630), f"WWW.@{app.username.upper()}.COM", fill=(150, 150, 150, 255), font=font_artist)

        # 6. Final Polish & Save
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        final_thumb = bg.convert("RGB")
        final_thumb.save(cache_path, "PNG", quality=100)
        return cache_path

    except Exception as e:
        logging.error(f"Final Error: {e}")
        return YOUTUBE_IMG_URL

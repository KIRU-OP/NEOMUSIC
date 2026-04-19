import os
import aiofiles
import aiohttp
import logging
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL
from NEOMUSIC import app

# Logging
logging.basicConfig(level=logging.ERROR)

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_futuristic.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        results_data = await results.next()
        data = results_data["result"][0]
        title = data.get("title", "Unknown Track")
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        artist = data.get("channel", {}).get("name", "Various Artists")
    except:
        title, thumbnail, artist = "Music Track", YOUTUBE_IMG_URL, "Neo Music"

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
        
        # 2. DARK THEME BACKGROUND
        # Background ko blur aur dark karke Tesla dashboard jaisa look dena
        bg = yt_img.resize((width, height))
        bg = bg.filter(ImageFilter.GaussianBlur(80))
        bg = ImageEnhance.Brightness(bg).enhance(0.2)
        draw = ImageDraw.Draw(bg)

        # 3. CIRCULAR MUSIC ART (LEFT SIDE)
        circle_size = 400
        # Rounded mask for circle
        mask = Image.new("L", (circle_size, circle_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, circle_size, circle_size), fill=255)
        
        main_img = ImageOps.fit(yt_img, (circle_size, circle_size), method=Image.Resampling.LANCZOS)
        
        # Disc Glow Effect (Metallic Ring)
        for i in range(25, 0, -2):
            alpha = int(100 * (1 - i/25))
            draw.ellipse([150-i, 160-i, 150+circle_size+i, 160+circle_size+i], outline=(255, 255, 255, alpha), width=2)
        
        bg.paste(main_img, (150, 160), mask)

        # 4. FONTS SETUP
        font_path = "NEOMUSIC/assets/thumb/font.ttf" # Use a clean Sans font like Roboto/Montserrat
        try:
            title_f = ImageFont.truetype(font_path, 65)
            artist_f = ImageFont.truetype(font_path, 35)
            small_f = ImageFont.truetype(font_path, 20)
            icon_f = ImageFont.truetype(font_path, 45) # For symbols
        except:
            title_f = artist_f = small_f = icon_f = ImageFont.load_default()

        # 5. TEXT (RIGHT SIDE)
        # Song Title
        clean_title = title[:25] + ".." if len(title) > 25 else title
        draw.text((650, 180), clean_title, fill=(255, 255, 255, 240), font=title_f)
        
        # Artist Name
        draw.text((650, 260), artist.upper(), fill=(180, 180, 180, 200), font=artist_f)

        # Lyrics Placeholder (Dotted lines style like the image)
        lyric_y = 380
        lyrics = ["Tell me one good reason why I should try", "Continuing to fight it", "Running in circle round and round"]
        for line in lyrics:
            draw.text((650, lyric_y), line, fill=(150, 150, 150, 150), font=small_f)
            lyric_y += 40

        # 6. DASHBOARD UI ELEMENTS (TOP & BOTTOM)
        # Top bar (Hi User, Time, Connectivity)
        draw.text((50, 30), "Hi, User", fill=(180, 180, 180, 200), font=small_f)
        draw.text((1100, 30), "My iPhone  5G", fill=(180, 180, 180, 200), font=small_f)
        
        # Center "MUSIC" logo at top
        draw.text((width//2 - 50, 30), "MUSICE", fill=(255, 255, 255, 180), font=small_f)

        # 7. PLAYBACK CONTROLS (BOTTOM)
        # Icons (Skip, Play, Shuffle) - Using Unicode Symbols
        controls_y = 600
        draw.text((200, controls_y), "⏮    ⏸    ⏭", fill=(255, 255, 255, 220), font=icon_f)
        draw.text((700, controls_y), "≡    ⇄    📂    ❤", fill=(200, 200, 200, 180), font=icon_f)

        # Bottom Bar (Temperature & Power)
        draw.text((150, 680), "<  21°  >", fill=(200, 200, 200, 200), font=small_f)
        draw.text((1050, 680), "<  21°  >", fill=(200, 200, 200, 200), font=small_f)
        
        # Power Icon Button (Circle)
        draw.ellipse([width//2-25, 670, width//2+25, 715], outline=(255,255,255,150), width=2)
        draw.text((width//2-10, 678), "⏻", fill="white", font=small_f)

        # Cleanup & Save
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        bg.convert("RGB").save(cache_path, "PNG", quality=100)
        return cache_path

    except Exception as e:
        logging.error(f"Futuristic UI Error: {e}")
        return YOUTUBE_IMG_URL

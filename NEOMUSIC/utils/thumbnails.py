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

# Cleaner to allow Marathi and English characters
def clean_title(text):
    return re.sub(r'[^\x00-\x7f\u0900-\u097F]+', '', text)

async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_same_to_same.png")
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
        # 1. BASE CANVAS (Pure White like the photo)
        width, height = 1280, 720
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        
        # 2. IMAGE PROCESSING (Right Side)
        yt_img = Image.open(temp_path).convert("RGBA")
        
        # Enhance image to look premium
        yt_img = ImageEnhance.Contrast(yt_img).enhance(1.2)
        yt_img = ImageEnhance.Sharpness(yt_img).enhance(1.5)
        
        # Resize and Fit to Right Side
        img_w = 880
        portrait = ImageOps.fit(yt_img, (img_w, height), method=Image.Resampling.LANCZOS)
        
        # 3. BLENDING MASK (To fade the left edge of the photo)
        mask = Image.new("L", (img_w, height), 255)
        for x in range(img_w):
            if x < 400: # Soft fade area
                alpha = int((x / 400) * 255)
                for y in range(height):
                    mask.putpixel((x, y), alpha)
        
        # Paste image on right with blend mask
        canvas.paste(portrait, (width - img_w, 0), mask)
        draw = ImageDraw.Draw(canvas)

        # 4. FONTS
        font_path = "NEOMUSIC/assets/thumb/font.ttf" # Use Marathi Calligraphy Font
        cursive_path = "NEOMUSIC/assets/thumb/cursive.ttf" # For 'full song'
        
        try:
            full_song_f = ImageFont.truetype(cursive_path, 38)
            main_title_f = ImageFont.truetype(font_path, 190) # Big text
            sub_title_f = ImageFont.truetype(font_path, 75)   # Sub text
            small_f = ImageFont.truetype(font_path, 25)
        except:
            full_song_f = main_title_f = sub_title_f = small_f = ImageFont.load_default()

        # 5. TEXT LAYOUT (Left Side)
        txt_col = (20, 20, 20) # Blackish grey
        
        # 'full song' cursive text
        draw.text((100, 235), "full song", fill=txt_col, font=full_song_f)
        
        # Main Title (Example: फुलाला)
        # You can use clean_title(title) here for dynamic Marathi titles
        draw.text((80, 265), "फुलाला", fill=txt_col, font=main_title_f)
        
        # Sub Title (Example: सुगंध मातीचा)
        draw.text((290, 490), "सुगंध मातीचा", fill=txt_col, font=sub_title_f)

        # 6. BRANDING & SOCIALS (Bottom Center-Left)
        draw.text((365, 600), "f  ", fill=(60, 60, 60), font=small_f)
        draw.text((320, 625), "DH EDITING CLUB", fill=(40, 40, 40), font=small_f)
        
        # Website Link (Bottom Left Corner)
        draw.text((20, 685), "www.Marathi.com", fill=(120, 120, 120), font=small_f)

        # 7. ADD BLUE ARTISTIC BRUSH GLOW
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        o_draw = ImageDraw.Draw(overlay)
        # Adding subtle blue shade behind the girl's face area
        o_draw.ellipse([600, 50, 1150, 550], fill=(0, 200, 255, 20))
        canvas = Image.alpha_composite(canvas, overlay)

        # Save result
        if os.path.exists(temp_path): os.remove(temp_path)
        canvas.convert("RGB").save(cache_path, "PNG", quality=100)
        return cache_path

    except Exception as e:
        logging.error(f"Error in Same-to-Same UI: {e}")
        return YOUTUBE_IMG_URL

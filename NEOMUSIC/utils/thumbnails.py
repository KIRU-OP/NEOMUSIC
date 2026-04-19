import os
import re
import aiofiles
import aiohttp
import logging
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL
from NEOMUSIC import app

# Logging Setup
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Helper function to truncate title
def truncate(text, length):
    if len(text) > length:
        return text[:length] + "..."
    return text

async def get_thumb(videoid: str) -> str:
    cache_path = os.path.join(CACHE_DIR, f"{videoid}_final_v2.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        results_data = await results.next()
        data = results_data["result"][0]
        title = data.get("title", "Unsupported Title")
        thumbnail = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        views = data.get("viewCount", {}).get("short", "0 Views")
    except Exception as e:
        title, thumbnail, views = "Unsupported Title", YOUTUBE_IMG_URL, "Unknown"

    thumb_path = os.path.join(CACHE_DIR, f"temp_{videoid}.jpg")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(thumb_path, "wb") as f:
                        await f.write(await resp.read())
                else: return YOUTUBE_IMG_URL
    except: return YOUTUBE_IMG_URL

    try:
        # 1. PREMIUM LIGHT BLUE BACKGROUND
        # Ek naya light blue canvas banate hain
        bg = Image.new("RGBA", (1280, 720), (225, 245, 254, 255)) # Very light sky blue
        draw = ImageDraw.Draw(bg)
        
        # Adding a soft blue gradient/glow effect
        overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        o_draw = ImageDraw.Draw(overlay)
        o_draw.ellipse([-200, -200, 600, 600], fill=(187, 222, 251, 150)) # Top left glow
        o_draw.ellipse([800, 300, 1500, 900], fill=(129, 212, 250, 100)) # Bottom right glow
        bg = Image.alpha_composite(bg, overlay.filter(ImageFilter.GaussianBlur(80)))

        # 2. MAIN THUMBNAIL (Full Colorful & Rounded)
        img = Image.open(thumb_path).convert("RGBA")
        main_w, main_h = 850, 480
        img = ImageOps.fit(img, (main_w, main_h), method=Image.Resampling.LANCZOS)

        # Rounded Corner Mask
        mask = Image.new("L", (main_w, main_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, main_w, main_h), radius=40, fill=255)
        
        # White border for thumbnail
        border_size = 8
        border = Image.new("RGBA", (main_w + border_size*2, main_h + border_size*2), (255, 255, 255, 255))
        b_mask = Image.new("L", (main_w + border_size*2, main_h + border_size*2), 0)
        ImageDraw.Draw(b_mask).rounded_rectangle((0, 0, main_w + border_size*2, main_h + border_size*2), radius=45, fill=255)
        
        # Paste Border and Image
        bg.paste(border, ((1280 - main_w - border_size*2)//2, 62), b_mask)
        bg.paste(img, ((1280 - main_w)//2, 70), mask)

        # 3. TYPOGRAPHY (Fonts)
        try:
            # Note: Aap fonts folder check karein, agar font.ttf nahi hai toh default load hoga
            font_title = ImageFont.truetype("NEOMUSIC/assets/thumb/font.ttf", 42)
            font_info = ImageFont.truetype("NEOMUSIC/assets/thumb/font.ttf", 26)
        except:
            font_title = ImageFont.load_default()
            font_info = ImageFont.load_default()

        # Title (Centered)
        clean_title = truncate(title, 50)
        title_w = draw.textlength(clean_title, font=font_title)
        draw.text(((1280 - title_w)//2, 575), clean_title, fill=(38, 50, 56), font=font_title)

        # Info (Views & Bot Username)
        info_text = f"Views: {views}  |  Playing on @{app.username}"
        info_w = draw.textlength(info_text, font=font_info)
        draw.text(((1280 - info_w)//2, 635), info_text, fill=(84, 110, 122), font=font_info)

        # 4. SLEEK PROGRESS BAR
        bar_w, bar_h = 600, 8
        bar_x = (1280 - bar_w) // 2
        bar_y = 680
        # Background bar
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=4, fill=(207, 216, 220))
        # Active progress (Bright Blue)
        draw.rounded_rectangle((bar_x, bar_y, bar_x + 250, bar_y + bar_h), radius=4, fill=(3, 169, 244))

        # Cleanup & Save
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        final_bg = bg.convert("RGB")
        final_bg.save(cache_path, quality=95)
        return cache_path

    except Exception as e:
        logging.error(f"Thumbnail error: {e}")
        return YOUTUBE_IMG_URL

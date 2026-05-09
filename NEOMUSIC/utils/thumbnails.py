import logging
import aiohttp
from youtubesearchpython.__future__ import VideosSearch
from config import YOUTUBE_IMG_URL

logging.basicConfig(level=logging.ERROR)

# List of words to block
BANNED_KEYWORDS = ["drugs", "sex", "porn", "alcohol", "weed", "coke", "heroin"]

async def get_thumb(videoid: str) -> str:
    try:
        # Fetch video details from YouTube
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        results_data = await results.next()
        
        if not results_data["result"]:
            return YOUTUBE_IMG_URL

        data = results_data["result"][0]
        title = data.get("title", "").lower()
        
        # YouTube API se best quality thumbnail uthana (ye hamesha valid hota hai)
        thumbnails = data.get("thumbnails", [])
        if thumbnails:
            # Last thumbnail usually has the highest resolution provided by API
            thumbnail_url = thumbnails[-1].get("url", YOUTUBE_IMG_URL)
        else:
            thumbnail_url = YOUTUBE_IMG_URL

        # SAFETY FILTER LOGIC
        if any(word in title for word in BANNED_KEYWORDS):
            logging.info(f"Thumbnail blocked due to sensitive content: {title}")
            return YOUTUBE_IMG_URL

        # --- FIX: SAFE HIGH RES LOGIC ---
        # Sirf tabhi replace karein jab humein pata ho ki video standard HD hai
        # Par behtar ye hai ki hum API wala hi use karein taaki 400 error na aaye.
        # Agar aapko risk lena hai toh hqdefault use karein kyunki ye hamesha exist karta hai.
        
        if not thumbnail_url or not thumbnail_url.startswith("http"):
            return YOUTUBE_IMG_URL

        return thumbnail_url

    except Exception as e:
        logging.error(f"Error fetching filtered thumbnail: {e}")
        return YOUTUBE_IMG_URL

# Optional Helper: Thumbnail exist karta hai ya nahi check karne ke liye (Fast check)
async def is_valid_thumb(url: str) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=5) as resp:
                return resp.status == 200
    except:
        return False

import logging
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
        thumbnail_url = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)

        # SAFETY FILTER LOGIC
        # If any banned keyword is found in the video title
        if any(word in title for word in BANNED_KEYWORDS):
            logging.info(f"Thumbnail blocked due to sensitive content: {title}")
            return YOUTUBE_IMG_URL # Show default placeholder image

        # High Resolution Logic: Try to get the max resolution image
        if "hqdefault.jpg" in thumbnail_url or "mqdefault.jpg" in thumbnail_url:
            thumbnail_url = thumbnail_url.replace("hqdefault.jpg", "maxresdefault.jpg").replace("mqdefault.jpg", "maxresdefault.jpg")

        return thumbnail_url

    except Exception as e:
        logging.error(f"Error fetching filtered thumbnail: {e}")
        return YOUTUBE_IMG_URL

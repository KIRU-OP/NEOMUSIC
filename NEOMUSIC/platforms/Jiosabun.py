import aiohttp
from typing import Optional, List, Dict, Any

# API Configuration
JIOSAAVN_API = "https://jiosaavn-api.pashivam584.workers.dev"

async def jiosaavn_search(query: str) -> Optional[Dict[str, Any]]:
    """
    Search JioSaavn for a song. 
    Returns the first result dictionary or None if not found.
    """
    url = f"{JIOSAAVN_API}/api/search/songs"
    params = {"query": query, "page": 1, "limit": 1}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                
        # API response structure check
        results = data.get("data", {}).get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"Error in jiosaavn_search: {e}")
        return None


async def jiosaavn_song_details(song_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch full song details using the Song ID.
    Returns the song detail dictionary or None.
    """
    url = f"{JIOSAAVN_API}/api/songs/{song_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                
        results = data.get("data", [])
        return results[0] if results else None
    except Exception as e:
        print(f"Error in jiosaavn_song_details: {e}")
        return None


def jiosaavn_get_audio_url(song: Dict[str, Any]) -> Optional[str]:
    """
    Extract best available audio URL from the song dictionary.
    Priority Order: 320kbps → 160kbps → 96kbps → Any available.
    """
    download_urls = song.get("downloadUrl", [])
    if not download_urls or not isinstance(download_urls, list):
        return None

    # Preferred qualities in order
    qualities = ["320kbps", "160kbps", "96kbps", "48kbps"]
    
    # Create a quick mapping
    url_map = {item.get("quality"): item.get("url") for item in download_urls}
    
    for q in qualities:
        if q in url_map and url_map[q]:
            return url_map[q]
            
    # Fallback: Return the very last one (usually highest or lowest available)
    return download_urls[-1].get("url") if download_urls else None


def jiosaavn_duration_to_seconds(song: Dict[str, Any]) -> int:
    """
    Extract song duration in seconds.
    """
    try:
        # Some APIs return duration as string, some as int
        return int(song.get("duration", 0))
    except (ValueError, TypeError):
        return 0


def jiosaavn_get_image(song: Dict[str, Any]) -> Optional[str]:
    """
    Extract the highest resolution thumbnail (500x500).
    """
    images = song.get("image", [])
    if isinstance(images, list) and images:
        # Usually the last element is the highest quality (500x500)
        return images[-1].get("url")
    return None


# --- Example of how to use it (Async) ---
"""
async def main():
    song = await jiosaavn_search("Pehle Bhi Main")
    if song:
        title = song.get("name")
        audio = jiosaavn_get_audio_url(song)
        duration = jiosaavn_duration_to_seconds(song)
        image = jiosaavn_get_image(song)
        
        print(f"Song: {title}\nDuration: {duration}s\nURL: {audio}\nImage: {image}")
"""

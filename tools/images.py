# tools/images.py
import os
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

async def get_images(location: str) -> str:
    """Get accurate images based on user's exact query - simple and direct."""
    
    if not UNSPLASH_ACCESS_KEY:
        return "❌ Real-time image data unavailable. Please check API configuration."

    # Use exact user query for search - no modifications
    search_query = location.strip()
    
    url = "https://api.unsplash.com/search/photos"
    headers = {
        "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}",
        "Accept-Version": "v1"
    }
    
    params = {
        "query": search_query,
        "per_page": 8,
        "order_by": "relevant",
        "orientation": "landscape"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=15) as response:
                if response.status == 401:
                    return "❌ Image service authentication failed. Please check API key."
                elif response.status == 403:
                    return "❌ Image service rate limit exceeded. Please try again later."
                elif response.status != 200:
                    return f"❌ Image service temporarily unavailable (Status: {response.status})"

                data = await response.json()
                results = data.get("results", [])
                
                if not results:
                    # Try with simplified search
                    words = search_query.split()
                    if len(words) > 1:
                        fallback_query = words[-1]  # Use last word only
                        params["query"] = fallback_query
                        
                        async with session.get(url, headers=headers, params=params, timeout=15) as retry_response:
                            if retry_response.status == 200:
                                retry_data = await retry_response.json()
                                results = retry_data.get("results", [])

                if not results:
                    return f"❌ No images found for '{location}'. Try a different or more specific location name."

                # Format results with hidden links
                images = []
                hidden_phrases = ["View Here", "See Image", "Check Photo", "Look Here", "View Picture", "See Here"]
                
                for i, img in enumerate(results[:6]):
                    photographer = img["user"]["name"]
                    description = img.get("alt_description", f"{search_query}")
                    image_url = img["urls"]["regular"]
                    
                    # Keep original description or create simple one
                    if not description or len(description) < 5:
                        description = f"Beautiful {search_query}"
                    
                    if len(description) > 80:
                        description = description[:77] + "..."
                    
                    # Capitalize first letter
                    description = description[0].upper() + description[1:] if description else f"{search_query} view"
                    
                    hidden_phrase = hidden_phrases[i % len(hidden_phrases)]
                    
                    images.append(f"📸 **{description}**\n   👤 By: {photographer}\n   🔗 [{hidden_phrase}]({image_url})")

                result = f"📷 **Images for '{location}':**\n\n"
                result += "\n\n".join(images)
                result += f"\n\n💡 **Tip:** Click the links above to view high-quality images!"

                return result

    except asyncio.TimeoutError:
        return f"❌ Image service timeout for '{location}'. Please try again."
    except Exception as e:
        return f"❌ Image service error: {str(e)}"

if __name__ == "__main__":
    location = input("Enter location: ")
    print(asyncio.run(get_images(location)))
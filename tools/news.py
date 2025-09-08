# tools/news.py
import os
import aiohttp
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

async def get_news(location: str) -> str:
    """Get recent travel and tourism news for the specified location - simple and accurate."""
    
    if not NEWS_API_KEY:
        return "❌ Real-time news data unavailable. Please check API configuration."

    # Simple search query focused on location + travel
    query = f'{location} AND (travel OR tourism OR tourist OR hotel OR attraction OR festival OR destination)'
    
    url = "https://newsapi.org/v2/everything"
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    params = {
        "q": query,
        "from": from_date,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 20
    }
    
    headers = {"X-API-Key": NEWS_API_KEY}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params, timeout=30) as response:
            if response.status != 200:
                return f"❌ Unable to fetch news data. Status: {response.status}"

            data = await response.json()
            articles = data.get("articles", [])

            if not articles:
                # Try simpler search
                simple_params = params.copy()
                simple_params["q"] = f'{location} travel'
                
                async with session.get(url, headers=headers, params=simple_params) as retry_response:
                    if retry_response.status == 200:
                        retry_data = await retry_response.json()
                        articles = retry_data.get("articles", [])

            if not articles:
                return f"❌ No recent news found for {location}. Try checking local tourism websites."

            # Filter for location relevance
            location_articles = []
            location_lower = location.lower()
            
            for article in articles:
                title = article.get("title", "").lower()
                description = (article.get("description") or "").lower()
                
                if location_lower in title or location_lower in description:
                    location_articles.append(article)

            if not location_articles:
                location_articles = articles[:6]  # Fallback to general results

            # Format results
            result = f"📰 Latest News for {location.title()}:\n\n"
            
            for i, article in enumerate(location_articles[:6], 1):
                title = article.get("title", "No title")
                source = article.get("source", {}).get("name", "Unknown")
                published = article.get("publishedAt", "")
                url_link = article.get("url", "")
                
                # Clean title
                if len(title) > 80:
                    title = title[:77] + "..."
                
                # Format date
                if published:
                    pub_date = datetime.fromisoformat(published.replace("Z", "+00:00")).strftime("%b %d")
                else:
                    pub_date = "Recent"

                # Simple emoji selection
                title_lower = title.lower()
                if any(word in title_lower for word in ["hotel", "resort"]):
                    emoji = "🏨"
                elif any(word in title_lower for word in ["temple", "heritage", "festival"]):
                    emoji = "🏛️"
                elif any(word in title_lower for word in ["food", "restaurant"]):
                    emoji = "🍛"
                elif any(word in title_lower for word in ["airport", "flight"]):
                    emoji = "✈️"
                else:
                    emoji = "📰"

                result += f"{emoji} {title}\n"
                result += f"   📅 {pub_date} | 🏢 {source}\n"
                result += f"   🔗 {url_link}\n\n"

            result += f"💡 Stay updated with the latest happenings in {location}!"
            return result


# ----------------- Run Individually -----------------
if __name__ == "__main__":
    location = input("Enter location for news: ").strip()
    if location:
        output = asyncio.run(get_news(location))
        print("\n" + output)
    else:
        print("❌ Please enter a valid location.")

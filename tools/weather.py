import os
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

async def get_weather(location: str) -> str:
    """Get current weather data for Indian travelers using OpenWeatherMap API."""
    
    if not OPENWEATHER_API_KEY:
        return "❌ Weather service unavailable - API key not configured"

    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {"q": location, "appid": OPENWEATHER_API_KEY, "units": "metric"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 404:
                return f"❌ Location '{location}' not found. Check spelling and try again."
            elif response.status == 401:
                return "❌ Weather service authentication failed"
            elif response.status != 200:
                return f"❌ Weather service error: {response.status}"

            data = await response.json()

            if data.get("cod") != 200:
                return f"❌ Weather data unavailable for '{location}'"

            # Extract weather data
            city = data["name"]
            country = data["sys"]["country"]
            temp = round(data["main"]["temp"], 1)
            weather_desc = data["weather"][0]["description"].title()
            feels_like = round(data["main"]["feels_like"], 1)
            humidity = data["main"]["humidity"]
            wind_speed = data.get("wind", {}).get("speed", 0)

            # Travel advice for Indian travelers
            travel_advice = ""
            if temp > 35:
                travel_advice = "\n🔥 **Travel Tip:** Very hot! Carry water, wear sunscreen, avoid midday travel."
            elif temp < 10:
                travel_advice = "\n🧥 **Travel Tip:** Cold weather! Pack warm clothes and layers."
            elif humidity > 80:
                travel_advice = "\n💧 **Travel Tip:** High humidity! Light, breathable cotton clothing recommended."
            elif wind_speed > 10:
                travel_advice = "\n💨 **Travel Tip:** Windy conditions! Secure loose items and be cautious outdoors."

            result = f"🌍 **Live Weather in {city}, {country}:**\n\n"
            result += f"🌡️ **Temperature:** {temp}°C (Feels like {feels_like}°C)\n"
            result += f"☁️ **Condition:** {weather_desc}\n"
            result += f"💧 **Humidity:** {humidity}%\n"
            result += f"💨 **Wind Speed:** {wind_speed} m/s"
            result += travel_advice
            result += f"\n\n🇮🇳 **For Indian Travelers:** Perfect weather data to plan your trip timing!"

            return result

if __name__ == "__main__":
    location = input("Enter city name: ")
    print(asyncio.run(get_weather(location)))
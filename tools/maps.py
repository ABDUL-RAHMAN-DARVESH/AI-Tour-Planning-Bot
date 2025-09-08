# tools/maps.py
import os
import aiohttp
import re
import asyncio
from dotenv import load_dotenv

load_dotenv()
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY")

TAG_RE = re.compile(r"<[^>]+>")

async def _geocode(address: str, session: aiohttp.ClientSession, timeout: int = 10):
    """Return (lng, lat, formatted_address) or (None, error_message)."""
    
    if not OPENROUTESERVICE_API_KEY:
        return None, "❌ OpenRouteService API key required for location services."
    
    geocode_url = "https://api.openrouteservice.org/geocode/search"
    headers = {"Authorization": OPENROUTESERVICE_API_KEY}
    params = {"text": address, "size": 1}
    
    async with session.get(geocode_url, headers=headers, params=params, timeout=timeout) as resp:
        if resp.status != 200:
            return None, f"❌ Location service error: {resp.status}"
        
        data = await resp.json()

    if not data.get("features"):
        return None, f"❌ Location '{address}' not found. Try more specific name."

    feature = data["features"][0]
    coords = feature["geometry"]["coordinates"]
    formatted_address = feature["properties"].get("label", address)
    
    return (coords[0], coords[1], formatted_address), None

async def get_maps(origin: str, destination: str, mode: str = "driving") -> str:
    """Get directions and travel information for Indian travelers using OpenRouteService API only."""
    
    if not OPENROUTESERVICE_API_KEY:
        return "❌ Real-time route data unavailable. Please check API configuration."

    mode_map = {
        "driving": "driving-car",
        "walking": "foot-walking", 
        "bicycling": "cycling-regular",
        "cycling": "cycling-regular",
        "transit": "driving-car"
    }
    
    profile = mode_map.get(mode.lower(), "driving-car")
    if mode.lower() not in mode_map:
        return "❌ Unsupported mode. Use: driving, walking, bicycling."

    async with aiohttp.ClientSession() as session:
        # Geocode origin & destination
        origin_geo, err = await _geocode(origin, session)
        if err:
            return err
        dest_geo, err = await _geocode(destination, session)
        if err:
            return err

        # Get directions
        directions_url = f"https://api.openrouteservice.org/v2/directions/{profile}"
        headers = {
            "Authorization": OPENROUTESERVICE_API_KEY,
            "Content-Type": "application/json"
        }
        body = {
            "coordinates": [[origin_geo[0], origin_geo[1]], [dest_geo[0], dest_geo[1]]],
            "format": "json",
            "instructions": True,
            "units": "m"
        }

        async with session.post(directions_url, json=body, headers=headers, timeout=20) as resp:
            if resp.status != 200:
                return f"❌ Unable to get route data. Status: {resp.status}"
            
            data = await resp.json()

        if "routes" not in data or not data["routes"]:
            return f"❌ No route found from {origin} to {destination}."

        # Parse route
        route = data["routes"][0]
        summary = route.get("summary", {})
        
        distance_km = round(summary.get("distance", 0) / 1000, 1)
        duration_min = round(summary.get("duration", 0) / 60)
        duration_text = f"{duration_min // 60}h {duration_min % 60}m" if duration_min >= 60 else f"{duration_min}m"
        
        start_address = origin_geo[2] if origin_geo else origin
        end_address = dest_geo[2] if dest_geo else destination

        # Get main steps
        steps_out = []
        segments = route.get("segments", [])
        for segment in segments[:1]:
            steps = segment.get("steps", [])
            for step in steps[:5]:
                instruction = step.get("instruction", "Continue")
                instruction = TAG_RE.sub("", instruction)
                instruction = " ".join(instruction.split())
                steps_out.append(f"{len(steps_out)+1}. {instruction}")

        google_maps_link = f"https://www.google.com/maps/dir/{origin.replace(' ', '+')}/{destination.replace(' ', '+')}"

        result = f"🗺️ Route from {start_address} to {end_address}:\n\n"
        result += f"📏 Distance: {distance_km} km\n"
        result += f"⏱️ Duration: {duration_text} ({mode})\n\n"
        if steps_out:
            result += "🛣️ Main directions:\n" + "\n".join(steps_out) + "\n\n"
        result += f"🔗 Full directions: {google_maps_link}\n\n"
        result += f"💡 Plan your journey considering Indian traffic conditions!"

        return result


# ----------------- Run Individually -----------------
if __name__ == "__main__":
    origin = input("Enter origin: ").strip()
    destination = input("Enter destination: ").strip()
    mode = input("Enter mode (driving/walking/bicycling): ").strip() or "driving"

    if origin and destination:
        output = asyncio.run(get_maps(origin, destination, mode))
        print("\n" + output)
    else:
        print("❌ Please provide both origin and destination.")

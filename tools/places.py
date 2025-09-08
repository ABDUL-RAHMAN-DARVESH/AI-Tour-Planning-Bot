import os
import aiohttp
import asyncio
from dotenv import load_dotenv
from typing import Optional, Tuple, List, Dict

load_dotenv()
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY")

# -----------------------------------------------------------------------------
# Geocode: Nominatim
# -----------------------------------------------------------------------------
async def geocode_location(location: str) -> Optional[Tuple[float, float, Tuple[float, float, float, float]]]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": location, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "IndianTravelApp/1.0", "Accept-Language": "en"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if not data:
                return None
            item = data[0]
            lat = float(item.get("lat"))
            lon = float(item.get("lon"))
            bb = item.get("boundingbox", [])
            if len(bb) == 4:
                # Nominatim boundingbox: [south, north, west, east]
                south = float(bb[0]); north = float(bb[1]); west = float(bb[2]); east = float(bb[3])
                return lat, lon, (south, west, north, east)
            else:
                d = 0.03
                return lat, lon, (lat - d, lon - d, lat + d, lon + d)

# -----------------------------------------------------------------------------
# Overpass query builder: include many tourism-related tags
# -----------------------------------------------------------------------------
def build_overpass_queries(bbox: Tuple[float, float, float, float], place_type: str) -> str:
    south, west, north, east = bbox
    tag_groups = []
    if place_type == "tourism":
        tag_groups = [
            'node["tourism"="attraction"]', 'way["tourism"="attraction"]', 'relation["tourism"="attraction"]',
            'node["tourism"="viewpoint"]', 'way["tourism"="viewpoint"]', 'relation["tourism"="viewpoint"]',
            'node["tourism"="museum"]', 'node["tourism"="gallery"]',
            'node["historic"]', 'node["leisure"="park"]', 'node["natural"="peak"]',
            'node["natural"="waterfall"]', 'node["amenity"="theatre"]', 'node["tourism"="information"]',
            'node["place"="locality"]',
        ]
    elif place_type == "restaurant":
        tag_groups = ['node["amenity"="restaurant"]', 'way["amenity"="restaurant"]', 'relation["amenity"="restaurant"]']
    elif place_type == "hotel":
        tag_groups = ['node["tourism"="hotel"]', 'way["tourism"="hotel"]', 'relation["tourism"="hotel"]']
    else:
        tag_groups = ['node["name"]', 'way["name"]', 'relation["name"]']

    queries = [f'{tg}({south},{west},{north},{east});' for tg in tag_groups]
    return "[out:json][timeout:25];(" + "".join(queries) + ");out center;"

# -----------------------------------------------------------------------------
# Query Overpass and parse results
# -----------------------------------------------------------------------------
async def overpass_search(bbox: Tuple[float, float, float, float], place_type: str, max_results: int = 20) -> Optional[List[Dict]]:
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = build_overpass_queries(bbox, place_type)
    async with aiohttp.ClientSession() as session:
        async with session.post(overpass_url, data=query, timeout=30) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            elements = data.get("elements", [])
            results = []
            seen = set()
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue
                key = name.strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                if el.get("type") == "node":
                    lat = el.get("lat"); lon = el.get("lon")
                else:
                    center = el.get("center") or {}
                    lat = center.get("lat"); lon = center.get("lon")
                category = tags.get("tourism") or tags.get("amenity") or tags.get("historic") or tags.get("leisure") or tags.get("natural") or "Place"
                results.append({"name": name.strip(), "category": category, "lat": lat, "lon": lon, "tags": tags})
                if len(results) >= max_results:
                    break
            return results if results else None

# -----------------------------------------------------------------------------
# Nominatim fallback
# -----------------------------------------------------------------------------
async def nominatim_search_named(location: str, place_type: str, max_results: int = 12) -> Optional[List[Dict]]:
    url = "https://nominatim.openstreetmap.org/search"
    q = f"{place_type} {location}"
    params = {"q": q, "format": "json", "limit": max_results, "addressdetails": 1, "extratags": 1, "namedetails": 1}
    headers = {"User-Agent": "IndianTravelApp/1.0", "Accept-Language": "en"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=12) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            results = []
            seen = set()
            for item in data:
                namedetails = item.get("namedetails") or {}
                name = namedetails.get("name") or item.get("display_name", "").split(",")[0].strip()
                if not name:
                    continue
                key = name.strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                lat = float(item.get("lat")) if item.get("lat") else None
                lon = float(item.get("lon")) if item.get("lon") else None
                category = item.get("type") or item.get("class") or "Place"
                importance = float(item.get("importance") or 0)
                results.append({"name": name.strip(), "category": category, "lat": lat, "lon": lon, "importance": importance, "raw": item})
            results.sort(key=lambda r: r.get("importance", 0), reverse=True)
            return results if results else None

# -----------------------------------------------------------------------------
# Main function
# -----------------------------------------------------------------------------
async def get_places(location: str, place_type: str = "tourism") -> str:
    if not location or not location.strip():
        return "❌ Provide a valid location."

    geo = await geocode_location(location)
    places_result = None

    if geo:
        lat, lon, bbox = geo
        scales = [1.0, 1.8, 3.5]
        base_south, base_west, base_north, base_east = bbox
        for scale in scales:
            mid_lat = (base_south + base_north) / 2
            mid_lon = (base_west + base_east) / 2
            half_lat = (base_north - base_south) / 2 * scale
            half_lon = (base_east - base_west) / 2 * scale
            trial_bbox = (mid_lat - half_lat, mid_lon - half_lon, mid_lat + half_lat, mid_lon + half_lon)
            results = await overpass_search(trial_bbox, place_type, max_results=30)
            if results and len(results) >= 3:
                places_result = results
                break
            if results and len(results) > 0 and not places_result:
                places_result = results

    if not places_result or len(places_result) < 3:
        nomi = await nominatim_search_named(location, place_type, max_results=20)
        if nomi:
            normalized = [{
                "name": item["name"],
                "category": item.get("category") or item.get("raw", {}).get("type"),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "tags": item.get("raw", {}).get("extratags", {})
            } for item in nomi]
            combined, seen = [], set()
            if places_result:
                for p in places_result:
                    k = p.get("name", "").strip().lower()
                    seen.add(k); combined.append(p)
            for n in normalized:
                k = n.get("name", "").strip().lower()
                if k not in seen:
                    seen.add(k); combined.append(n)
            places_result = combined if combined else places_result

    if not places_result:
        return f"❌ No {place_type} places found for '{location}'. Try a larger nearby city or check spelling."

    out_lines = [f"🏛️ **{place_type.replace('_',' ').title()} in {location.title()}:**", ""]
    for idx, p in enumerate(places_result[:10], 1):
        name = p.get("name") or "Unknown"
        cat = p.get("category") or ""
        lat, lon = p.get("lat"), p.get("lon")
        out_lines.append(f"📍 **{name}**" + (f" ({cat.title()})" if cat and cat.lower() not in (name.lower(), "place") else ""))
        if lat and lon:
            out_lines.append(f"   📌 Coordinates: {lat}, {lon}")
        if place_type == "tourism":
            out_lines.append("   🎫 Entry: Check current rates at entrance or official site.")
        elif place_type == "restaurant":
            out_lines.append("   💰 Cost: Check menu or call the restaurant.")
        elif place_type == "hotel":
            out_lines.append("   🏨 Rates: Check booking platforms for live rates.")
        out_lines.append("")
    out_lines.append("💡 **Tip:** Results prefer named OSM features. For small towns, try a nearby larger city (e.g., 'Kochi').")
    return "\n".join(out_lines)

# -----------------------------------------------------------------------------
# Run Individually
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    location = input("Enter location: ").strip()
    place_type = input("Enter place type (tourism/restaurant/hotel): ").strip().lower() or "tourism"
    if location:
        print("\nFetching data, please wait...\n")
        output = asyncio.run(get_places(location, place_type))
        print(output)
    else:
        print("❌ Please provide a valid location.")
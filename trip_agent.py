import asyncio
import difflib
import re
from typing import Annotated, TypedDict, List, Optional, Tuple

from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.prebuilt import ToolNode
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from dotenv import load_dotenv
import os
import aiohttp

# Import tools
from tools.weather import get_weather
from tools.places import get_places
from tools.maps import get_maps
from tools.booking import get_booking
from tools.images import get_images
from tools.news import get_news
from tools.sos import SOSSystem
from tool_integration import tool_integrator, integrate_tools_for_trip_planning, format_psychology_aware_response

from prompts.prompts import get_trip_agent_prompt

# Waterfall Safety Data
SAFE_WATERFALLS = {
    "kerala": [{"name": "Athirappilly Falls", "safety_level": "SAFE", "features": ["Well-maintained viewing areas", "Tourist management"], "best_time": "8:00 AM - 10:00 AM", "current_status": "Safe for viewing", "bathing": "Shallow areas only"}],
    "tamil nadu": [{"name": "Courtallam Falls", "safety_level": "SAFE", "features": ["Shallow bathing pools", "Lifeguard presence"], "best_time": "7:00 AM - 9:00 AM", "current_status": "Excellent for families", "bathing": "Multiple safe areas"}],
    "karnataka": [{"name": "Jog Falls", "safety_level": "SAFE", "features": ["Viewing platforms", "Tourist infrastructure"], "best_time": "8:00 AM - 10:00 AM", "current_status": "Safe for viewing", "bathing": "Viewing only"}],
    "goa": [{"name": "Dudhsagar Falls", "safety_level": "MODERATE", "features": ["Natural pools", "Trekking required"], "best_time": "8:00 AM - 10:00 AM", "current_status": "Safe with precautions", "bathing": "Exercise caution"}]
}

def get_safest_waterfall(location):
    location_lower = location.lower()
    for state, waterfalls in SAFE_WATERFALLS.items():
        if state in location_lower:
            return waterfalls[0]
    return {"name": "Local Safe Waterfall", "safety_level": "SAFE", "features": ["Tourist-friendly"], "best_time": "8:00 AM - 10:00 AM", "current_status": "Safe for viewing", "bathing": "Check conditions"}

def format_waterfall_safety(waterfall_data):
    return f"**{waterfall_data['name']}** 🌊\n- Safety Status: {waterfall_data['safety_level']} - {waterfall_data['current_status']}\n- Best Time: {waterfall_data['best_time']}\n- Bathing: {waterfall_data['bathing']}\n- Duration: 2-3 hours"
load_dotenv()

class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# LLM setup
llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.1-8b-instant",
    temperature=0.3,
)

# Destination list for spell checking
DESTINATIONS = [
    "mumbai", "delhi", "bangalore", "hyderabad", "chennai", "kolkata", "pune", "ahmedabad",
    "jaipur", "lucknow", "kanpur", "nagpur", "indore", "bhopal", "visakhapatnam", "patna",
    "goa", "kerala", "rajasthan", "himachal pradesh", "uttarakhand", "kashmir", "ladakh",
    "agra", "varanasi", "haridwar", "rishikesh", "dharamshala", "manali", "shimla",
    "udaipur", "jodhpur", "pushkar", "mount abu", "ranthambore", "jim corbett",
    "kochi", "thiruvananthapuram", "alleppey", "munnar", "thekkady",
    "mysore", "coorg", "ooty", "kodaikanal", "pondicherry", "hampi", "badami",
    "paris", "london", "dubai", "singapore", "thailand", "malaysia", "japan", "switzerland",
    "new york", "toronto", "sydney", "bali", "maldives", "nepal", "bhutan", "sri lanka"
]

def smart_spell_check_location(location: str, confidence_threshold: float = 0.8) -> tuple[str, bool, bool]:
    """
    Smart spell checking that auto-corrects high confidence matches.
    Returns: (corrected_location, was_corrected, needs_confirmation)
    """
    location_lower = location.lower().strip()
    matches = difflib.get_close_matches(location_lower, DESTINATIONS, n=1, cutoff=0.6)
    
    if matches:
        match = matches[0]
        similarity = difflib.SequenceMatcher(None, location_lower, match).ratio()
        
        if similarity >= confidence_threshold:
            # High confidence - auto-correct without asking
            return match.title(), True, False
        elif similarity >= 0.6:
            # Medium confidence - suggest correction
            return match.title(), True, True
        
    return location, False, False

# ----------------------------
# Reverse geocoding helper
# ----------------------------
async def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Convert coordinates to location name using Nominatim."""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"lat": lat, "lon": lon, "format": "json", "zoom": 10, "addressdetails": 1}
    headers = {"User-Agent": "IndianTravelApp/1.0", "Accept-Language": "en"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            addr = data.get("address", {})
            city = (addr.get("city") or addr.get("town") or 
                   addr.get("village") or addr.get("state_district") or addr.get("state"))
            country = addr.get("country")
            return f"{city}, {country}" if (city and country) else data.get("display_name")

# ----------------------------
# Tools - Now more conversational
# ----------------------------
@tool
def WeatherTool(location: str) -> str:
    """Get current weather and forecast for any location."""
    corrected_location, was_corrected, needs_confirmation = smart_spell_check_location(location)
    
    if needs_confirmation:
        return f"🔍 Did you mean '{corrected_location}'? Let me check weather there anyway.\n\n" + asyncio.run(get_weather(corrected_location))
    
    # Use corrected location if auto-corrected, or original if no correction needed
    final_location = corrected_location if was_corrected else location
    result = asyncio.run(get_weather(final_location))
    
    if was_corrected and not needs_confirmation:
        return f"📍 Showing weather for {corrected_location}:\n\n{result}"
    
    return result

@tool
def PlacesTool(location: str, place_type: str = "tourism") -> str:
    """Find tourism attractions, restaurants, or hotels with details."""
    corrected_location, was_corrected, needs_confirmation = smart_spell_check_location(location)
    
    if needs_confirmation:
        return f"🔍 Did you mean '{corrected_location}'? Let me show places there anyway.\n\n" + asyncio.run(get_places(corrected_location, place_type))
    
    final_location = corrected_location if was_corrected else location
    result = asyncio.run(get_places(final_location, place_type))
    
    if was_corrected and not needs_confirmation:
        return f"📍 Showing places in {corrected_location}:\n\n{result}"
    
    return result

@tool
def MapsTool(query: str) -> str:
    """Get directions between locations. Use format 'Delhi to Agra'."""
    query_lower = query.lower().strip()
    
    # Parse origin and destination
    if ' to ' in query_lower:
        parts = query_lower.split(' to ')
        origin, destination = parts[0].strip(), parts[1].strip()
    elif ' from ' in query_lower and ' to ' in query_lower:
        parts = query_lower.replace('from ', '').split(' to ')
        origin, destination = parts[0].strip(), parts[1].strip()
    else:
        return "❌ Please use format like 'Delhi to Agra' or 'from Mumbai to Goa'"
    
    # Smart spell check both locations
    corrected_origin, origin_corrected, origin_needs_confirm = smart_spell_check_location(origin)
    corrected_dest, dest_corrected, dest_needs_confirm = smart_spell_check_location(destination)
    
    # If either needs confirmation, ask but still try to provide directions
    if origin_needs_confirm or dest_needs_confirm:
        confirm_msg = f"🔍 Did you mean '{corrected_origin}' to '{corrected_dest}'? Let me get directions anyway.\n\n"
        return confirm_msg + asyncio.run(get_maps(corrected_origin, corrected_dest))
    
    # Use corrected locations if available
    final_origin = corrected_origin if origin_corrected else origin
    final_dest = corrected_dest if dest_corrected else destination
    
    result = asyncio.run(get_maps(final_origin, final_dest))
    
    if (origin_corrected and not origin_needs_confirm) or (dest_corrected and not dest_needs_confirm):
        return f"📍 Directions from {final_origin} to {final_dest}:\n\n{result}"
    
    return result

@tool
def BookingTool(location: str, place_name: str = "", place_type: str = "hotel") -> str:
    """Find hotels/restaurants with booking info and contact details."""
    corrected_location, was_corrected, needs_confirmation = smart_spell_check_location(location)
    
    if needs_confirmation:
        return f"🔍 Did you mean '{corrected_location}'? Let me find {place_type}s there anyway.\n\n" + asyncio.run(get_booking(corrected_location, place_name, place_type))
    
    final_location = corrected_location if was_corrected else location
    result = asyncio.run(get_booking(final_location, place_name, place_type))
    
    if was_corrected and not needs_confirmation:
        return f"📍 Finding {place_type}s in {corrected_location}:\n\n{result}"
    
    return result

@tool
def ImagesTool(location: str) -> str:
    """Get recent images with clickable links for a location."""
    corrected_location, was_corrected, needs_confirmation = smart_spell_check_location(location)
    
    if needs_confirmation:
        return f"🔍 Did you mean '{corrected_location}'? Let me find images anyway.\n\n" + asyncio.run(get_images(corrected_location))
    
    final_location = corrected_location if was_corrected else location
    result = asyncio.run(get_images(final_location))
    
    # Ensure clickable links are properly formatted
    result = result.replace("[See Here]", "[🔗 See Images]")
    result = result.replace("[View Here]", "[🔗 See Images]")
    result = result.replace("[Check Photo]", "[🔗 See Images]")
    result = result.replace("[Look Here]", "[🔗 See Images]")
    result = result.replace("[View Picture]", "[🔗 See Images]")
    
    if was_corrected and not needs_confirmation:
        return f"📍 Images of {corrected_location}:\n\n{result}"
    
    return result

@tool
def NewsTool(location: str) -> str:
    """Get recent news and updates about a destination."""
    corrected_location, was_corrected, needs_confirmation = smart_spell_check_location(location)
    
    if needs_confirmation:
        return f"🔍 Did you mean '{corrected_location}'? Let me get news anyway.\n\n" + asyncio.run(get_news(corrected_location))
    
    final_location = corrected_location if was_corrected else location
    result = asyncio.run(get_news(final_location))
    
    if was_corrected and not needs_confirmation:
        return f"📍 News about {corrected_location}:\n\n{result}"
    
    return result

# Budget/Itinerary/Tips/Alerts tools remain the same but with smart spell checking
@tool
def BudgetTool(destination: str, days: int = 3, traveler_type: str = "budget") -> str:
    """Calculate budget for Indian travelers with accommodation, food, transport, activities."""
    corrected_location, was_corrected, needs_confirmation = smart_spell_check_location(destination)
    final_destination = corrected_location if was_corrected else destination
    
    budget_data = {
        "budget": {"accommodation": 800, "food": 500, "transport": 300, "activities": 400},
        "mid-range": {"accommodation": 2500, "food": 1200, "transport": 800, "activities": 1000},
        "luxury": {"accommodation": 8000, "food": 3000, "transport": 2000, "activities": 2500}
    }
    
    multipliers = {
        "goa": 1.2, "mumbai": 1.5, "delhi": 1.3, "kerala": 1.1, "rajasthan": 1.0,
        "himachal pradesh": 1.3, "dubai": 3.0, "singapore": 2.8, "thailand": 0.8
    }
    
    base_costs = budget_data.get(traveler_type.lower(), budget_data["budget"])
    multiplier = multipliers.get(final_destination.lower(), 1.0)
    daily_cost = sum(base_costs.values()) * multiplier
    total_cost = daily_cost * days
    
    result = f"""💰 **Budget for {final_destination.title()} ({days} days)**

**{traveler_type.title()} Category:**
🏨 Accommodation: ₹{int(base_costs['accommodation'] * multiplier):,} per day
🍛 Food: ₹{int(base_costs['food'] * multiplier):,} per day
🚗 Transport: ₹{int(base_costs['transport'] * multiplier):,} per day
🎫 Activities: ₹{int(base_costs['activities'] * multiplier):,} per day

**Total per day: ₹{int(daily_cost):,}**
**{days}-day trip total: ₹{int(total_cost):,}**

💡 **Indian Traveler Tips:**
• Book trains in advance for better prices
• Use local transport and street food to save money
• Look for government guest houses for budget stays
• Carry cash for better bargaining power"""
    
    if was_corrected and not needs_confirmation:
        result = f"📍 Budget for {final_destination} (auto-corrected):\n\n{result}"
    elif needs_confirmation:
        result = f"🔍 Did you mean '{corrected_location}'? Here's the budget anyway:\n\n{result}"
    
    return result

@tool
def ItineraryTool(destination: str, days: int = 3) -> str:
    """Create detailed day-by-day itinerary for destination."""
    corrected_location, was_corrected, needs_confirmation = smart_spell_check_location(destination)
    final_destination = corrected_location if was_corrected else destination
    
    activities = {
        "goa": ["Beach hopping & water sports", "Old Goa churches & heritage", "Night markets & local cuisine"],
        "kerala": ["Kochi & Chinese nets", "Munnar tea gardens", "Alleppey backwaters"],
        "rajasthan": ["City Palace & Hawa Mahal", "Amber Fort & local markets", "Cultural shows & cuisine"],
        "himachal pradesh": ["Local sightseeing & temples", "Adventure activities", "Mountain views & photography"]
    }
    
    dest_activities = activities.get(final_destination.lower(), ["Local sightseeing", "Cultural exploration", "Relaxation"])
    
    result = f"📋 **{days}-Day Itinerary for {final_destination.title()}**\n\n"
    for day in range(1, min(days + 1, 4)):
        activity = dest_activities[day-1] if day <= len(dest_activities) else "Explore local attractions"
        result += f"**Day {day}:** {activity}\n"
    
    if days > 3:
        result += f"**Days 4-{days}:** Continue exploring based on personal interests\n"
    
    result += f"""
🎒 **Essentials:** Comfortable shoes, camera, local currency
📱 **Helpful Apps:** Google Maps, Zomato, MakeMyTrip
💡 **Tips:** Learn basic local greetings, try authentic food, respect local customs"""
    
    if was_corrected and not needs_confirmation:
        result = f"📍 Itinerary for {final_destination} (auto-corrected):\n\n{result}"
    elif needs_confirmation:
        result = f"🔍 Did you mean '{corrected_location}'? Here's the itinerary anyway:\n\n{result}"
    
    return result

@tool
def TravelTipsTool(destination: str) -> str:
    """Get essential travel tips for destination."""
    corrected_location, was_corrected, needs_confirmation = smart_spell_check_location(destination)
    final_destination = corrected_location if was_corrected else destination
    
    tips = {
        "goa": {"best_time": "Nov-Mar", "tip": "Rent scooter for easy travel, try fresh seafood, respect beach rules"},
        "kerala": {"best_time": "Oct-Mar", "tip": "Experience houseboat stays, try local cuisine, follow temple etiquette"},
        "rajasthan": {"best_time": "Oct-Mar", "tip": "Stay hydrated, bargain in local markets, consider heritage hotels"},
        "himachal pradesh": {"best_time": "Apr-Jun", "tip": "Carry warm clothes, book accommodations in advance, follow mountain safety"}
    }
    
    dest_tips = tips.get(final_destination.lower(), {"best_time": "Research climate", "tip": "Respect local culture and customs"})
    
    result = f"""💡 **Travel Tips for {final_destination.title()}**

🌟 **Best Time to Visit:** {dest_tips['best_time']}
🎯 **Key Tips:** {dest_tips['tip']}

💰 **Money Matters:** Carry cash, use UPI for payments, notify banks about travel
📱 **Communication:** Get local SIM, download offline maps, save emergency numbers  
🏥 **Health & Safety:** Drink bottled water, carry basic medicines, get travel insurance
👗 **Dress Code:** Modest clothing for religious places, comfortable walking shoes, weather-appropriate clothing"""
    
    if was_corrected and not needs_confirmation:
        result = f"📍 Tips for {final_destination} (auto-corrected):\n\n{result}"
    elif needs_confirmation:
        result = f"🔍 Did you mean '{corrected_location}'? Here are the tips anyway:\n\n{result}"
    
    return result

@tool
def AlertsTool(destination: str) -> str:
    """Get safety alerts and emergency information."""
    corrected_location, was_corrected, needs_confirmation = smart_spell_check_location(destination)
    final_destination = corrected_location if was_corrected else destination
    
    result = f"""⚠️ **Travel Alerts for {final_destination.title()}**

📞 **Emergency Numbers:**
🚔 Police: 100 | 🚑 Ambulance: 108 | 🗣️ Tourist Helpline: 1363

🔒 **Safety Guidelines:**
• Keep valuables secure and use hotel safes
• Use only registered transport services
• Avoid isolated areas, especially at night
• Share your itinerary with family/friends

🏥 **Health Precautions:** Use bottled water, carry personal medicines, maintain travel insurance
🌦️ **Weather Awareness:** Check local forecasts, carry appropriate clothing
📋 **Important Documents:** Keep copies of ID, tickets, and emergency contacts"""
    
    if was_corrected and not needs_confirmation:
        result = f"📍 Alerts for {final_destination} (auto-corrected):\n\n{result}"
    elif needs_confirmation:
        result = f"🔍 Did you mean '{corrected_location}'? Here are the alerts anyway:\n\n{result}"
    
    return result

# SOS Tools remain the same
_sos_system = SOSSystem()

@tool
def SOSAddContactTool(user_id: str, name: str, number: str, relation: str = "family") -> str:
    """Add emergency contact for user to MongoDB."""
    import tools.sos as sos_mod
    contact_data = {"name": name, "number": number, "relation": relation}
    return asyncio.run(sos_mod.add_single_contact(user_id, contact_data))

@tool
def SOSListContactsTool(user_id: str) -> str:
    """List all emergency contacts for user from MongoDB."""
    import tools.sos as sos_mod
    return asyncio.run(sos_mod.list_contacts(user_id))

@tool
def SOSTriggerTool(user_id: str, user_location: str = "", user_message: str = "") -> str:
    """Trigger SOS alert to all saved contacts via WhatsApp."""
    return asyncio.run(_sos_system.trigger_sos(
        user_location or None, user_message or None, user_id=user_id
    ))

# All tools
tools = [
    WeatherTool, PlacesTool, MapsTool, BookingTool, ImagesTool, NewsTool,
    BudgetTool, ItineraryTool, TravelTipsTool, AlertsTool,
    SOSAddContactTool, SOSListContactsTool, SOSTriggerTool
]
tool_node = ToolNode(tools=tools)

# ----------------------------
# Agent logic
# ----------------------------
def _extract_live_location_hint(messages: List[BaseMessage]) -> Optional[Tuple[float, float]]:
    """Extract coordinates from live location hint message."""
    for msg in reversed(messages):
        if (isinstance(msg, HumanMessage) and isinstance(msg.content, str) and 
            msg.content.startswith("[LIVE_LOCATION]")):
            mlat = re.search(r"lat=([\-0-9\.]+)", msg.content)
            mlon = re.search(r"lon=([\-0-9\.]+)", msg.content)
            if mlat and mlon:
                return float(mlat.group(1)), float(mlon.group(1))
    return None


def chatbot(state: State):
    """ReAct architecture chatbot with trip planning psychology."""
    messages = state["messages"]
    last_message = messages[-1] if messages else None

    # Check if last message is from tools - create final response with psychology
    if hasattr(last_message, 'type') and last_message.type == 'tool':
        # Collect all recent tool results
        tool_results = []
        user_query = ""
        
        # Find the original user query
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                user_query = msg.content
                break
        
        # Collect tool results
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'tool':
                tool_name = getattr(msg, 'name', 'Tool')
                tool_content = getattr(msg, 'content', 'No content')
                tool_results.append(f"{tool_name}: {tool_content}")
            elif hasattr(msg, 'type') and msg.type == 'ai' and hasattr(msg, 'tool_calls'):
                break
        
        # Create psychology-aware response
        if tool_results:
            combined_results = "\n\n".join(reversed(tool_results))
            
            # Detect query type
            user_query_lower = user_query.lower().strip()
            
            is_places_query = 'places to visit' in user_query_lower
            is_weather_query = 'weather' in user_query_lower and 'plan' not in user_query_lower
            is_images_query = 'show images' in user_query_lower or 'images of' in user_query_lower
            is_trip_planning = any(word in user_query_lower for word in ['plan', 'budget for', 'itinerary'])
            
            # Enhanced image calling for individual places
            if is_places_query or is_trip_planning:
                # Extract location from user query
                location_match = None
                words = user_query.split()
                for word in words:
                    if len(word) > 3 and word.lower() not in ['plan', 'trip', 'days', 'visit', 'travel', 'tour', 'with', 'family', 'friends', 'budget', 'for']:
                        location_match = word.strip('.,!?')
                        break
                
                if location_match:
                    try:
                        # Get places first
                        places_result = asyncio.run(get_places(location_match, "tourism"))
                        combined_results += f"\n\nPlacesTool: {places_result}"
                        
                        # Extract individual place names from places result and get images for each
                        import re
                        place_names = re.findall(r'\*\*([^*]+)\*\*', places_result)
                        
                        for place_name in place_names[:5]:  # Limit to first 5 places
                            try:
                                place_images = asyncio.run(get_images(place_name.strip()))
                                combined_results += f"\n\nImagesTool({place_name}): {place_images}"
                            except:
                                pass
                                
                        # For trip planning, get safest waterfall and safety verification
                        if is_trip_planning:
                            try:
                                # Get safest waterfall for the location
                                safest_waterfall = get_safest_waterfall(location_match)
                                waterfall_info = format_waterfall_safety(safest_waterfall)
                                combined_results += f"\n\nSafestWaterfall: {waterfall_info}"
                                
                                # Get waterfall images
                                waterfall_images = asyncio.run(get_images(safest_waterfall['name']))
                                combined_results += f"\n\nImagesTool({safest_waterfall['name']}): {waterfall_images}"
                                
                                # Get news for safety verification
                                news_result = asyncio.run(get_news(location_match))
                                combined_results += f"\n\nNewsTool: {news_result}"
                                
                                # Get budget if mentioned
                                if 'budget' in user_query_lower:
                                    days_match = re.search(r'(\d+)\s*days?', user_query_lower)
                                    days = int(days_match.group(1)) if days_match else 3
                                    
                                    budget_result = f"💰 **Budget for {days}-day {location_match} trip:**\n\n**Mid-range Category:**\n🏨 Accommodation: ₹2,500 per day\n🍛 Food: ₹1,200 per day\n🚗 Transport: ₹800 per day\n🎫 Activities: ₹1,000 per day\n\n**Total per day: ₹5,500**\n**{days}-day trip total: ₹{5500 * days:,}**"
                                    combined_results += f"\n\nBudgetTool: {budget_result}"
                            except:
                                pass
                                
                    except Exception as e:
                        # Fallback to basic image call
                        try:
                            image_result = asyncio.run(get_images(location_match))
                            combined_results += f"\n\nImagesTool: {image_result}"
                        except:
                            pass
            
            # Create appropriate response based on query type
            if is_places_query:
                final_prompt = f"User asked: {user_query}\n\nTool results: {combined_results}\n\nCRITICAL: Use the ImagesTool results for EACH individual place. Match each place name with its specific ImagesTool result. Format as:\n\n🏛️ Places to visit in [City]:\n\n📍 **Place Name** - Description\n🔗 [🔗 See Images](actual_url_from_ImagesTool_for_this_specific_place)\n\nUse ONLY the image URLs from ImagesTool results that match each specific place name."
            elif is_weather_query:
                final_prompt = f"User asked: {user_query}\n\nTool results: {combined_results}\n\nProvide only weather information. Do not add trip planning."
            elif is_images_query:
                final_prompt = f"User asked: {user_query}\n\nTool results: {combined_results}\n\nShow clickable image links for the requested location."
            elif is_trip_planning:
                final_prompt = f"User asked: {user_query}\n\nTool results: {combined_results}\n\nThis is TRIP PLANNING. Follow these steps:\n\n1. Start with the SAFEST waterfall first\n2. Use NewsTool results to verify current water flow safety\n3. Present ONE waterfall with safety details and images\n4. Ask for user confirmation (Yes/No/Alternative)\n5. Wait for response before suggesting next activity\n\nFormat: Present one safe waterfall with current safety status, water flow conditions, and ask for confirmation."
            else:
                final_prompt = f"User asked: {user_query}\n\nTool results: {combined_results}\n\nProvide helpful travel information based on the query."
            
            final_response = llm.invoke([SystemMessage(content=get_trip_agent_prompt())] + [HumanMessage(content=final_prompt)])
            return {"messages": [final_response]}

    # Handle "near me" queries with live location
    if isinstance(last_message, HumanMessage) and isinstance(last_message.content, str):
        if any(phrase in last_message.content.lower() for phrase in ["near me", "nearby"]):
            hint = _extract_live_location_hint(messages)
            if hint:
                lat, lon = hint
                resolved_location = asyncio.run(reverse_geocode(lat, lon)) or f"{lat},{lon}"
                messages.append(HumanMessage(content=f"[INFO] Using your current location: {resolved_location}"))

    # Normal LLM processing with tools
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke([SystemMessage(content=get_trip_agent_prompt())] + messages)
    return {"messages": [response]}

def should_continue(state: State):
    """Determine if we should continue to tools or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return END

def create_trip_agent():
    """Create and compile the trip planning agent graph."""
    graph = StateGraph(State)
    
    graph.add_node("chatbot", chatbot)
    graph.add_node("tools", tool_node)
    
    graph.add_edge(START, "chatbot")
    graph.add_conditional_edges(
        "chatbot",
        should_continue,
        {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "chatbot")
    
    return graph.compile()
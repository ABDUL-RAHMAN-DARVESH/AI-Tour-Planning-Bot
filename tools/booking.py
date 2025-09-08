import os
import aiohttp
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
RAPIDAPI_BASE_URL = os.getenv("RAPIDAPI_BASE_URL")

async def get_booking(location: str = None, place_type: str = None, budget_type: str = "all") -> str:
    """Interactive booking system for hotels, resorts, cottages with live pricing for Indian travelers."""
    
    # Step 1: Ask for location if not provided
    if not location:
        return "🏨 **Welcome to Hotel Booking Assistant!**\n\nPlease tell me your destination (e.g., 'Goa', 'Kerala', 'Manali'):"
    
    # Step 2: Ask for accommodation type if not provided
    if not place_type:
        return f"📍 **Destination:** {location.title()}\n\n🏨 **What type of accommodation are you looking for?**\n\n" + \
               "• **Hotel** - Standard hotels with modern amenities\n" + \
               "• **Resort** - Luxury resorts with recreational facilities\n" + \
               "• **Cottage** - Cozy cottages and homestays\n" + \
               "• **Villa** - Private villas and vacation homes\n\n" + \
               "Please specify: hotel, resort, cottage, or villa"
    
    # API config check
    if not all([RAPIDAPI_KEY, RAPIDAPI_HOST, RAPIDAPI_BASE_URL]):
        return "❌ API credentials not configured. Cannot fetch hotel data."
    
    checkin_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    checkout_date = (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%d")
    
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}

    # ✅ Budget ranges mapping
    budget_map = {
        "budget": (0, 3000),
        "average": (3000, 8000),
        "rich": (8000, 20000),
        "luxury": (20000, 100000),
        "all": None
    }
    
    search_params = {
        "dest_type": "city",
        "dest_id": location,   # ⚠️ This expects a city ID (not plain name) in Booking.com API
        "search_type": "CITY", 
        "arrival_date": checkin_date,
        "departure_date": checkout_date,
        "adults": 2,
        "room_qty": 1,
        "languagecode": "en-us",
        "currency_code": "INR"
    }

    # ✅ Apply budget filter if not "all"
    budget_choice = budget_map.get(budget_type.lower())
    if budget_choice:
        search_params["price_min"], search_params["price_max"] = budget_choice
    
    async with aiohttp.ClientSession() as session:
        search_url = f"{RAPIDAPI_BASE_URL}/api/v1/hotels/searchHotels"
        
        try:
            async with session.get(search_url, headers=headers, params=search_params, timeout=15) as response:
                if response.status == 404:
                    return f"❌ Location '{location}' not found via API."
                elif response.status == 401:
                    return "❌ API authentication failed - Invalid credentials."
                elif response.status == 429:
                    return "❌ API rate limit exceeded. Try again later."
                elif response.status != 200:
                    return f"❌ API error: Status {response.status}"
                
                search_data = await response.json()
                
                if not search_data.get("data") or not search_data["data"].get("hotels"):
                    return f"❌ No hotels found for '{location}' via API."
                
                # ✅ Success
                hotel_count = len(search_data['data']['hotels'])
                budget_info = f" (Budget: {budget_type.title()})" if budget_type.lower() != "all" else ""
                return f"✅ Found {hotel_count} {place_type.title()}s in {location.title()}{budget_info}!"
                
        except Exception as e:
            return f"❌ API connection failed: {str(e)}"


async def handle_booking_conversation(user_input: str, conversation_state: dict = None) -> tuple[str, dict]:
    """Handle interactive booking conversation with state management."""
    if not conversation_state:
        conversation_state = {"step": "location", "location": None, "place_type": None}
    
    if conversation_state["step"] == "location":
        conversation_state["location"] = user_input.strip()
        conversation_state["step"] = "place_type"
        response = await get_booking(conversation_state["location"])
        return response, conversation_state
    
    elif conversation_state["step"] == "place_type":
        place_type = user_input.strip().lower()
        if place_type in ["hotel", "resort", "cottage", "villa"]:
            conversation_state["place_type"] = place_type
            conversation_state["step"] = "complete"
            response = await get_booking(conversation_state["location"], place_type)
            return response, conversation_state
        else:
            response = "❌ Please choose from: hotel, resort, cottage, or villa"
            return response, conversation_state
    
    else:
        # Start new conversation
        conversation_state = {"step": "location", "location": None, "place_type": None}
        response = await get_booking()
        return response, conversation_state

def _get_fallback_booking(location: str, place_type: str, budget_type: str = "all") -> str:
    """Fallback booking information when API is unavailable - Booking.com only."""
    checkin_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    checkout_date = (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%d")
    
    # Budget ranges for filtering
    budget_ranges = {
        "budget": "&price=INR-0-3000",
        "average": "&price=INR-3000-8000", 
        "rich": "&price=INR-8000-20000",
        "luxury": "&price=INR-20000-100000",
        "all": ""
    }
    
    budget_filter = budget_ranges.get(budget_type.lower(), "")
    search_query = f"{place_type}+in+{location.replace(' ', '+')}"
    booking_url = f"https://www.booking.com/searchresults.html?ss={search_query}&checkin={checkin_date}&checkout={checkout_date}&group_adults=2&no_rooms=1&selected_currency=INR{budget_filter}"
    
    # Check why API is unavailable
    api_status = "❌ **API temporarily unavailable**"
    if not all([RAPIDAPI_KEY, RAPIDAPI_HOST, RAPIDAPI_BASE_URL]):
        api_status = "❌ **API credentials not configured**"
    
    result = f"🏨 **{place_type.title()}s in {location.title()}**\n\n{api_status} - Search directly on Booking.com:\n\n"
    result += f"📅 **Dates:** {checkin_date} to {checkout_date}\n\n"
    
    if budget_type != "all":
        result += f"💰 **Budget Filter:** {budget_type.title()} range applied\n\n"
    
    result += f"📍 **Search {place_type.title()}s in {location.title()}**\n"
    result += f"🔗 [Book Here]({booking_url})\n\n"
    result += f"💡 **Tip:** Search for '{place_type} in {location.lower()}' on Booking.com\n"
    result += "🇮🇳 **For Indian Travelers:** All prices in INR with best deals!"
    
    return result

def check_api_config():
    """Check API configuration status"""
    print("\n🔧 **API Configuration Check:**")
    print(f"RAPIDAPI_KEY: {'✅ Set' if RAPIDAPI_KEY else '❌ Missing'}")
    print(f"RAPIDAPI_HOST: {'✅ Set' if RAPIDAPI_HOST else '❌ Missing'}")
    print(f"RAPIDAPI_BASE_URL: {'✅ Set' if RAPIDAPI_BASE_URL else '❌ Missing'}")
    
    if not all([RAPIDAPI_KEY, RAPIDAPI_HOST, RAPIDAPI_BASE_URL]):
        print("\n❌ **Missing API credentials!**")
        print("Please add these to your .env file:")
        print("RAPIDAPI_KEY=your_rapidapi_key")
        print("RAPIDAPI_HOST=booking-com.p.rapidapi.com")
        print("RAPIDAPI_BASE_URL=https://booking-com.p.rapidapi.com")
    else:
        print("\n✅ **All API credentials configured!**")
    print()

if __name__ == "__main__":
    import sys
    import io
    
    # Fix encoding for Windows console
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("🏨 Hotel Booking Assistant")
    check_api_config()
    
    location = input("Enter destination: ")
    place_type = input("Enter accommodation type (hotel/resort/cottage/villa): ")
    budget = input("Enter budget type (budget/average/rich/luxury/all): ") or "all"
    print(asyncio.run(get_booking(location, place_type, budget)))
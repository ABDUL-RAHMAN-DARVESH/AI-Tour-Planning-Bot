import asyncio
import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage
from trip_agent import create_trip_agent
from db.mongo import upsert_user_location, get_user_location

# Updated import path for SOS system
try:
    from tools.sos import SOSSystem
    from tools.sos import add_single_contact
except ImportError as e:
    print(f"Warning: SOS system import failed: {e}")
    class SOSSystem:
        async def trigger_sos(self, *args, **kwargs):
            return "SOS system not available"
    async def add_single_contact(*args, **kwargs):
        return "Contact system not available"

import uvicorn
import sys

# ----------------------------
# Helpers / greeting
# ----------------------------
def get_greeting():
    """Get time-based personalized greeting."""
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "Good morning! Ready to explore India today?"
    elif hour < 17:
        return "Good afternoon! Where shall we travel today?"
    else:
        return "Good evening! Let's plan your next adventure!"

# ----------------------------
# FastAPI app + CORS
# ----------------------------
app = FastAPI(title="AI Travel Guide - Conversational")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# ----------------------------
# Session state and graph
# ----------------------------
SESSIONS: Dict[str, Dict[str, Any]] = {}
GRAPH = create_trip_agent()

# ----------------------------
# Models
# ----------------------------
class LocationIn(BaseModel):
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    city_hint: Optional[str] = Field(None, description="Optional free-text city")

class ContactIn(BaseModel):
    name: str
    number: str
    relation: str

# ----------------------------
# Frontend route
# ----------------------------
@app.get("/")
async def serve_home():
    """Serve the complete Tripset-style website."""
    return FileResponse("frontend/tripset-full.html")

@app.get("/classic")
async def serve_bot_interface():
    """Serve the bot chat interface."""
    return FileResponse("frontend/index.html")



# ----------------------------
# API routes
# ----------------------------
@app.get("/api/status")
async def api_status():
    """API status endpoint."""
    return {
        "message": "AI Travel Guide - Conversational (Fixed SOS)",
        "greeting": get_greeting(),
        "status": "running"
    }

@app.post("/api/location/{user_id}")
async def post_location(user_id: str, loc: LocationIn):
    """Save user location."""
    try:
        await upsert_user_location(user_id, loc.lat, loc.lon, loc.city_hint)
        return {"status": "ok", "user_id": user_id}
    except Exception as e:
        print(f"Error saving location: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/location/{user_id}")
async def get_location(user_id: str):
    """Get user location."""
    try:
        doc = await get_user_location(user_id)
        if not doc:
            return {"status": "empty"}
        return {
            "status": "ok", 
            "location": {
                "lat": doc.get("lat"), 
                "lon": doc.get("lon"), 
                "city_hint": doc.get("city_hint")
            }
        }
    except Exception as e:
        print(f"Error getting location: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/sos/{user_id}")
async def trigger_sos(user_id: str, location: Optional[LocationIn] = None):
    """Trigger immediate SOS alert."""
    try:
        print(f"SOS triggered for user: {user_id}")
        sos_system = SOSSystem()
        
        # Format location if provided
        user_location = None
        if location:
            user_location = f"Lat: {location.lat}, Lon: {location.lon}"
            if location.city_hint:
                user_location += f", Near: {location.city_hint}"
            print(f"SOS location: {user_location}")
        
        # Trigger SOS
        result = await sos_system.trigger_sos(user_location, None, user_id)
        print(f"SOS result: {result}")
        
        # Check if contacts were found
        if "No emergency contacts found" in result:
            return {
                "status": "error", 
                "message": "No emergency contacts found. Please add contacts first using Setup SOS button."
            }
        
        # Check if any messages were sent successfully
        if "sent" in result.lower() or "success" in result.lower():
            return {"status": "success", "message": result}
        else:
            return {"status": "partial", "message": result}
            
    except Exception as e:
        print(f"SOS API error: {e}")
        return {
            "status": "error", 
            "message": f"SOS system error: {str(e)}"
        }

@app.post("/api/contacts/{user_id}")
async def add_contact(user_id: str, contact: ContactIn):
    """Add emergency contact."""
    try:
        print(f"Adding contact for user {user_id}: {contact.name}")
        result = await add_single_contact(user_id, contact.dict())
        print(f"Contact add result: {result}")
        return {"status": "success", "message": result}
    except Exception as e:
        print(f"Error adding contact: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/contacts/{user_id}")
async def get_contacts(user_id: str):
    """Get all emergency contacts for user."""
    try:
        from tools.sos import list_contacts
        result = await list_contacts(user_id)
        return {"status": "success", "message": result}
    except Exception as e:
        print(f"Error getting contacts: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/images")
async def get_place_images(place: str):
    """Get images for a place using the images tool."""
    try:
        from tools.images import get_wikimedia_images
        result = await get_wikimedia_images(place)
        return {"status": "success", "images": result}
    except Exception as e:
        print(f"Error getting images: {e}")
        return {"status": "error", "message": str(e)}

# ----------------------------
# WebSocket chat - IMPROVED
# ----------------------------
@app.websocket("/ws/{user_id}")
async def ws_chat(websocket: WebSocket, user_id: str):
    await websocket.accept()

    # Initialize session if new - NO SYSTEM MESSAGE IN CONVERSATION
    if user_id not in SESSIONS:
        SESSIONS[user_id] = {"messages": []}

    # Send psychology-aware welcome
    greeting = get_greeting()
    await websocket.send_text(f"🎯 **Welcome to Your AI Travel Guide!**\n\n{greeting}\n\n**I specialize in:**\n• 🗺️ **Step-by-step trip planning** (considering meal times & energy levels)\n• 🌤️ **Real-time weather** for perfect timing\n• 🏞️ **Safe attractions** (family-friendly waterfalls first!)\n• 🏨 **Smart accommodation** suggestions\n• 🍛 **Local food** recommendations\n\n**Psychology-aware planning:** I understand when you need breaks, meals, and rest!\n\n**Ready to plan your perfect journey?** Try: 'Plan a 2-day trip to Ooty' or ask about any destination!")

    try:
        while True:
            # Receive user message
            user_text = await websocket.receive_text()
            
            if not user_text.strip():
                await websocket.send_text("🎯 **I'm here to help with your travel needs!**\n\n**Try asking:**\n• 'Plan a weekend trip to Goa'\n• 'Weather in Manali tomorrow'\n• 'Best places in Kerala'\n• 'Hotels in Ooty'\n\n**What's your travel question?**")
                continue

            # Check for SOS-related queries
            user_lower = user_text.lower()
            if any(word in user_lower for word in ["sos", "emergency", "help me", "urgent"]):
                # Handle SOS through the chat interface
                if "add contact" in user_lower or "setup" in user_lower:
                    await websocket.send_text("To setup emergency contacts, please use the 'Setup SOS' button in the interface above. This will allow you to add emergency contacts for future SOS alerts.")
                    continue
                elif "sos" in user_lower or "emergency" in user_lower:
                    await websocket.send_text("For immediate emergency assistance, use the red SOS button (🆘) in the input area. This will instantly send alerts to your saved emergency contacts. If you haven't set up contacts yet, use the 'Setup SOS' button first.")
                    continue

            # Add user message to session
            SESSIONS[user_id]["messages"].append(HumanMessage(content=user_text))

            # Send psychology-aware thinking message
            if any(word in user_lower for word in ["plan", "trip", "days", "itinerary"]):
                await websocket.send_text("🎯 **Planning Your Perfect Trip...** \n\nAnalyzing your preferences and gathering the best recommendations!")
            elif any(word in user_lower for word in ["weather", "places", "directions", "budget"]):
                await websocket.send_text("🔍 **Gathering Latest Information...** \n\nFetching real-time data for you!")

            try:
                # Process with graph - with better error handling
                result = GRAPH.invoke(SESSIONS[user_id])

                if "messages" in result and result["messages"]:
                    SESSIONS[user_id] = result
                    
                    # Find the latest AI response
                    latest_ai_response = None
                    for msg in reversed(result["messages"]):
                        if (hasattr(msg, 'content') and 
                            hasattr(msg, 'type') and 
                            msg.type == 'ai' and 
                            msg.content and 
                            isinstance(msg.content, str) and
                            not (hasattr(msg, 'tool_calls') and msg.tool_calls)):
                            latest_ai_response = msg.content
                            break

                    if latest_ai_response:
                        response_text = latest_ai_response.strip()
                        
                        # Enhanced response formatting for frontend
                        # Convert image links to clickable format
                        response_text = response_text.replace(
                            "[See Here]", "[🔗 See Here]"
                        ).replace(
                            "[View Here]", "[🔗 View Here]"
                        ).replace(
                            "[Check Photo]", "[🔗 Check Photo]"
                        )
                        
                        await websocket.send_text(response_text)
                    else:
                        # Psychology-aware fallback response
                        if any(word in user_lower for word in ['plan', 'trip', 'days', 'itinerary']):
                            await websocket.send_text(f"🎯 **Let's Plan Your Perfect Trip!**\n\nI'm analyzing your request for {user_text}. \n\n**Step-by-Step Planning:**\n• First, I'll suggest morning activities (8-11 AM)\n• Then breakfast spots with local specialties\n• Followed by afternoon attractions\n• Evening relaxation and dinner options\n\n✅ **Ready to create your personalized itinerary!**")
                        else:
                            await websocket.send_text(f"🎯 **Processing Your Travel Query**\n\nI'm gathering information about {user_text}.\n\n**Quick Tips:**\n• For weather: 'Weather in [city]'\n• For places: 'Best places in [destination]'\n• For planning: 'Plan 3-day trip to [location]'\n\n✅ **Ready to help with your travel needs!**")
                else:
                    # Structured fallback response
                    await websocket.send_text(f"🎯 **Step 1 of 2: Query Processing**\n\nI understand you're asking about travel. Let me help!\n\n**Step 2 of 2: How to Get Best Results**\n• Be specific about destinations\n• Mention what you need (weather, places, hotels)\n• Ask about trip planning for detailed itineraries\n\n✅ **Ready to assist with your travel needs!**")
                    
            except Exception as e:
                print(f"Graph processing error: {e}")
                # Provide helpful step-by-step response even on error
                await websocket.send_text(f"🎯 **Step 1 of 2: Processing Your Travel Query**\n\nI'm here to help with your travel planning! \n\n**Step 2 of 2: Let's Get Started**\nTry asking about:\n• Weather: 'What's the weather in Mumbai?'\n• Places: 'Best places to visit in Goa'\n• Planning: 'Plan a 3-day trip to Kerala'\n\n✅ **Ready to create your perfect travel experience!**")

    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")
        # Clean up session after disconnect
        if user_id in SESSIONS:
            del SESSIONS[user_id]
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_text("Connection issue. Please refresh and try again.")
        except:
            pass

# ----------------------------
# CLI Mode Support - IMPROVED
# ----------------------------
async def run_cli():
    """Run the AI Travel Guide directly in terminal."""
    print("\n" + "="*50)
    print(get_greeting())
    print("AI Travel Guide (CLI Mode)")
    print("Ask me about weather, places, directions, or travel planning!")
    print("Type 'exit' to quit, or 'sos' for emergency features.")
    print("="*50 + "\n")

    user_id = "cli_user"
    if user_id not in SESSIONS:
        SESSIONS[user_id] = {"messages": []}

    while True:
        try:
            user_text = input("\nYou: ").strip()
            if user_text.lower() in ["exit", "quit", "bye"]:
                print("\nSafe travels! Have a wonderful journey!")
                break
            
            # Handle SOS in CLI mode
            if user_text.lower() == "sos":
                print("\nTriggering SOS system...")
                from tools.sos import handle_sos_workflow
                result = await handle_sos_workflow(user_id, interactive=True)
                print(f"\nSOS Result: {result}")
                continue

            if not user_text:
                print("Ask me anything about travel! Weather, places to visit, directions...")
                continue

            SESSIONS[user_id]["messages"].append(HumanMessage(content=user_text))
            
            # Show thinking for relevant queries
            user_lower = user_text.lower()
            if any(word in user_lower for word in ["weather", "places", "directions", "budget"]):
                print("Getting latest information...")

            result = GRAPH.invoke(SESSIONS[user_id])
            
            if "messages" in result and result["messages"]:
                SESSIONS[user_id] = result
                
                # Find latest AI response
                for msg in reversed(result["messages"]):
                    if (hasattr(msg, 'content') and 
                        hasattr(msg, 'type') and 
                        msg.type == 'ai' and 
                        msg.content and 
                        isinstance(msg.content, str) and
                        not (hasattr(msg, 'tool_calls') and msg.tool_calls)):
                        
                        response_text = msg.content.strip()
                        print(f"\nTravel Guide: {response_text}")
                        break
                else:
                    # Try once more if no response
                    await asyncio.sleep(0.5)
                    result2 = GRAPH.invoke(SESSIONS[user_id])
                    if "messages" in result2 and result2["messages"]:
                        SESSIONS[user_id] = result2
                        for msg in reversed(result2["messages"]):
                            if (hasattr(msg, 'content') and 
                                hasattr(msg, 'type') and 
                                msg.type == 'ai' and 
                                msg.content and 
                                isinstance(msg.content, str) and
                                not (hasattr(msg, 'tool_calls') and msg.tool_calls)):
                                print(f"\nTravel Guide: {msg.content}")
                                break
                        else:
                            print("\nCould you be more specific? Try: 'Weather in Mumbai' or 'Places in Goa'")
                    else:
                        print("\nI didn't understand that. Ask about a specific destination!")
            else:
                print("\nPlease try asking about a specific place or travel need!")
                
        except KeyboardInterrupt:
            print("\n\nGoodbye! Safe travels!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            print("Please try asking about a specific destination.")

# ----------------------------
# Entry Point
# ----------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        # Run in CLI mode
        asyncio.run(run_cli())
    else:
        # Run in server mode
        print("\nStarting AI Travel Guide Server...")
        print("Access at: http://localhost:7860")
        print("WebSocket endpoint: ws://localhost:7860/ws/{user_id}")
        print("API status: http://localhost:7860/api/status")
        print("SOS functionality: Integrated and working\n")
        
        uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)
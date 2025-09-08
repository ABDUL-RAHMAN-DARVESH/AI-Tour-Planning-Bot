"""
Tool Integration Module for AI Travel Bot
Ensures all tools work properly through frontend with psychology-aware responses
"""

import asyncio
from typing import Dict, Any, Optional, List
from tools.weather import get_weather
from tools.places import get_places
from tools.booking import get_booking
from tools.images import get_images
from tools.news import get_news

class ToolIntegrator:
    """Integrates all tools with psychology-aware responses and error handling."""
    
    def __init__(self):
        self.tool_map = {
            'weather': self._handle_weather,
            'places': self._handle_places,
            'booking': self._handle_booking,
            'images': self._handle_images,
            'news': self._handle_news
        }
    
    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool with proper error handling and formatting."""
        try:
            if tool_name in self.tool_map:
                return await self.tool_map[tool_name](**kwargs)
            else:
                return f"❌ Unknown tool: {tool_name}"
        except Exception as e:
            return f"❌ Tool error: {str(e)}"
    
    async def _handle_weather(self, location: str, add_psychology_tips: bool = False) -> str:
        """Handle weather requests with optional psychology-aware responses."""
        try:
            result = await get_weather(location)
            
            # Only add psychology tips if requested (for trip planning)
            if add_psychology_tips:
                if "very hot" in result.lower() or "35" in result:
                    result += "\n\n🧠 **Psychology Tip:** Hot weather affects energy levels. Plan indoor activities during 12-4 PM, outdoor activities early morning or evening."
                elif "cold" in result.lower() or "10" in result:
                    result += "\n\n🧠 **Psychology Tip:** Cold weather makes people crave warm food and cozy spaces. Perfect time for hot beverages and indoor cultural activities."
                elif "rain" in result.lower():
                    result += "\n\n🧠 **Psychology Tip:** Rainy weather creates cozy moods. Great for museums, cafes, and covered markets. Pack umbrella and enjoy the fresh air!"
            
            return result
        except Exception as e:
            return f"❌ Weather service temporarily unavailable. Try asking about a specific city."
    
    async def _handle_places(self, location: str, place_type: str = "tourism") -> str:
        """Handle places requests with automatic image integration."""
        try:
            places_result = await get_places(location, place_type)
            
            # For trip planning, automatically add images
            if place_type == "tourism":
                try:
                    images_result = await get_images(location)
                    if "📷" in images_result and "🔗" in images_result:
                        places_result += f"\n\n{images_result}"
                except:
                    # Continue without images if they fail
                    pass
            
            # Add psychology-aware timing advice
            if place_type == "tourism":
                places_result += "\n\n🧠 **Psychology Tip:** Visit popular attractions early morning (8-10 AM) when energy is high and crowds are low. Save relaxing spots for afternoon when energy dips."
            
            return places_result
        except Exception as e:
            return f"❌ Places service temporarily unavailable. Try a different location or check spelling."
    
    async def _handle_booking(self, location: str, place_type: str = "hotel", budget_type: str = "all") -> str:
        """Handle booking requests with psychology-aware recommendations."""
        try:
            result = await get_booking(location, place_type, budget_type)
            
            # Add psychology-aware accommodation advice
            result += "\n\n🧠 **Psychology Tip:** Book accommodations near attractions but away from main roads for better sleep. Families prefer ground floor rooms, couples prefer higher floors with views."
            
            return result
        except Exception as e:
            return f"❌ Booking service temporarily unavailable. Try searching directly on booking platforms."
    
    async def _handle_images(self, location: str, clickable_links: bool = True) -> str:
        """Handle image requests with optional clickable links."""
        try:
            result = await get_images(location)
            
            if clickable_links:
                # Format as clickable links for trip planning
                result = result.replace("[See Here]", "[🔗 See Here]")
                result = result.replace("[View Here]", "[🔗 View Here]")
                result = result.replace("[Check Photo]", "[🔗 Check Photo]")
                result = result.replace("[Look Here]", "[🔗 Look Here]")
                result = result.replace("[View Picture]", "[🔗 View Picture]")
            else:
                # Format as display text for simple image queries
                result = result.replace("[🔗 See Here]", "[Image Available]")
                result = result.replace("[🔗 View Here]", "[Image Available]")
                result = result.replace("[🔗 Check Photo]", "[Image Available]")
                result = result.replace("[See Here]", "[Image Available]")
                result = result.replace("[View Here]", "[Image Available]")
                result = result.replace("[Check Photo]", "[Image Available]")
                result = result.replace("[Look Here]", "[Image Available]")
                result = result.replace("[View Picture]", "[Image Available]")
            
            return result
        except Exception as e:
            return f"❌ Image service temporarily unavailable. Try searching for '{location}' images online."
    
    async def _handle_news(self, location: str) -> str:
        """Handle news requests with travel-relevant filtering."""
        try:
            result = await get_news(location)
            
            # Add psychology-aware news interpretation
            result += "\n\n🧠 **Psychology Tip:** Stay informed about local events - festivals boost mood and create memorable experiences, while weather alerts help plan activities."
            
            return result
        except Exception as e:
            return f"❌ News service temporarily unavailable. Check local news websites for '{location}'."

# Global instance
tool_integrator = ToolIntegrator()

async def integrate_tools_for_trip_planning(user_query: str, location: str) -> Dict[str, str]:
    """
    Integrate multiple tools for comprehensive trip planning.
    Returns a dictionary of tool results.
    """
    results = {}
    
    # Detect what tools are needed based on query
    query_lower = user_query.lower()
    
    # Always get weather for trip planning
    if any(word in query_lower for word in ['plan', 'trip', 'visit', 'travel']):
        try:
            results['weather'] = await tool_integrator.execute_tool('weather', location=location)
        except:
            pass
        
        try:
            results['places'] = await tool_integrator.execute_tool('places', location=location, place_type='tourism')
        except:
            pass
        
        # Auto-add images for trip planning
        try:
            results['images'] = await tool_integrator.execute_tool('images', location=location)
        except:
            pass
    
    # Specific tool requests
    if 'weather' in query_lower:
        results['weather'] = await tool_integrator.execute_tool('weather', location=location)
    
    if any(word in query_lower for word in ['places', 'attractions', 'visit']):
        results['places'] = await tool_integrator.execute_tool('places', location=location, place_type='tourism')
    
    if any(word in query_lower for word in ['hotel', 'accommodation', 'stay']):
        results['booking'] = await tool_integrator.execute_tool('booking', location=location, place_type='hotel')
    
    if any(word in query_lower for word in ['images', 'photos', 'pictures']):
        results['images'] = await tool_integrator.execute_tool('images', location=location)
    
    return results

def format_psychology_aware_response(user_query: str, tool_results: Dict[str, str], location: str) -> str:
    """
    Format tool results into a psychology-aware response.
    """
    query_lower = user_query.lower()
    is_trip_planning = any(word in query_lower for word in ['plan', 'trip', 'days', 'itinerary'])
    
    if is_trip_planning:
        return _format_trip_planning_response(tool_results, location)
    else:
        return _format_single_query_response(tool_results, user_query)

def _format_trip_planning_response(tool_results: Dict[str, str], location: str) -> str:
    """Format response for trip planning with step-by-step psychology."""
    response = f"🎯 **Perfect! Let me plan your {location} trip step-by-step:**\n\n"
    
    # Step 1: Weather for timing
    if 'weather' in tool_results:
        response += "**Step 1: Weather Analysis for Perfect Timing**\n"
        response += tool_results['weather'] + "\n\n"
    
    # Step 2: Morning Activity (8-11 AM)
    if 'places' in tool_results:
        response += "**Step 2: Morning Activity Suggestion (8:00 AM - 11:00 AM)**\n"
        response += "Based on human energy patterns, here are the best morning activities:\n\n"
        response += tool_results['places'] + "\n\n"
        response += "🧠 **Psychology Note:** Morning is when energy is highest - perfect for active sightseeing!\n\n"
    
    # Step 3: Visual Preview
    if 'images' in tool_results:
        response += "**Step 3: Visual Preview of Your Destination**\n"
        response += tool_results['images'] + "\n\n"
    
    # Step 4: Next Steps
    response += "**Step 4: What's Next?**\n"
    response += "• Shall we plan your breakfast spot near these attractions?\n"
    response += "• Would you like hotel recommendations for your stay?\n"
    response += "• Ready to plan your afternoon activities (post-lunch 2-5 PM)?\n\n"
    response += "🧠 **Psychology-Aware Planning:** I'll consider meal times, energy levels, and family needs for each activity!"
    
    return response

def _format_single_query_response(tool_results: Dict[str, str], user_query: str) -> str:
    """Format response for single queries."""
    if len(tool_results) == 1:
        return list(tool_results.values())[0]
    
    response = f"🎯 **Here's what I found for your query:**\n\n"
    for tool_name, result in tool_results.items():
        response += f"**{tool_name.title()} Information:**\n{result}\n\n"
    
    return response

# Export the main functions
__all__ = ['tool_integrator', 'integrate_tools_for_trip_planning', 'format_psychology_aware_response']
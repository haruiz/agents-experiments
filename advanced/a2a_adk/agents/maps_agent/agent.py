import os
from google.adk.agents.llm_agent import Agent
import googlemaps
from dotenv import load_dotenv, find_dotenv
from google import genai
from google.genai import types


load_dotenv(find_dotenv())

print("Initializing Google Maps client...")
print(os.getenv("GOOGLE_MAPS_API_KEY"))
gmaps_client = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
genai_client = genai.Client(http_options=types.HttpOptions(api_version="v1"))

def get_place_location(place_name: str) -> dict[str, str]:
    """
    Get coordinates from an address using Google Maps API.
    :param place_name: the name of the place to get coordinates for
    :return:
    """
    """Get coordinates from an address using Google Maps API."""
    try:
        geocode_result = gmaps_client.geocode(place_name)
        if geocode_result is None:
            return {
                "status": "error",
                "message": f"Could not find coordinates for address: {place_name}"
            }

        location = geocode_result[0]["geometry"]["location"]
        lat = location["lat"]
        lng = location["lng"]
        return {
            "status": "success",
            "result": {"latitude": lat, "longitude": lng}
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def get_place_details(query_prompt: str, latitude: float, longitude: float) -> str:
    """
    Get place details using Google Maps Tool in Gemini.
    :param query_prompt:
    :param latitude:
    :param longitude:
    :return:
    """
    response = genai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query_prompt,
        config=types.GenerateContentConfig(
            tools=[
                # Use Google Maps Tool
                types.Tool(google_maps=types.GoogleMaps(
                    enable_widget=False  # Optional: return Maps widget token
                ))
            ],
            tool_config=types.ToolConfig(
                retrieval_config=types.RetrievalConfig(
                    lat_lng=types.LatLng(  # Pass geo coordinates for location-aware grounding
                        latitude=latitude,
                        longitude=longitude,
                    ),
                    language_code="en_US",  # Optional: localize Maps results
                ),
            ),
        ),
    )
    return response.text

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='A helpful assistant for user interact with google maps',
    tools=[get_place_location, get_place_details],
    instruction="""
    You are a helpful assistant that enables users to interact effectively with Google Maps.
    Your capabilities include:
    - Getting the coordinates of a place based on its name or address.
    - Retrieving detailed information about places using Google Maps tools.
    
    Tools:
    - get_place_location: Use this tool to obtain the latitude and longitude of a specified place.
    - get_place_details: Use this tool to fetch detailed information about a place using its coordinates, including 
    general information, reviews, and nearby points of interest.
    
    """
)

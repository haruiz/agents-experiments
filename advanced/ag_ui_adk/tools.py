import os

import googlemaps
import httpx
from google import genai
from google.genai import types
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


gmaps_client = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
genai_client = genai.Client(http_options=types.HttpOptions(api_version="v1"))

def get_weather_condition(code: int) -> str:
    """Map weather code to human-readable condition.

    Args:
        code: WMO weather code.

    Returns:
        Human-readable weather condition string.
    """
    conditions = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return conditions.get(code, "Unknown")


async def get_weather(location: str) -> dict:
    """Get the weather for a given location.

    Args:
        location: City name.

    Returns:
        Dictionary with weather information including temperature, feels like,
        humidity, wind speed, wind gust, conditions, and location name.
    """
    async with httpx.AsyncClient() as client:
        # Geocode the location
        geocoding_url = (
            f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
        )
        geocoding_response = await client.get(geocoding_url)
        geocoding_data = geocoding_response.json()
        print(geocoding_data)

        if not geocoding_data.get("results"):
            raise ValueError(f"Location '{location}' not found")

        result = geocoding_data["results"][0]
        latitude = result["latitude"]
        longitude = result["longitude"]
        name = result["name"]

        # Get weather data
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitude}&longitude={longitude}"
            f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
            f"wind_speed_10m,wind_gusts_10m,weather_code"
        )
        weather_response = await client.get(weather_url)
        weather_data = weather_response.json()


        current = weather_data["current"]

        result =  {
            "temperature": current["temperature_2m"],
            "feelsLike": current["apparent_temperature"],
            "humidity": current["relative_humidity_2m"],
            "windSpeed": current["wind_speed_10m"],
            "windGust": current["wind_gusts_10m"],
            "conditions": get_weather_condition(current["weather_code"]),
            "location": name,
        }
        return result


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
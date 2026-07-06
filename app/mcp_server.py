from mcp.server.fastmcp import FastMCP
import random

mcp = FastMCP("crop-doctor-mcp")

@mcp.tool()
def get_soil_metrics(location: str, crop_type: str = "tomato") -> dict:
    """Gets simulated real-time soil chemistry and moisture metrics for a crop in a location.

    Args:
        location: The location or region where the crop is grown.
        crop_type: The type of crop (e.g., tomato, potato, wheat).
    """
    random.seed(hash(location + crop_type))
    ph = round(random.uniform(5.5, 7.5), 1)
    nitrogen = random.randint(10, 50)
    phosphorus = random.randint(10, 50)
    potassium = random.randint(10, 50)
    moisture = random.choice(["dry", "optimal", "waterlogged"])
    
    return {
        "location": location,
        "crop_type": crop_type,
        "soil_ph": ph,
        "nutrients": {
            "nitrogen_ppm": nitrogen,
            "phosphorus_ppm": phosphorus,
            "potassium_ppm": potassium
        },
        "moisture_level": moisture
    }

@mcp.tool()
def get_local_weather_forecast(location: str) -> dict:
    """Gets a simulated local weather forecast including temperature, humidity, and rainfall.

    Args:
        location: The city or region name.
    """
    random.seed(hash(location))
    temp = random.randint(55, 95)
    humidity = random.randint(30, 95)
    rainfall_probability = random.randint(0, 100)
    conditions = random.choice(["sunny", "cloudy", "rainy", "humid"])
    
    return {
        "location": location,
        "temperature_f": temp,
        "humidity_percentage": humidity,
        "rainfall_probability": rainfall_probability,
        "conditions": conditions
    }

@mcp.tool()
def search_treatment_database(disease: str) -> dict:
    """Searches a local organic remedies and treatments database for a given plant disease.

    Args:
        disease: The name of the plant disease (e.g., blight, powdery mildew).
    """
    db = {
        "blight": {
            "remedy": "Apply copper fungicide or a diluted baking soda spray (1 tbsp baking soda + 1 tsp liquid soap + 1 gallon water).",
            "prevention": "Ensure good spacing for air circulation, avoid overhead watering, and prune lower leaves.",
            "severity": "High"
        },
        "powdery mildew": {
            "remedy": "Spray with a milk-water mixture (1 part milk to 9 parts water) or neem oil.",
            "prevention": "Grow in full sun, improve air circulation, and prune infected leaves early.",
            "severity": "Medium"
        },
        "aphids": {
            "remedy": "Blast with a strong stream of water or spray with insecticidal soap / neem oil.",
            "prevention": "Encourage natural predators like ladybugs, and plant companion herbs like dill or marigolds.",
            "severity": "Low"
        },
        "rust": {
            "remedy": "Apply sulfur dust or copper-based sprays. Remove and destroy infected leaves.",
            "prevention": "Avoid wetting foliage, clean tools between plants, and rotate crops.",
            "severity": "Medium"
        }
    }
    
    query = disease.lower()
    for key, val in db.items():
        if key in query:
            return {"disease": key, "result": val}
            
    return {
        "disease": disease,
        "result": {
            "remedy": "Use a general organic fungicide (neem oil) and prune affected parts.",
            "prevention": "Maintain soil health, rotate crops, and sanitize tools.",
            "severity": "Unknown"
        }
    }

if __name__ == "__main__":
    mcp.run()

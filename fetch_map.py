"""
Salamina Map Data Fetcher

This script uses the Overpass API to download and cache OpenStreetMap (OSM) data
for Salamina island, including points of interest, places, and residential areas.
"""

import json
import requests

def fetch_salamina_map_data():
    """
    Fetches residential landuse areas, buildings, and place names (towns, villages,
    neighborhoods) for Salamina, Greece using the Overpass API.
    """
    overpass_url = "http://overpass-api.de/api/interpreter"

    # Overpass QL query to find built-up residential areas and place nodes
    overpass_query = """
    [out:json][timeout:90];
    // Find the area for Salamina to restrict our search
    area["name"="Σαλαμίνα"]->.searchArea;
    (
      // Get nodes for all place names (towns, villages, hamlets, neighborhoods, localities)
      // This will match the "black text" locations on the map (Batsi, Peristeria, etc.)
      node["place"~"town|village|suburb|hamlet|neighbourhood|isolated_dwelling|locality"](area.searchArea);

      // Get the exact polygon borders of built-up / residential areas
      way["landuse"~"residential|commercial|retail|industrial|military"](area.searchArea);
      relation["landuse"~"residential|commercial|retail|industrial|military"](area.searchArea);

      // Also grab any area explicitly tagged as a place
      way["place"~"town|village|suburb|hamlet|neighbourhood"](area.searchArea);
      relation["place"~"town|village|suburb|hamlet|neighbourhood"](area.searchArea);

      // Get all buildings to ensure no area is left blank if residential tags are missing
      way["building"](area.searchArea);
      relation["building"](area.searchArea);
    );
    // Output geometry directly so we can parse coordinates for ways and relations
    out geom;
    """

    print("Fetching exact residential areas and place names from Overpass API...")
    try:
        response = requests.post(overpass_url, data={'data': overpass_query})
        response.raise_for_status()

        data = response.json()

        output_filename = "salamina_map_data.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Successfully fetched data. Saved to {output_filename}")
        print(f"Found {len(data.get('elements', []))} elements (residential areas and place names).")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
    except json.JSONDecodeError:
        print("Error decoding the response as JSON. The API might have returned an error message.")

if __name__ == "__main__":
    fetch_salamina_map_data()

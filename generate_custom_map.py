"""
Salamina Custom Map Generator

This script reads the base Salamina island outline and a collection of custom
GeoJSON areas, processing them into a highly optimized, commercial-ready SVG map.
"""

import os
import glob
import json
from shapely.geometry import shape, Polygon
from shapely.ops import unary_union

def generate_custom_svg():
    """
    Main function to generate the SVG map.
    Reads 'salamina_outline.json' for the island base and parses all
    '.geojson' files in the 'custom_areas/' directory.
    """
    input_outline_filename = "salamina_outline.json"
    output_filename = "salamina_custom_labeled.svg"
    custom_dir = "custom_areas"

    # SVG Settings
    width = 1200
    height = 1000

    # Load Island Outline to establish bounds
    try:
        with open(input_outline_filename, 'r', encoding='utf-8') as f:
            outline_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {input_outline_filename} not found. Please run outline fetcher first.")
        return

    # Extract raw lat/lon coordinates to find bounding box
    raw_coords = []
    poly_list = outline_data.get('coordinates', []) if outline_data.get('type') == 'MultiPolygon' else [outline_data.get('coordinates', [])]
    for poly in poly_list:
        if poly: raw_coords.extend(poly[0])

    if not raw_coords:
        print("Could not extract coordinates from outline.")
        return

    lons, lats = zip(*raw_coords)
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Add padding
    lat_pad = (max_lat - min_lat) * 0.05
    lon_pad = (max_lon - min_lon) * 0.05
    min_lat -= lat_pad
    max_lat += lat_pad
    min_lon -= lon_pad
    max_lon += lon_pad

    def project(lat, lon):
        """Converts lat/lon to X/Y pixel coordinates on our SVG canvas."""
        x = (lon - min_lon) / (max_lon - min_lon) * width
        y = height - ((lat - min_lat) / (max_lat - min_lat) * height)
        return x, y

    # Process Island Outline into Projected Polygons
    island_polygons = [Polygon([project(c[1], c[0]) for c in poly[0]]) for poly in poly_list if poly and len(poly[0]) >= 3]

    island_boundary = unary_union(island_polygons).simplify(0.5, preserve_topology=True)

    # Load Custom Areas
    custom_regions = {}
    if os.path.exists(custom_dir):
        for filepath in glob.glob(os.path.join(custom_dir, "*.geojson")):
            name = os.path.splitext(os.path.basename(filepath))[0]

            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    gj = json.load(f)
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse {filepath}")
                    continue

            polys = []
            features = gj.get("features", [])
            for feature in features:
                geom = feature.get("geometry")
                if not geom: continue

                # Project the raw geographic coordinates directly into SVG pixel space
                def project_coords(coords):
                    if isinstance(coords[0], (int, float)):
                        # GeoJSON is [lon, lat]
                        return project(coords[1], coords[0])
                    return [project_coords(c) for c in coords]

                try:
                    projected_geom = {
                        "type": geom["type"],
                        "coordinates": project_coords(geom["coordinates"])
                    }
                    s = shape(projected_geom)

                    if s.geom_type == 'LineString' and len(s.coords) >= 3:
                        s = Polygon(s.coords)
                    if s.geom_type in ('Polygon', 'MultiPolygon'):
                        polys.append(s if s.is_valid else s.buffer(0))
                except Exception as e:
                    print(f"Skipping a malformed feature in {name}: {e}")

            if polys:
                # Merge all drawn shapes in the file for this area
                union_poly = unary_union(polys)

                # Perfectly clip it so it doesn't spill into the ocean
                clipped_poly = union_poly.intersection(island_boundary).simplify(0.5, preserve_topology=True)
                if not clipped_poly.is_empty:
                    custom_regions[name] = clipped_poly

    # Generate SVG Elements
    svg_elements = []

    # SVG Stylesheets
    svg_elements.append('''  <style>
    .water { fill: #aadaff; }
    .land { fill: #f2efe9; stroke: #dcd0b9; stroke-width: 1.5px; }
    .custom-area { stroke: #888888; stroke-width: 1px; fill-opacity: 0.6; }
    .marker { fill: #222; stroke: #fff; stroke-width: 1px; }
    .label { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #111; text-anchor: middle; paint-order: stroke; stroke: #ffffff; stroke-width: 3px; stroke-linecap: round; stroke-linejoin: round; }
  </style>''')

    # 1. Background (Water)
    svg_elements.append('  <rect width="100%" height="100%" class="water" />')

    # 2. Island Base (Land)
    def geom_to_path_d(geom):
        """Converts a Polygon/MultiPolygon to an SVG path string, supporting holes."""
        path_data = []
        for poly in ([geom] if isinstance(geom, Polygon) else geom.geoms):
            if poly.is_empty: continue
            # Exterior ring
            path_data.append("M" + " ".join([f"{x:.1f},{y:.1f}" for x, y in poly.exterior.coords]) + "Z")
            # Interior rings (holes)
            for interior in poly.interiors:
                path_data.append("M" + " ".join([f"{x:.1f},{y:.1f}" for x, y in interior.coords]) + "Z")
        return " ".join(path_data)

    # Draw the main island
    island_path = geom_to_path_d(island_boundary)
    svg_elements.append(f'  <path id="island_base" class="land" fill-rule="evenodd" d="{island_path}" />')

    # 3. Custom Hand-Drawn Regions
    colors = [
        "#fbb4ae", "#b3cde3", "#ccebc5", "#decbe4", "#fed9a6",
        "#ffffcc", "#e5d8bd", "#fddaec", "#f2f2f2", "#b3e2cd",
        "#fdcdac", "#cbd5e8", "#f4cae4", "#e6f5c9", "#fff2ae"
    ]

    svg_elements.append('  <g id="custom_regions">')
    color_idx = 0
    for name, region in custom_regions.items():
        color = colors[color_idx % len(colors)]
        color_idx += 1
        safe_name = name.replace(' ', '_').replace('"', '')

        region_path = geom_to_path_d(region)
        svg_elements.append(f'    <path id="custom_{safe_name}" class="custom-area" fill="{color}" fill-rule="evenodd" d="{region_path}" />')
    svg_elements.append('  </g>')

    # 4. Markers and Labels
    svg_elements.append('  <g id="markers_and_labels">')
    for name, region in custom_regions.items():
        # Find a safe interior point to place label and marker
        rep_point = region.representative_point()
        x, y = rep_point.x, rep_point.y

        # Draw center point
        svg_elements.append(f'    <circle cx="{x:.1f}" cy="{y:.1f}" r="3" class="marker" />')

        # Draw place name label
        svg_elements.append(f'    <text x="{x:.1f}" y="{y - 8:.1f}" class="label">{name}</text>')
    svg_elements.append('  </g>')

    # Assemble and write final SVG file
    svg_header = f'<?xml version="1.0" encoding="UTF-8"?>\n<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
    svg_footer = '</svg>'

    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(svg_header)
        f.write("\n".join(svg_elements))
        f.write("\n" + svg_footer)

    print(f"Generated Map: {output_filename}")
    print(f"Mapped {len(custom_regions)} custom areas: {', '.join(custom_regions.keys())}")

if __name__ == "__main__":
    generate_custom_svg()

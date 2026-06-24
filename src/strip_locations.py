import argparse
import json
import os
from pathlib import Path
import geopandas as gpd
import pandas as pd
import xarray as xr

def process_resource_file(file_path: Path, standardized_removed: set[str]):
    # 1. Process NetCDF files
    if file_path.suffix.lower() == '.nc':
        print(f"  Processing NetCDF: {file_path.name}")
        try:
            with xr.open_dataset(file_path) as ds:
                ds.load()
            
            if "locations" in ds.dims:
                if "locations" in ds.coords:
                    locations_clean = [str(x).replace(" ", "") for x in ds.locations.values.astype(str)]
                    keep_mask = [loc not in standardized_removed for loc in locations_clean]
                    num_before = ds.sizes["locations"]
                    ds_filtered = ds.isel(locations=keep_mask)
                    num_after = ds_filtered.sizes["locations"]
                    print(f"    Filtered locations dimension: {num_before} -> {num_after}")
                    
                    # Save to temp file first to prevent corruption, then overwrite
                    temp_path = file_path.with_suffix('.tmp.nc')
                    ds_filtered.to_netcdf(temp_path)
                    temp_path.replace(file_path)
                else:
                    print(f"    [WARNING] 'locations' dimension exists in {file_path.name} but has no coordinate variable. Skipping.")
            else:
                print(f"    No 'locations' dimension found. Skipping.")
        except Exception as e:
            print(f"    [ERROR] Failed to process NetCDF {file_path.name}: {e}")

    # 2. Process CSV files (connectivity matrices)
    elif file_path.suffix.lower() == '.csv':
        print(f"  Processing CSV: {file_path.name}")
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            comments = [line for line in lines if line.startswith('#')]
            
            df = pd.read_csv(file_path, comment='#', index_col=0)
            
            # Filter rows (index)
            row_clean = [str(r).replace(" ", "") for r in df.index]
            keep_rows = [loc not in standardized_removed for loc in row_clean]
            
            # Filter columns
            col_clean = [str(c).replace(" ", "") for c in df.columns]
            keep_cols = [loc not in standardized_removed for loc in col_clean]
            
            df_filtered = df.loc[keep_rows, keep_cols]
            print(f"    Filtered shape: {df.shape} -> {df_filtered.shape}")
            
            with open(file_path, 'w') as f:
                for comment in comments:
                    f.write(comment)
                df_filtered.to_csv(f)
        except Exception as e:
            print(f"    [ERROR] Failed to process CSV {file_path.name}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Strip locations with carrying capacity (k) = 0 from an ADRIA Domain data package")
    parser.add_argument("domain_path", type=str, help="Path to the ADRIA Domain directory")
    args = parser.parse_args()

    domain_path = Path(args.domain_path).resolve()
    if not domain_path.exists() or not domain_path.is_dir():
        print(f"[ERROR] Domain path '{domain_path}' does not exist or is not a directory.")
        return

    dpkg_path = domain_path / "datapackage.json"
    if not dpkg_path.exists():
        print(f"[ERROR] datapackage.json not found at {dpkg_path}")
        return

    with open(dpkg_path, "r") as f:
        dpkg_data = json.load(f)

    # 1. Find the spatial resource
    resources = dpkg_data.get("resources", [])
    spatial_res = next((r for r in resources if r.get("format", "").lower() == "geopackage"), None)
    if not spatial_res:
        spatial_res = next((r for r in resources if r.get("name") == "spatial_data"), None)

    if not spatial_res:
        print("[ERROR] Spatial GeoPackage resource not defined in datapackage.json.")
        return

    spatial_path = domain_path / spatial_res.get("path")
    if not spatial_path.exists():
        print(f"[ERROR] Spatial file missing at {spatial_path}")
        return

    # Determine columns
    location_id_col = spatial_res.get("location_id_col") or "reef_siteid"
    k_col = spatial_res.get("k_col") or "k"

    print(f"Loading GeoPackage from: {spatial_path.name}")
    print(f"  Location ID Column: '{location_id_col}'")
    print(f"  Carrying Capacity Column: '{k_col}'")

    gdf = gpd.read_file(spatial_path)
    if k_col not in gdf.columns:
        print(f"[ERROR] Column '{k_col}' not found in GeoPackage columns: {list(gdf.columns)}")
        return
    if location_id_col not in gdf.columns:
        print(f"[ERROR] Column '{location_id_col}' not found in GeoPackage columns: {list(gdf.columns)}")
        return

    # 2. Find locations where k == 0
    k_values = pd.to_numeric(gdf[k_col], errors='coerce').fillna(0.0)
    zero_k_mask = k_values == 0.0
    removed_ids = gdf.loc[zero_k_mask, location_id_col].astype(str).tolist()
    
    if not removed_ids:
        print("No locations with carrying capacity (k) = 0 found. Nothing to strip.")
        return

    print(f"Found {len(removed_ids)} locations with carrying capacity = 0:")
    for rid in removed_ids[:10]:
        print(f"  - {rid}")
    if len(removed_ids) > 10:
        print(f"  - ... and {len(removed_ids) - 10} more.")

    # 3. Filter GeoPackage
    filtered_gdf = gdf[~zero_k_mask]
    print(f"Filtering GeoPackage sites: {len(gdf)} -> {len(filtered_gdf)}")
    
    # Save GeoPackage back
    layer_name = spatial_path.stem
    spatial_path.unlink(missing_ok=True)
    filtered_gdf.to_file(str(spatial_path), layer=layer_name, driver="GPKG", engine="pyogrio")
    print("  GeoPackage updated.")

    # 4. Filter other data resources
    standardized_removed = {s.replace(" ", "") for s in removed_ids}
    
    for resource in resources:
        res_name = resource.get("name")
        res_path_str = resource.get("path")
        if not res_path_str:
            continue
        
        # Skip the spatial GeoPackage itself as we just processed it
        if res_name == spatial_res.get("name") or res_path_str == spatial_res.get("path"):
            continue
            
        full_res_path = domain_path / res_path_str
        if not full_res_path.exists():
            print(f"[WARNING] Resource path '{res_path_str}' does not exist. Skipping.")
            continue
            
        print(f"Processing resource '{res_name}' at path '{res_path_str}'...")
        if full_res_path.is_dir():
            for child in full_res_path.rglob("*"):
                if child.is_file():
                    process_resource_file(child, standardized_removed)
        else:
            process_resource_file(full_res_path, standardized_removed)

    # 5. Document removed locations in datapackage.json
    # Keep track of cumulative removed location IDs (extend if existing)
    existing_removed = dpkg_data.get("removed_locations", [])
    combined_removed = sorted(list(set(existing_removed + removed_ids)))
    dpkg_data["removed_locations"] = combined_removed

    with open(dpkg_path, "w") as f:
        json.dump(dpkg_data, f, indent=4)
    print(f"datapackage.json updated with 'removed_locations' list containing {len(combined_removed)} IDs.")
    print("Strip operation complete.")

if __name__ == "__main__":
    main()

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
import geopandas as gpd

from schemas import DataPackage
from utils import load_geopackage_ids

def parse_index_mapping(map_json_str: Optional[str], map_file_path: Optional[str]) -> Dict[int, str]:
    """
    Parses index-to-ID mapping from JSON string or file.
    Indices in the JSON keys (e.g. "89") are converted to integers.
    """
    raw_mapping: Dict[str, str] = {}

    if map_json_str:
        try:
            raw_mapping = json.loads(map_json_str)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse --map-json: {e}")
            sys.exit(1)

    if map_file_path:
        file_path = Path(map_file_path)
        if not file_path.exists():
            print(f"[ERROR] Mapping file not found: {map_file_path}")
            sys.exit(1)
        try:
            with open(file_path, "r") as f:
                raw_mapping.update(json.load(f))
        except Exception as e:
            print(f"[ERROR] Failed to read mapping file: {e}")
            sys.exit(1)

    # Convert keys to integer indices
    index_mapping: Dict[int, str] = {}
    for k, v in raw_mapping.items():
        try:
            index_mapping[int(k)] = str(v)
        except ValueError:
            print(f"[ERROR] Invalid mapping key '{k}'. Index keys must be integers.")
            sys.exit(1)

    return index_mapping

def validate_mapping_against_geopackage(
    index_mapping: Dict[int, str], 
    spatial_ids: List[str]
) -> None:
    """
    Validates that the target IDs in the index mapping exist in the spatial GeoPackage.
    """
    spatial_set = set(spatial_ids)
    invalid_ids = []
    
    for idx, target_id in index_mapping.items():
        # Validate index boundary
        if idx < 0 or idx >= len(spatial_ids):
            print(f"[ERROR] Mapping index {idx} is out of boundary (0 to {len(spatial_ids) - 1}).")
            sys.exit(1)
            
        # Validate ID exists in geopackage
        if target_id not in spatial_set:
            invalid_ids.append((idx, target_id))

    if invalid_ids:
        print("[ERROR] The following mapped IDs are not present in the spatial GeoPackage:")
        for idx, target_id in invalid_ids:
            print(f"  Index {idx} -> '{target_id}' (missing)")
        sys.exit(1)

def strip_pandas_suffix(name: str) -> str:
    """
    Strips Pandas deduplication suffixes like '.1', '.2' from a name.
    """
    if "." in name:
        return name.split(".")[0]
    return name

def process_connectivity_file(
    file_path: Path, 
    spatial_ids: List[str],
    index_mapping: Dict[int, str],
    dry_run: bool,
    aligned_mappings: Dict[str, str]
) -> bool:
    """
    Processes a single connectivity CSV file by remapping headers in-place based on the index mapping.
    Returns True if the file was modified, False otherwise.
    """
    if file_path.suffix.lower() != ".csv":
        return False

    try:
        # Load comments
        with open(file_path, "r") as f:
            lines = f.readlines()
        comments = [line for line in lines if line.startswith("#")]

        # Load CSV data
        df = pd.read_csv(file_path, comment="#", header=0, index_col=0)
        row_count, col_count = df.shape

        if row_count != len(spatial_ids) or col_count != len(spatial_ids):
            print(f"  [WARNING] Dimensions of {file_path.name} ({row_count}x{col_count}) do not match GeoPackage site count ({len(spatial_ids)}). Skipping.")
            return False

        # Convert index and columns to list to modify
        current_rows = list(df.index)
        current_cols = list(df.columns)

        modified = False
        change_details = []

        # Apply specific mappings
        for idx, target_id in index_mapping.items():
            old_row = current_rows[idx]
            old_col = current_cols[idx]
            if old_row != target_id or old_col != target_id:
                aligned_mappings[old_row] = target_id
                current_rows[idx] = target_id
                current_cols[idx] = target_id
                modified = True
                change_details.append(f"    - Index {idx:3d} | Row/Col: '{old_row}' -> '{target_id}'")

        if not modified:
            return False

        if dry_run:
            print(f"  [DRY-RUN] Would modify connectivity IDs in: {file_path.name}")
            for detail in change_details:
                print(detail)
            return True

        # Assign updated IDs back
        df.index = current_rows
        df.columns = current_rows

        # Write comments and updated matrix back
        with open(file_path, "w") as f:
            for comment in comments:
                f.write(comment)
            df.to_csv(f)

        print(f"  [OK] Successfully aligned IDs in: {file_path.name}")
        for detail in change_details:
            print(detail)
        return True

    except Exception as e:
        print(f"  [ERROR] Failed to process connectivity file {file_path.name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Align/map connectivity matrix row & column indices to correct GeoPackage site IDs"
    )
    parser.add_argument("domain_path", type=str, help="Path to the ADRIA Domain directory")
    parser.add_argument("--map-json", type=str, help="JSON string mapping index to site ID, e.g. '{\"89\": \"Lizard_1f\"}'")
    parser.add_argument("--map-file", type=str, help="Path to a JSON file containing index to site ID mapping")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing them to disk")
    args = parser.parse_args()

    # 1. Validate inputs (mapping is required)
    if not args.map_json and not args.map_file:
        print("[ERROR] You must specify a mapping input: either --map-json or --map-file")
        sys.exit(1)

    domain_path = Path(args.domain_path).resolve()
    if not domain_path.exists() or not domain_path.is_dir():
        print(f"[ERROR] Domain path '{domain_path}' does not exist or is not a directory.")
        sys.exit(1)

    dpkg_path = domain_path / "datapackage.json"
    if not dpkg_path.exists():
        print(f"[ERROR] datapackage.json not found at {dpkg_path}")
        sys.exit(1)

    # 2. Load datapackage and GeoPackage spatial IDs
    with open(dpkg_path, "r") as f:
        dpkg_data = json.load(f)
    
    dpkg_schema = DataPackage(**dpkg_data)
    spatial_ids = load_geopackage_ids(domain_path, dpkg_schema)
    if spatial_ids is None:
        print("[ERROR] Failed to load location IDs from GeoPackage. Aborting alignment.")
        sys.exit(1)

    # 3. Parse and validate mapping
    index_mapping = parse_index_mapping(args.map_json, args.map_file)
    validate_mapping_against_geopackage(index_mapping, spatial_ids)
    print(f"Loaded and validated mapping for {len(index_mapping)} indices.")

    # 4. Find connectivity files
    resources = dpkg_data.get("resources", [])
    conn_res = next((r for r in resources if r.get("name") == "connectivity"), None)
    if not conn_res:
        conn_res = next((r for r in resources if r.get("format", "").lower() == "csv" and "connectivity" in r.get("path", "").lower()), None)

    if not conn_res:
        print("[ERROR] Connectivity resource not defined in datapackage.json.")
        sys.exit(1)

    conn_path_str = conn_res.get("path")
    full_conn_path = domain_path / conn_path_str
    if not full_conn_path.exists():
        print(f"[ERROR] Connectivity path '{conn_path_str}' does not exist.")
        sys.exit(1)

    print(f"Scanning connectivity files in: {full_conn_path.name}")

    aligned_mappings: Dict[str, str] = {}
    modified_files_count = 0
    total_files_count = 0

    # 5. Process files
    if full_conn_path.is_dir():
        for child in full_conn_path.rglob("*.csv"):
            total_files_count += 1
            if process_connectivity_file(child, spatial_ids, index_mapping, args.dry_run, aligned_mappings):
                modified_files_count += 1
    else:
        total_files_count += 1
        if process_connectivity_file(full_conn_path, spatial_ids, index_mapping, args.dry_run, aligned_mappings):
            modified_files_count += 1

    print(f"Scan complete. Checked {total_files_count} files.")
    
    if modified_files_count == 0:
        print("No mismatched row/column names found in connectivity matrices. Nothing to modify.")
        sys.exit(0)

    if args.dry_run:
        print(f"[DRY-RUN] Would have updated {modified_files_count} files. Total unique IDs to align: {len(aligned_mappings)}")
        sys.exit(0)

    print(f"Updated {modified_files_count} of {total_files_count} connectivity files.")
    print(f"Total unique IDs aligned: {len(aligned_mappings)}")

    # 6. Update datapackage.json to log the aligned mappings
    existing_aligned = dpkg_data.get("aligned_connectivity_ids", {})
    if not isinstance(existing_aligned, dict):
        existing_aligned = {}
        
    existing_aligned.update(aligned_mappings)
    
    # Clean keys of the merged dictionary (remove pandas suffixes)
    cleaned_aligned = {}
    for k, v in existing_aligned.items():
        clean_key = strip_pandas_suffix(k)
        cleaned_aligned[clean_key] = v
        
    dpkg_data["aligned_connectivity_ids"] = cleaned_aligned

    with open(dpkg_path, "w") as f:
        json.dump(dpkg_data, f, indent=4)

    print(f"datapackage.json updated with 'aligned_connectivity_ids' mapping containing {len(cleaned_aligned)} entries.")
    print("Alignment operation complete.")

if __name__ == "__main__":
    main()

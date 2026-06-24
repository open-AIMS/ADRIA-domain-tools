import argparse
import json
import os
from pathlib import Path
import pandas as pd

def process_connectivity_file(file_path: Path, cleaned_ids_set: set[str]) -> bool:
    if file_path.suffix.lower() != '.csv':
        return False
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        comments = [line for line in lines if line.startswith('#')]
        
        df = pd.read_csv(file_path, comment='#', index_col=0)
        
        # Find rows and columns containing spaces
        rows_with_spaces = [str(r) for r in df.index if " " in str(r)]
        cols_with_spaces = [str(c) for c in df.columns if " " in str(c)]
        
        if not rows_with_spaces and not cols_with_spaces:
            return False
            
        # Add original names to cumulative set for documentation
        cleaned_ids_set.update(rows_with_spaces)
        cleaned_ids_set.update(cols_with_spaces)
        
        # Strip spaces
        df.index = [str(i).replace(" ", "") for i in df.index]
        df.columns = [str(c).replace(" ", "") for c in df.columns]
        
        # Save back
        with open(file_path, 'w') as f:
            for comment in comments:
                f.write(comment)
            df.to_csv(f)
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to process connectivity file {file_path.name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Clean/normalize connectivity matrix headers by removing spaces to align with canonical site IDs")
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

    # Find the connectivity resource
    resources = dpkg_data.get("resources", [])
    conn_res = next((r for r in resources if r.get("name") == "connectivity"), None)
    if not conn_res:
        conn_res = next((r for r in resources if r.get("format", "").lower() == "csv" and "connectivity" in r.get("path", "").lower()), None)

    if not conn_res:
        print("[ERROR] Connectivity resource not defined in datapackage.json.")
        return

    conn_path_str = conn_res.get("path")
    full_conn_path = domain_path / conn_path_str
    if not full_conn_path.exists():
        print(f"[ERROR] Connectivity path '{conn_path_str}' does not exist.")
        return

    print(f"Scanning connectivity files in: {full_conn_path.name}")
    
    cleaned_ids = set()
    modified_files_count = 0
    total_files_count = 0

    if full_conn_path.is_dir():
        for child in full_conn_path.rglob("*.csv"):
            total_files_count += 1
            if process_connectivity_file(child, cleaned_ids):
                modified_files_count += 1
    else:
        total_files_count += 1
        if process_connectivity_file(full_conn_path, cleaned_ids):
            modified_files_count += 1

    print(f"Scan complete. Checked {total_files_count} files.")
    
    if modified_files_count == 0:
        print("No space-containing site IDs found in connectivity matrices. Nothing to clean.")
        return

    print(f"Cleaned {modified_files_count} of {total_files_count} connectivity files.")
    print(f"Total unique IDs normalized: {len(cleaned_ids)}")
    
    # Document normalized IDs in datapackage.json
    existing_normalized = dpkg_data.get("normalized_connectivity_ids", [])
    combined_normalized = sorted(list(set(existing_normalized + list(cleaned_ids))))
    dpkg_data["normalized_connectivity_ids"] = combined_normalized

    with open(dpkg_path, "w") as f:
        json.dump(dpkg_data, f, indent=4)
        
    print(f"datapackage.json updated with 'normalized_connectivity_ids' list containing {len(combined_normalized)} IDs.")
    print("Clean operation complete.")

if __name__ == "__main__":
    main()

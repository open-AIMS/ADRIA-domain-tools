# ADRIA Domain Tools

A collection of utility CLI tools to validate, normalize, and process ADRIA Domain Data Packages.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) (recommended Python package manager)

## Installation

To sync the dependencies and set up the virtual environment:

```bash
uv sync
```

## CLI Tools

### 1. Domain Validator
Validates that an ADRIA Domain Data Package meets the required specifications.

**Usage:**
```bash
uv run validator <path_to_domain_directory>
```
Or directly via script:
```bash
uv run src/main.py <path_to_domain_directory>
```

**Checks Performed:**
1.  **Schema Validation**: Verifies `datapackage.json` against the expected Pydantic schema.
2.  **Resource Existence**: Checks that all files and folders listed in the `resources` block exist.
3.  **Naming Conventions**: Ensures the spatial GeoPackage filename matches the domain directory name.
4.  **Content Checks**: Validates NetCDF dimensions and coordinate variables (`locations`, `timesteps`, etc.), and checks that location IDs in NetCDF and connectivity CSV headers match the GeoPackage.

---

### 2. Strip Locations
Strips locations that have a carrying capacity ($k$) equal to `0.0` from all files in the domain.

**Usage:**
```bash
uv run strip-locations <path_to_domain_directory>
```
Or directly via script:
```bash
uv run src/strip_locations.py <path_to_domain_directory>
```

**Actions Performed:**
1.  Loads the spatial GeoPackage and reads the carrying capacity column (`k` by default) to identify locations with a value of `0.0`.
2.  Filters out matching locations from the GeoPackage.
3.  Filters the `locations` dimension of NetCDF files (e.g., DHW, cyclones, coral cover, waves).
4.  Filters matching rows and columns from connectivity CSV matrices.
5.  Saves updated files in-place and documents the removed location IDs under the `"removed_locations"` key in `datapackage.json`.

---

### 3. Clean Connectivity
Normalizes location IDs in the connectivity matrices by removing space characters.

**Usage:**
```bash
uv run clean-connectivity <path_to_domain_directory>
```
Or directly via script:
```bash
uv run src/clean_connectivity.py <path_to_domain_directory>
```

**Actions Performed:**
1.  Reads the row index and column headers of CSV files in the connectivity directory.
2.  Strips space characters (e.g., `Outer Flat` becomes `OuterFlat`) to match the canonical IDs used in the GeoPackage.
3.  Saves the updated CSV matrices in-place, preserving any comment headers.
4.  Documents that space cleaning was performed by setting `"connectivity_spaces_removed": true` in `datapackage.json`.

---

### 4. Align Connectivity
Aligns mismatched connectivity site names with the canonical location IDs from the spatial GeoPackage.

**Usage:**
```bash
uv run align-connectivity --map-json '<mapping_json>' <path_to_domain_directory>
```
Example:
```bash
uv run align-connectivity --map-json '{"89": "Lizard_14116A_OuterFlat_1f"}' /path/to/Lizard_domain
```
Or directly via script:
```bash
uv run src/align_connectivity.py --map-json '<mapping_json>' <path_to_domain_directory>
```

**Actions Performed:**
1.  Loads the spatial GeoPackage and reads the canonical location IDs (`reef_siteid`).
2.  Parses the JSON mapping (can map either indices or raw names to new canonical names).
3.  Validates that all target names exist in the spatial GeoPackage before applying changes.
4.  Scans and updates the row and column headers in connectivity CSV matrices in-place.
5.  Documents the clean, unique mapping dictionary under the `"aligned_connectivity_ids"` key in `datapackage.json`.

---

## Development

The project is managed with `uv`.

- To add a dependency: `uv add <package_name>`

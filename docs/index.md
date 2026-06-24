# ADRIA Domain Tools Documentation

This documentation provides details on the package specifications, validation workflow, and data modification tools within the `ADRIA-domain-tools` repository.

---

## 1. Domain Data Package Specification

An ADRIA Domain Data Package is a structured collection of spatial, environmental, and connectivity data configured for model simulations. A valid package must contain a `datapackage.json` metadata file at its root and follow the folder layout below:

```
<Domain_Directory>/
│   datapackage.json
│   README.md
│
├───DHWs/                # NetCDF files representing DHW projections
│
├───connectivity/        # CSV transfer probability matrices
│
├───cyclones/            # NetCDF files representing cyclone mortality
│
├───spatial/             # Geopackage and coral cover netCDF
│   │   MyDomain.gpkg
│   │   coral_cover.nc
│
└───waves/               # (Optional) NetCDF files representing wave stress
```

---

## 2. Validation Checks

The `validator` tool performs the following verification steps:

### Schema Validation
Verifies that `datapackage.json` contains all required fields (e.g., `name`, `title`, `version`, `resources`) and conforms to the defined schema.

### Resource Verification
Ensures that every resource listed in `datapackage.json` is physically present at the specified path (as a file or folder) inside the domain directory.

### Naming Conventions
Verifies that the spatial GeoPackage filename matches the domain directory name (e.g., directory `Davies_v080` must contain `spatial/Davies_v080.gpkg`).

### Content Alignment
*   **NetCDF Dimensions**: Checks that `dhw`, `coral_cover`, `cyclones`, and `waves` datasets contain the required dimensions (`locations`, `timesteps`, etc.) in the correct order.
*   **ID Mapping**: Extracts site IDs from the GeoPackage and confirms that they match the coordinate values in the NetCDF files and the row/column names in the connectivity CSV matrices.

---

## 3. Processing and Normalization Tools

These tools update domain files in-place to ensure consistency and prevent runtime warnings or errors during simulations.

### Strip Locations (`strip-locations`)
Some modeling workflows require the removal of locations that cannot support coral growth. This tool filters out sites with a carrying capacity ($k$) of `0.0`.
*   **GeoPackage Filter**: Removes matching geometries from the GeoPackage file.
*   **Dataset Propagation**: Drops the matching locations from the `locations` dimension of NetCDF files (DHW, coral cover, cyclones, waves).
*   **Matrix Reduction**: Removes the corresponding rows and columns from all connectivity CSV files.
*   **Metadata Logging**: Records the list of removed site IDs in the `removed_locations` field within `datapackage.json`.

### Clean Connectivity (`clean-connectivity`)
Raw connectivity datasets may contain location names formatted with spaces (e.g., `Outer Flat`), while spatial GeoPackages use space-stripped names (e.g., `OuterFlat`). This tool resolves name mismatches.
*   **Header Normalization**: Strips spaces from the row and column headers in connectivity CSV files.
*   **Metadata Logging**: Records the original site IDs that underwent space-stripping under the `normalized_connectivity_ids` field within `datapackage.json`.

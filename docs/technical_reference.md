# Technical Reference - Fishbone-QA-911

## Architecture Overview

The tool is implemented in two forms - an ArcGIS Notebook (`Fishbone_Notebook.ipynb`) and a Python Toolbox (`FishboneQA.pyt`) - both operating entirely within the ArcPy data access framework (`arcpy.da`). Both forms share identical core logic. The toolbox wraps that logic in a parameterized geoprocessing interface with input validation and progress messaging.

Execution follows a three-phase architecture:

1. **Matching phase** - reads civic and road data, writes QA results to a copy of the civic layer
2. **Line generation phase** - draws fishbone polylines for matched civic points
3. **Point generation phase** - writes unmatched civic points to a separate feature class

All road data is loaded into memory as Python dictionaries before any civic iteration begins. This eliminates repeated I/O and avoids the need for `MakeFeatureLayer` inside loops, which is both a performance bottleneck and a source of SQL compatibility issues with file geodatabases.

## Data Model

### Spatial Reference
All output feature classes inherit the spatial reference of the input civic layer at creation time via `arcpy.Describe(civic_fc).spatialReference`. No projection is performed at any stage - inputs are assumed to be in a consistent coordinate system.

### Geometry Operations
| Operation | Method | Notes |
|---|---|---|
| Civic-to-segment distance | `PointGeometry.distanceTo(Polyline)` | Returns planar distance in the CRS unit |
| Nearest point on segment | `Polyline.measureOnLine(Point)` + `Polyline.positionAlongLine(measure)` | Returns a `PointGeometry` along the segment |
| Line construction | `arcpy.Polyline(arcpy.Array([pt1, pt2]), spatial_reference)` | Two-vertex polyline |

## Memory Structures

### `road_lookup`
```
dict[str, list[tuple]]
key   → normalized street name (upper, stripped)
value → list of (OID, fL, tL, fR, tR, NAME_FULL, SHAPE@)
```
Built once from a full scan of the road layer. Used during the matching phase to retrieve all segments sharing a street name in O(1) time. Normalization is applied at build time so lookups require no repeated string operations.

### `road_detail_lookup`
```
dict[int, dict]
key   → road segment OBJECTID
value → {name_full, fL, tL, fR, tR, shape}
```
Built in the same scan as `road_lookup`. Used during line generation to retrieve road attributes and geometry by OID without opening a nested cursor. Keeping this separate from `road_lookup` avoids redundant tuple unpacking and keeps both structures purpose-specific.

## Matching Algorithm

For each civic point the matching logic proceeds as follows:
```
1. Normalize civic street name → uppercase, strip whitespace
2. Lookup road_lookup[street_name] → candidate list
3. For each candidate:
       in_left  = min(fL,tL) <= StreetNumber <= max(fL,tL)
       in_right = min(fR,tR) <= StreetNumber <= max(fR,tR)
       if in_left or in_right → add to matched[]
4. If matched is empty:
       MatchedSegmentOID = None
       RangeStatus = "OutOfRange"
5. If matched is non-empty:
       For each match compute distanceTo(civic_shape)
       Select match with minimum distance
       MatchedSegmentOID = winning OID
       RangeStatus = "WithinRange"
```

**Range check design notes:**
- `min/max` wrapping handles reversed ranges (where `F_Addr > T_Addr`) without requiring data pre-processing
- Range fields are cast to `float` at read time - cast failures are caught silently and the affected side is treated as `None`, excluding it from range checks without halting execution
- Tiebreaking by proximity is a deliberate design choice - odd/even side logic was not implemented as it would require knowledge of road directionality and odd/even conventions which adds complexity without meaningfully improving results for this use case

## Cursor Strategy

### Input Protection
The input civic layer is never opened with an `UpdateCursor`. Instead it is copied to the output GDB using `CopyFeatures_management` and all write operations are performed on the copy. The road layer is opened with `SearchCursor` only.

### Why Two Passes for Output Generation
ArcGIS file geodatabases do not support concurrent write transactions on the same workspace. Opening two `InsertCursor` objects simultaneously against the same GDB triggers a `RuntimeError: workspace already in transaction mode`. Output generation is therefore split into two sequential passes:

- **Pass 1** - `SearchCursor` on `Civic_QA_Result` + `InsertCursor` on `Fishbone_Lines`
- **Pass 2** - `SearchCursor` on `Civic_QA_Result` + `InsertCursor` on `Fishbone_OutOfRange`

Each pass opens exactly one write cursor against the GDB, satisfying the single-transaction constraint.

### Cursor Types Used
| Cursor | Target | Purpose |
|---|---|---|
| `SearchCursor` | Road layer | Build `road_lookup` and `road_detail_lookup` |
| `UpdateCursor` | `Civic_QA_Result` | Write `MatchedSegmentOID` and `RangeStatus` |
| `SearchCursor` | `Civic_QA_Result` | Read civic data for output generation (×2 passes) |
| `InsertCursor` | `Fishbone_Lines` | Write matched fishbone lines |
| `InsertCursor` | `Fishbone_OutOfRange` | Write unmatched civic points |

All cursors are opened using context managers (`with` blocks) to guarantee release on error or completion.

## Output Feature Class Construction

Both output feature classes are deleted and recreated on every run via `arcpy.Exists()` + `arcpy.Delete_management()` before `arcpy.CreateFeatureclass_management()`. This ensures schema consistency across re-runs and avoids append conflicts.

Fields are added individually after creation using `arcpy.AddField_management()`. The `field_length` argument is passed only for `TEXT` fields - numeric fields omit this parameter to avoid type coercion warnings.

## Performance Characteristics

| Operation | Complexity | Notes |
|---|---|---|
| Road dictionary build | O(n) | Single full scan of road layer |
| Civic matching loop | O(c × k) | c = civic count, k = avg segments per street name |
| Nearest segment selection | O(k) per civic point | k is typically very small (1–5) |
| Line generation pass | O(c) | One geometry operation per matched civic point |
| OutOfRange pass | O(c) | Point copy only, no geometry construction |

The matching loop dominates runtime. The dictionary-based approach is substantially faster than the alternative of calling `MakeFeatureLayer` with a SQL filter per civic point, which would incur geoprocessing overhead on every iteration.

## Error Handling

| Condition | Behaviour |
|---|---|
| `StreetName` is `None` | `RangeStatus = "NoData"`, point written to `Fishbone_OutOfRange` |
| `StreetNumber` is `None` | `RangeStatus = "NoData"`, point written to `Fishbone_OutOfRange` |
| Range field cast to float fails | That side's range treated as `None`, excluded from check silently |
| Road OID not in `road_detail_lookup` | Civic point skipped in line generation pass |
| Civic point has no geometry | Skipped in both output passes |
| Street name not in `road_lookup` | Returns empty candidate list, civic flagged `OutOfRange` |

No exceptions are raised for data quality issues - all error conditions are handled defensively to allow the tool to run to completion across an entire dataset without interruption.

## Known Constraints and Limitations

- **Single workspace constraint** - both output feature classes must reside in the same GDB. Output generation is split into two sequential cursor passes to comply with the ArcGIS file GDB single-transaction rule.
- **Planar distance only** - `distanceTo` computes planar (Euclidean) distance. For datasets in geographic coordinate systems (decimal degrees) this may produce inaccurate proximity results. A projected coordinate system is strongly recommended.
- **No odd/even parity check** - the tool does not enforce whether a civic number should fall on the left or right side of the road. Both sides are checked inclusively.
- **Exact name matching only** - normalization handles case and whitespace but not abbreviation variants. Street name standardization should be applied to both datasets upstream of this tool.
- **In-memory road dictionary** - for very large road datasets the dictionary structures may consume significant memory. This has not been observed as an issue at typical municipal dataset scales.

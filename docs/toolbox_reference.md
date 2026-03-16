# Toolbox Reference - Fishbone-QA-911

## Overview

`FishboneQA.pyt` is an ArcGIS Pro Python Toolbox containing a single tool - **Civic to Road Fishbone QA - Enhanced**. It exposes the full Fishbone-QA-911 logic with enhanced parity validation as a standard geoprocessing tool with a parameter dialog, field dropdowns, input validation, and progress messaging in the Geoprocessing pane.

**Enhanced Features:**
- Automatic odd/even parity-based matching
- Detection of addresses on wrong side of street
- Road segment range quality validation
- Optional street name component parsing (pre/post-directional)

## Installation

1. Clone or download the repository
2. Open ArcGIS Pro and navigate to the **Catalog** pane
3. Right-click **Toolboxes** → **Add Toolbox**
4. Browse to `FishboneQA.pyt` and select it
5. The toolbox appears in the Catalog pane and the tool is ready to run

To make the toolbox permanently available across all projects, right-click it in the Catalog pane and select **Add To Favorites**.

## Parameters

### Required Parameters

| # | Parameter | Type | Required | Description |
|---|---|---|---|---|
| 0 | Civic Address Layer | Feature Layer | Yes | Input civic point layer - never modified |
| 1 | Civic - Street Name Field | Field | Yes | Text field containing the civic street name |
| 2 | Civic - Street Number Field | Field | Yes | Numeric field containing the civic address number |
| 3 | Road Segment Layer | Feature Layer | Yes | Input road polyline layer - never modified |
| 4 | Road - Street Name Field | Field | Yes | Text field containing the road full name |
| 5 | Road - From Address Left Field | Field | Yes | From address range, left side |
| 6 | Road - To Address Left Field | Field | Yes | To address range, left side |
| 7 | Road - From Address Right Field | Field | Yes | From address range, right side |
| 8 | Road - To Address Right Field | Field | Yes | To address range, right side |
| 9 | Output Geodatabase | Workspace | Yes | File GDB where all outputs will be written |

### Enhanced Optional Parameters

| # | Parameter | Type | Default | Description |
|---|---|---|---|---|
| 10 | Enable Address Parity Validation | Boolean | True | Validate odd/even address patterns and match to correct side |

### Field Dropdowns
Field parameters are dynamically populated based on the layer selected in their parent parameter:
- Street name fields show **Text** fields only
- Street number fields show **Short, Long, Double, Single** fields only
- Address range fields show all field types since they are commonly stored as text in 911 datasets

### Output Geodatabase
Defaults to the current ArcGIS Pro project's default geodatabase. Can be pointed to any existing file geodatabase. The tool will not create the GDB if it does not exist - it must be created beforehand.

## Validation

The tool performs the following checks before execution begins:

| Check | Behaviour |
|---|---|
| Civic layer geometry type | Must be **Point** - error shown in dialog if not |
| Road layer geometry type | Must be **Polyline** - error shown in dialog if not |
| Output GDB exists | Must exist before running - tool errors if path is invalid |
| Field dropdowns | Filtered by type to prevent incompatible field selection |
| Directional field parameters | Enabled only when parsing is enabled (parameter 11) |

## Execution Flow

Each stage is reported in the Geoprocessing messages pane:

1. **Copy civic layer** - input civic layer is copied to `Civic_QA_Result` in the output GDB and QA fields are added to the copy
2. **Build road lookup** - all road segments are read into two in-memory dictionaries; road ranges are validated for parity consistency
3. **Match civic points** - each civic point is matched to its road segment using **parity-preference matching** (addresses match to correct odd/even side first)
4. **Create output feature classes** - `Fishbone_Lines`, `Fishbone_OutOfRange`, and `Road_QA_Issues` are created fresh in the output GDB
5. **Pass 1 - Draw fishbone lines** - matched civic points are connected to their road segments
6. **Pass 2 - Write OutOfRange points** - unmatched civic points are written to `Fishbone_OutOfRange`
7. **Pass 3 - Write Road QA Issues** - road segments with range problems are written to `Road_QA_Issues` (if any found)

## Enhanced Matching Logic

### Parity-Preference Matching (when enabled)

The tool uses **parity-first** matching when Address Parity Validation is enabled:

1. **Find all ranges** containing the address number
2. **Filter by parity**: Prefer ranges where address parity (odd/even) matches range parity
3. **Pick closest**: Among parity-matched candidates, select the nearest segment
4. **Fallback**: If no parity match exists, use closest of any range and flag as mismatch

**Example:**
```
Address 1084 (EVEN number)
Road Segment:
  Left Range:  1001-1151 (ODD parity)
  Right Range: 1000-1152 (EVEN parity)

Result: Matches to RIGHT range (EVEN matches EVEN)
Even if point is slightly closer to left geometrically
```

This ensures addresses automatically match to their correct odd/even side, preventing false positives.

## Outputs

All outputs are written to the specified output geodatabase. Existing outputs are deleted and recreated on each run.

### Civic_QA_Result (Point)

| Field | Type | Description |
|---|---|---|
| *(all original fields)* | - | Carried over from input civic layer |
| `MatchedSegmentOID` | Long | OBJECTID of the matched road segment |
| `RangeStatus` | Text (30) | `WithinRange`, `OutOfRange`, or `NoData` |
| `MatchedSide` | Text (10) | `LEFT` or `RIGHT` - which range side was matched |
| `AddressParity` | Text (10) | `EVEN` or `ODD` - parity of the address number *(when parity validation enabled)* |
| `RangeParity` | Text (10) | `EVEN`, `ODD`, or `MIXED` - parity of the matched range *(when parity validation enabled)* |
| `ParityMatch` | Text (20) | `MATCH` or `MISMATCH` - whether parity is correct *(when parity validation enabled)* |

### Fishbone_Lines (Polyline)

| Field | Type | Description |
|---|---|---|
| `CivicOID` | Long | OBJECTID of the source civic point |
| `RoadOID` | Long | OBJECTID of the matched road segment |
| `RangeStatus` | Text (30) | Always `WithinRange` in this layer |
| `RoadName` | Text (100) | Road name from the selected road name field |
| `CivicNumber` | Double | Civic street number |
| `MatchedRange` | Text (50) | Address range with parity e.g. `L:100-200 (EVEN) R:101-199 (ODD)` |
| `MatchedSide` | Text (10) | Which side was matched (`LEFT` or `RIGHT`) |
| `AddressParity` | Text (10) | Parity of address *(when parity validation enabled)* |
| `RangeParity` | Text (10) | Parity of matched range *(when parity validation enabled)* |
| `ParityMatch` | Text (20) | Match status *(when parity validation enabled)* |

### Fishbone_OutOfRange (Point)

| Field | Type | Description |
|---|---|---|
| `CivicOID` | Long | OBJECTID of the source civic point |
| `StreetName` | Text (100) | Street name from the selected civic name field |
| `CivicNumber` | Double | Civic street number |
| `RangeStatus` | Text (30) | `OutOfRange` or `NoData` |
| `AddressParity` | Text (10) | Parity of address *(when parity validation enabled)* |

### Road_QA_Issues (Polyline) - NEW

This layer is only created when issues are detected in road segment ranges.

| Field | Type | Description |
|---|---|---|
| `RoadOID` | Long | OBJECTID of the road segment |
| `RoadName` | Text (100) | Road name |
| `Issue` | Text (200) | Description of the problem |
| `FromLeft` | Double | From address left side |
| `ToLeft` | Double | To address left side |
| `FromRight` | Double | From address right side |
| `ToRight` | Double | To address right side |

**Common Issues Detected:**
- "Left range: From and To addresses are identical"
- "Right range: Unusually large range gap: 10250"
- "Left range parity: Mixed parity range: 100 (EVEN) to 199 (ODD)"

## Enhanced Statistics Output

The tool reports comprehensive statistics in the Geoprocessing messages:

```
MATCHING STATISTICS:
  Total civic points: 10000
  Within range: 9500
  Out of range: 450
  No data: 50
  Parity mismatches (odd/even): 15
```

## Re-running the Tool

The tool is fully safe to re-run. On each execution all outputs are deleted and rebuilt from scratch. The original input layers are never altered at any point. Correct your source data and re-run - no manual cleanup is needed between runs.

## Using in ModelBuilder

The tool can be added to a ModelBuilder model like any standard geoprocessing tool. All parameters are exposed and connectable. The output feature classes can be referenced by downstream tools in the model using their full paths.

## Calling from a Script

```python
import arcpy

arcpy.ImportToolbox(r"C:\path\to\FishboneQA.pyt")

# Basic usage (parity validation enabled by default)
arcpy.FishboneQA.FishboneQATool(
    civic_fc        = r"C:\path\to\data.gdb\Civic_Points",
    civic_name_field= "StreetName",
    civic_num_field = "StreetNumber",
    road_fc         = r"C:\path\to\data.gdb\Road_Segments",
    road_name_field = "NAME_FULL",
    road_fL_field   = "F_Addr_L_911",
    road_tL_field   = "T_Addr_L_911",
    road_fR_field   = "F_Addr_R_911",
    road_tR_field   = "T_Addr_R_911",
    out_gdb         = r"C:\path\to\output.gdb",
    enable_parity_check = True  # Optional, default is True
)

# With parity validation disabled
arcpy.FishboneQA.FishboneQATool(
    civic_fc        = r"C:\path\to\data.gdb\Civic_Points",
    civic_name_field= "StreetName",
    civic_num_field = "StreetNumber",
    road_fc         = r"C:\path\to\data.gdb\Road_Segments",
    road_name_field = "NAME_FULL",
    road_fL_field   = "F_Addr_L_911",
    road_tL_field   = "T_Addr_L_911",
    road_fR_field   = "F_Addr_R_911",
    road_tR_field   = "T_Addr_R_911",
    out_gdb         = r"C:\path\to\output.gdb",
    enable_parity_check = False  # Disable for sequential numbering
)
```

## Symbology Recommendations

### Fishbone_Lines
- **Symbolize by `ParityMatch`:**
  - `MATCH` = Thin green line (correct addresses)
  - `MISMATCH` = Thick red line (wrong-side addresses)
- **Alternative:** Symbolize by line length to identify unusually long fishbones
- Label with `CivicNumber`, `MatchedRange`, and `ParityMatch` for full context

### Fishbone_OutOfRange
- Apply a bold circle marker, red or orange
- Label with `CivicNumber` and `StreetName` to identify problem records without clicking

### Road_QA_Issues
- Apply bold red or magenta line symbology
- Label with `Issue` field to show problem description
- Review and fix these segments before re-running civic QA

## Troubleshooting

| Issue | Likely Cause | Fix |
|---|---|---|
| Field dropdowns are empty | Wrong layer type selected or layer not loaded in map | Confirm the layer is loaded in the current map and is the correct geometry type |
| Tool errors on output GDB | GDB does not exist | Create the file GDB manually before running |
| All civics returning `OutOfRange` | Street name fields do not match between layers | Check naming conventions and run normalization upstream if needed |
| Many parity mismatches | Road ranges have incorrect parity patterns | Check `Road_QA_Issues` layer for range problems; update road data |
| All addresses on one side show MISMATCH | Bug in older version | Ensure using latest version with parity-preference matching |
| Tool errors mid-run on geometry | Null geometries in input layers | Run **Check Geometry** and **Repair Geometry** on both inputs before running |
| `Fishbone_Lines` is empty | No civic points matched any road segment | Verify correct fields are selected and both layers share the same coordinate system |

## Known Limitations

- **Exact name matching only** - normalization handles case and whitespace but not abbreviation variants. Pre-normalize street names in both datasets upstream of this tool.
- **Planar distance only** - a projected coordinate system is strongly recommended.
- **Parity validation assumes standard addressing** - if your jurisdiction uses sequential numbering (1,2,3,4...) on one side, disable parity validation.
- **Output GDB must be a file GDB** - enterprise geodatabases and in-memory workspaces are not supported as output targets.
- **Single workspace write constraint** - output generation is split into sequential passes to comply with the ArcGIS file GDB single-transaction rule.

## Version Notes

**v2.0 - Enhanced (Current)**
- Added parity-preference matching (matches to correct odd/even side first)
- Added address parity validation fields
- Added road range quality validation
- Added `Road_QA_Issues` output layer
- Enhanced statistics reporting

**v1.0 - Original**
- Basic range matching
- Distance-based tiebreaking only
- No parity validation

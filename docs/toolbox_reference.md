# Toolbox Reference - Fishbone-QA-911

## Overview

`FishboneQA.pyt` is an ArcGIS Pro Python Toolbox containing a single tool - **Civic to Road Fishbone QA**. It exposes the full Fishbone-QA-911 logic as a standard geoprocessing tool with a parameter dialog, field dropdowns, input validation, and progress messaging in the Geoprocessing pane.

## Installation

1. Clone or download the repository
2. Open ArcGIS Pro and navigate to the **Catalog** pane
3. Right-click **Toolboxes** → **Add Toolbox**
4. Browse to `FishboneQA.pyt` and select it
5. The toolbox appears in the Catalog pane and the tool is ready to run

To make the toolbox permanently available across all projects, right-click it in the Catalog pane and select **Add To Favorites**.

## Parameters

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

## Execution Flow

Each stage is reported in the Geoprocessing messages pane:

1. **Copy civic layer** - input civic layer is copied to `Civic_QA_Result` in the output GDB and QA fields are added to the copy
2. **Build road lookup** - all road segments are read into two in-memory dictionaries keyed by street name and OBJECTID respectively
3. **Match civic points** - each civic point is matched to its road segment and results written back to the copy
4. **Create output feature classes** - `Fishbone_Lines` and `Fishbone_OutOfRange` are created fresh in the output GDB
5. **Pass 1 - Draw fishbone lines** - matched civic points are connected to their road segments
6. **Pass 2 - Write OutOfRange points** - unmatched civic points are written to `Fishbone_OutOfRange`

## Outputs

All outputs are written to the specified output geodatabase. Existing outputs are deleted and recreated on each run.

### Civic_QA_Result (Point)
| Field | Type | Description |
|---|---|---|
| *(all original fields)* | - | Carried over from input civic layer |
| `MatchedSegmentOID` | Long | OBJECTID of the matched road segment |
| `RangeStatus` | Text (20) | `WithinRange`, `OutOfRange`, or `NoData` |

### Fishbone_Lines (Polyline)
| Field | Type | Description |
|---|---|---|
| `CivicOID` | Long | OBJECTID of the source civic point |
| `RoadOID` | Long | OBJECTID of the matched road segment |
| `RangeStatus` | Text (20) | Always `WithinRange` in this layer |
| `RoadName` | Text (100) | Road name from the selected road name field |
| `CivicNumber` | Double | Civic street number |
| `MatchedRange` | Text (50) | Address range of matched segment e.g. `L:100-200 R:101-201` |

### Fishbone_OutOfRange (Point)
| Field | Type | Description |
|---|---|---|
| `CivicOID` | Long | OBJECTID of the source civic point |
| `StreetName` | Text (100) | Street name from the selected civic name field |
| `CivicNumber` | Double | Civic street number |
| `RangeStatus` | Text (20) | `OutOfRange` or `NoData` |

## Re-running the Tool

The tool is fully safe to re-run. On each execution all three outputs are deleted and rebuilt from scratch. The original input layers are never altered at any point. Correct your source data and re-run - no manual cleanup is needed between runs.

## Using in ModelBuilder

The tool can be added to a ModelBuilder model like any standard geoprocessing tool. All nine parameters are exposed and connectable. The three output feature classes (`Civic_QA_Result`, `Fishbone_Lines`, `Fishbone_OutOfRange`) are written directly to the output GDB and can be referenced by downstream tools in the model using their full paths.

## Calling from a Script
```python
import arcpy

arcpy.ImportToolbox(r"C:\path\to\FishboneQA.pyt")

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
    out_gdb         = r"C:\path\to\output.gdb"
)
```

## Symbology Recommendations

### Fishbone_Lines
- Symbolize by `RangeStatus` - a thin green line works well
- Label with `RoadName`, `CivicNumber`, and `MatchedRange` for full inline context at street scale

### Fishbone_OutOfRange
- Apply a bold circle marker, red or orange
- Label with `CivicNumber` and `StreetName` to identify problem records without clicking

## Troubleshooting

| Issue | Likely Cause | Fix |
|---|---|---|
| Field dropdowns are empty | Wrong layer type selected or layer not loaded in map | Confirm the layer is loaded in the current map and is the correct geometry type |
| Tool errors on output GDB | GDB does not exist | Create the file GDB manually before running |
| All civics returning `OutOfRange` | Street name fields do not match between layers | Check naming conventions and run normalization upstream if needed |
| Tool errors mid-run on geometry | Null geometries in input layers | Run **Check Geometry** and **Repair Geometry** on both inputs before running |
| `Fishbone_Lines` is empty | No civic points matched any road segment | Verify correct fields are selected and both layers share the same coordinate system |

## Known Limitations

- **Exact name matching only** - normalization handles case and whitespace but not abbreviation variants. Pre-normalize street names in both datasets upstream of this tool.
- **Planar distance only** - a projected coordinate system is strongly recommended.
- **No odd/even parity enforcement** - both left and right ranges are checked inclusively.
- **Output GDB must be a file GDB** - enterprise geodatabases and in-memory workspaces are not supported as output targets.
- **Single workspace write constraint** - output generation is split into two sequential passes to comply with the ArcGIS file GDB single-transaction rule.

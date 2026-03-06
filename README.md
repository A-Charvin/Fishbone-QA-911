# Fishbone QA 911
ArcGIS Pro geoprocessing tool for validating civic address points against road segment address ranges - built for NG911 dataset QAQC.

## What It Does
In a 911 address database, every civic address point should fall within the address range of its corresponding road segment. Fishbone QA 911 automatically checks every civic point against its road's address ranges, flags mismatches, and visualizes the results as a fishbone diagram directly in ArcGIS Pro.

**Matched points** get a line drawn from the civic point to its road segment - when you zoom out these look like fish bones branching off the road, making it immediately obvious where addresses sit relative to their street.

**Unmatched points** are written to a separate layer so problem addresses are isolated and easy to find.

## Outputs

| Output | Type | Description |
|---|---|---|
| `Civic_QA_Result` | Point | Copy of input civic layer with QA fields appended |
| `Fishbone_Lines` | Polyline | One line per matched civic point to its road segment |
| `Fishbone_OutOfRange` | Point | Civic points with no valid road range match |

> The original input data is never modified. All outputs are written to a user-specified file geodatabase.

## Requirements

- ArcGIS Pro 3.x or later
- ArcPy (included with ArcGIS Pro)
- A file geodatabase containing civic address points and road segments
- No additional Python packages required

## Installation

1. Clone or download this repository
```bash
git clone https://github.com/A-Charvin/Fishbone-QA-911.git
```
2. Open ArcGIS Pro and go to the **Catalog** pane
3. Right-click **Toolboxes** → **Add Toolbox**
4. Browse to `FishboneQA.pyt` and add it
5. The tool will appear in your Catalog under Toolboxes

## Usage

### As a Geoprocessing Tool (Recommended)
1. Open the toolbox in the Catalog pane
2. Double-click **Civic to Road Fishbone QA**
3. Fill in the parameters:
   - Point to your civic address layer and road segment layer
   - Select the appropriate fields from the dropdowns
   - Choose an output file geodatabase
4. Click Run

### As a Notebook
A standalone notebook version (`Fishbone_Notebook.ipynb`) is included for direct use in ArcGIS Notebooks if you prefer to run and modify the logic interactively.

## Input Data Requirements

### Civic Address Layer (Point)
| Field | Type | Description |
|---|---|---|
| Street Name | Text | Name of the street the address belongs to |
| Street Number | Numeric | The civic address number |

### Road Segment Layer (Polyline)
| Field | Type | Description |
|---|---|---|
| Street Name | Text | Full road name - should match civic street names |
| From Address Left | Text or Numeric | Start of address range, left side |
| To Address Left | Text or Numeric | End of address range, left side |
| From Address Right | Text or Numeric | Start of address range, right side |
| To Address Right | Text or Numeric | End of address range, right side |

> Field names do not need to match exactly - you select them from dropdowns when running the tool.

## How It Works
1. All road segments are loaded into memory and indexed by street name
2. Each civic point is looked up against that index by name
3. Candidate segments are filtered to those whose address range contains the civic number
4. If multiple candidates exist, the nearest one by straight-line distance is selected
5. Results are written to a copy of the civic layer - the original is never touched
6. Fishbone lines and OutOfRange points are generated as separate outputs

For a full explanation of the concept and methodology see the [Plain Language Guide](docs/plain_language_guide.md).
For technical implementation details see the [Technical Reference](docs/technical_reference.md).
For toolbox parameter and deployment details see the [Toolbox Reference](docs/toolbox_reference.md).

## Symbology Tips
- Symbolize `Fishbone_Lines` with a **green line** for clean at-a-glance QA
- Symbolize `Fishbone_OutOfRange` with a **bold red circle marker** to make problem addresses stand out
- Label fishbone lines with `RoadName + CivicNumber + MatchedRange` for full inline context at street scale

## Known Limitations
- Street name matching is exact after case and whitespace normalization - abbreviation differences such as `ST` vs `STREET` will cause missed matches. Pre-normalize your data for best results.
- Distance tiebreaking is planar - a projected coordinate system is strongly recommended.
- Output target must be a file geodatabase - enterprise geodatabases are not currently supported.

## Documentation
Full documentation is available in the [`docs/`](docs/) folder:

| Document | Description |
|---|---|
| [Plain Language Guide](docs/plain_language_guide.md) | Concept, methodology, and how to read the outputs - written for all skill levels |
| [Technical Reference](docs/technical_reference.md) | Architecture, algorithm, cursor strategy, and performance characteristics |
| [Toolbox Reference](docs/toolbox_reference.md) | Parameters, validation, deployment, and troubleshooting for the `.pyt` tool |

## Contributing
Contributions are welcome. If you work in 911 GIS or municipal addressing and have suggestions for improving the matching logic, adding odd/even parity checks, or supporting enterprise geodatabases, feel free to open an issue or submit a pull request.

## License
MIT License - free to use, modify, and distribute. Attribution appreciated but not required.

## Author
Developed for NG911 address data QAQC at Frontenac County, Ontario, Canada.
If you use or adapt this tool for your own municipality, feel free to open a discussion - it's always good to hear how it's being used in the field.

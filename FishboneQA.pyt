import arcpy
import os


class Toolbox:
    def __init__(self):
        self.label = "Civic QA Fishbone Toolbox"
        self.alias = "FishboneQA"
        self.tools = [FishboneQATool]


class FishboneQATool:
    def __init__(self):
        self.label = "Civic to Road Fishbone QA"
        self.description = (
            "Matches civic address points to road segments by street name and address range. "
            "Outputs fishbone lines for matched points and a separate layer for unmatched points."
        )
        self.canRunInBackground = False

    # ------------------------------------------------------------------
    # Parameter definitions
    # ------------------------------------------------------------------
    def getParameterInfo(self):
        # 0 - Civic input layer
        p_civic = arcpy.Parameter(
            displayName="Civic Address Layer",
            name="civic_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        # 1 - Civic: StreetName field
        p_civic_name = arcpy.Parameter(
            displayName="Civic - Street Name Field",
            name="civic_name_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_civic_name.parameterDependencies = ["civic_fc"]
        p_civic_name.filter.list = ["Text"]

        # 2 - Civic: StreetNumber field
        p_civic_num = arcpy.Parameter(
            displayName="Civic - Street Number Field",
            name="civic_num_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_civic_num.parameterDependencies = ["civic_fc"]
        p_civic_num.filter.list = ["Short", "Long", "Double", "Single"]

        # 3 - Road input layer
        p_road = arcpy.Parameter(
            displayName="Road Segment Layer",
            name="road_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        # 4 - Road: Name field
        p_road_name = arcpy.Parameter(
            displayName="Road - Street Name Field",
            name="road_name_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_road_name.parameterDependencies = ["road_fc"]
        p_road_name.filter.list = ["Text"]

        # 5 - Road: F_Addr_L
        p_fL = arcpy.Parameter(
            displayName="Road - From Address Left Field",
            name="road_fL_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_fL.parameterDependencies = ["road_fc"]

        # 6 - Road: T_Addr_L
        p_tL = arcpy.Parameter(
            displayName="Road - To Address Left Field",
            name="road_tL_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_tL.parameterDependencies = ["road_fc"]

        # 7 - Road: F_Addr_R
        p_fR = arcpy.Parameter(
            displayName="Road - From Address Right Field",
            name="road_fR_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_fR.parameterDependencies = ["road_fc"]

        # 8 - Road: T_Addr_R
        p_tR = arcpy.Parameter(
            displayName="Road - To Address Right Field",
            name="road_tR_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_tR.parameterDependencies = ["road_fc"]

        # 9 - Output GDB
        p_out_gdb = arcpy.Parameter(
            displayName="Output Geodatabase",
            name="out_gdb",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
        )
        p_out_gdb.filter.list = ["Local Database"]
        # Default to project default GDB
        p_out_gdb.defaultEnvironmentName = "workspace"

        return [
            p_civic, p_civic_name, p_civic_num,
            p_road, p_road_name,
            p_fL, p_tL, p_fR, p_tR,
            p_out_gdb
        ]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        # Validate civic layer is a point layer
        if parameters[0].altered and not parameters[0].hasError():
            desc = arcpy.Describe(parameters[0].valueAsText)
            if desc.shapeType != "Point":
                parameters[0].setErrorMessage("Civic layer must be a Point feature class.")

        # Validate road layer is a polyline layer
        if parameters[3].altered and not parameters[3].hasError():
            desc = arcpy.Describe(parameters[3].valueAsText)
            if desc.shapeType != "Polyline":
                parameters[3].setErrorMessage("Road layer must be a Polyline feature class.")

        return

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------
    def execute(self, parameters, messages):
        # Unpack parameters
        civic_fc        = parameters[0].valueAsText
        civic_name_fld  = parameters[1].valueAsText
        civic_num_fld   = parameters[2].valueAsText
        road_fc         = parameters[3].valueAsText
        road_name_fld   = parameters[4].valueAsText
        fL_fld          = parameters[5].valueAsText
        tL_fld          = parameters[6].valueAsText
        fR_fld          = parameters[7].valueAsText
        tR_fld          = parameters[8].valueAsText
        out_gdb         = parameters[9].valueAsText

        # Output paths
        civic_result  = os.path.join(out_gdb, "Civic_QA_Result")
        output_lines  = os.path.join(out_gdb, "Fishbone_Lines")
        output_oor    = os.path.join(out_gdb, "Fishbone_OutOfRange")

        sr = arcpy.Describe(civic_fc).spatialReference

        # ------------------------------------------------------------------
        # Copy civic layer to output GDB - inputs are never modified
        # ------------------------------------------------------------------
        messages.addMessage("Copying civic layer to output GDB...")
        if arcpy.Exists(civic_result):
            arcpy.Delete_management(civic_result)
        arcpy.CopyFeatures_management(civic_fc, civic_result)

        # Add QA fields to the COPY only
        arcpy.AddField_management(civic_result, "MatchedSegmentOID", "LONG")
        arcpy.AddField_management(civic_result, "RangeStatus", "TEXT", field_length=20)

        # ------------------------------------------------------------------
        # Build road lookup dictionary
        # ------------------------------------------------------------------
        messages.addMessage("Building road lookup dictionary...")
        road_fields = ["OBJECTID", road_name_fld, fL_fld, tL_fld, fR_fld, tR_fld, "SHAPE@"]
        road_lookup = {}
        road_detail_lookup = {}

        with arcpy.da.SearchCursor(road_fc, road_fields) as cur:
            for r in cur:
                oid      = r[0]
                name     = r[1].upper().strip() if r[1] else None
                try:
                    fL, tL = float(r[2]), float(r[3])
                except:
                    fL = tL = None
                try:
                    fR, tR = float(r[4]), float(r[5])
                except:
                    fR = tR = None
                shp = r[6]

                if name:
                    entry = (oid, fL, tL, fR, tR, r[1], shp)
                    road_lookup.setdefault(name, []).append(entry)

                road_detail_lookup[oid] = {
                    "name_full": r[1],
                    "fL": fL, "tL": tL,
                    "fR": fR, "tR": tR,
                    "shape": shp
                }

        messages.addMessage(f"Road lookup built: {len(road_lookup)} unique street names.")

        # ------------------------------------------------------------------
        # Matching loop - operates on the COPY
        # ------------------------------------------------------------------
        messages.addMessage("Matching civic points to road segments...")
        civic_fields = ["OBJECTID", civic_name_fld, civic_num_fld, "MatchedSegmentOID", "RangeStatus", "SHAPE@"]

        with arcpy.da.UpdateCursor(civic_result, civic_fields) as cur:
            for row in cur:
                street_num  = row[2]
                street_name = row[1].upper().strip() if row[1] else None

                if street_name is None or street_num is None:
                    row[3] = None
                    row[4] = "NoData"
                    cur.updateRow(row)
                    continue

                candidates = road_lookup.get(street_name, [])
                matched = []

                for (oid, fL, tL, fR, tR, name_full, shp) in candidates:
                    in_left  = fL is not None and tL is not None and min(fL, tL) <= street_num <= max(fL, tL)
                    in_right = fR is not None and tR is not None and min(fR, tR) <= street_num <= max(fR, tR)
                    if in_left or in_right:
                        matched.append((oid, fL, tL, fR, tR, name_full, shp))

                if not matched:
                    row[3] = None
                    row[4] = "OutOfRange"
                else:
                    civic_shp = row[-1]
                    min_dist  = None
                    matched_oid = None
                    for (oid, fL, tL, fR, tR, name_full, shp) in matched:
                        dist = civic_shp.distanceTo(shp)
                        if min_dist is None or dist < min_dist:
                            min_dist = dist
                            matched_oid = oid
                    row[3] = matched_oid
                    row[4] = "WithinRange"

                cur.updateRow(row)

        messages.addMessage("Matching complete.")

        # ------------------------------------------------------------------
        # Create Fishbone_Lines
        # ------------------------------------------------------------------
        messages.addMessage("Creating Fishbone_Lines...")
        if arcpy.Exists(output_lines):
            arcpy.Delete_management(output_lines)

        arcpy.CreateFeatureclass_management(
            out_path=os.path.dirname(output_lines),
            out_name=os.path.basename(output_lines),
            geometry_type="POLYLINE",
            spatial_reference=sr
        )

        for fname, ftype, flength in [
            ("CivicOID",     "LONG",   None),
            ("RoadOID",      "LONG",   None),
            ("RangeStatus",  "TEXT",   20),
            ("RoadName",     "TEXT",   100),
            ("CivicNumber",  "DOUBLE", None),
            ("MatchedRange", "TEXT",   50),
        ]:
            kwargs = {"field_length": flength} if flength else {}
            arcpy.AddField_management(output_lines, fname, ftype, **kwargs)

        # ------------------------------------------------------------------
        # Create Fishbone_OutOfRange
        # ------------------------------------------------------------------
        messages.addMessage("Creating Fishbone_OutOfRange...")
        if arcpy.Exists(output_oor):
            arcpy.Delete_management(output_oor)

        arcpy.CreateFeatureclass_management(
            out_path=os.path.dirname(output_oor),
            out_name=os.path.basename(output_oor),
            geometry_type="POINT",
            spatial_reference=sr
        )

        for fname, ftype, flength in [
            ("CivicOID",    "LONG",   None),
            ("StreetName",  "TEXT",   100),
            ("CivicNumber", "DOUBLE", None),
            ("RangeStatus", "TEXT",   20),
        ]:
            kwargs = {"field_length": flength} if flength else {}
            arcpy.AddField_management(output_oor, fname, ftype, **kwargs)

        # ------------------------------------------------------------------
        # Pass 1 - Fishbone lines
        # ------------------------------------------------------------------
        messages.addMessage("Drawing fishbone lines...")
        result_fields = ["OBJECTID", civic_name_fld, civic_num_fld, "SHAPE@", "MatchedSegmentOID", "RangeStatus"]
        line_fields   = ["SHAPE@", "CivicOID", "RoadOID", "RangeStatus", "RoadName", "CivicNumber", "MatchedRange"]

        with arcpy.da.SearchCursor(civic_result, result_fields) as civic_cur, \
             arcpy.da.InsertCursor(output_lines, line_fields) as line_cur:

            for civ_oid, civ_street, civ_num, civ_shp, seg_oid, status in civic_cur:
                if civ_shp is None or status in ("OutOfRange", "NoData") or seg_oid is None:
                    continue

                road = road_detail_lookup.get(seg_oid)
                if road is None:
                    continue

                range_str = ""
                if road["fL"] is not None and road["tL"] is not None:
                    lo, hi = int(min(road["fL"], road["tL"])), int(max(road["fL"], road["tL"]))
                    range_str = f"L:{lo}-{hi}"
                if road["fR"] is not None and road["tR"] is not None:
                    lo, hi = int(min(road["fR"], road["tR"])), int(max(road["fR"], road["tR"]))
                    range_str += f" R:{lo}-{hi}" if range_str else f"R:{lo}-{hi}"

                civic_pt   = civ_shp.centroid
                road_shp   = road["shape"]
                nearest_pt = road_shp.positionAlongLine(road_shp.measureOnLine(civic_pt))

                line_geom = arcpy.Polyline(
                    arcpy.Array([civic_pt, nearest_pt.firstPoint]),
                    sr
                )

                line_cur.insertRow([
                    line_geom, civ_oid, seg_oid, status,
                    road["name_full"], civ_num, range_str
                ])

        messages.addMessage("Fishbone lines written.")

        # ------------------------------------------------------------------
        # Pass 2 - OutOfRange points
        # ------------------------------------------------------------------
        messages.addMessage("Writing OutOfRange points...")
        oor_fields = ["SHAPE@", "CivicOID", "StreetName", "CivicNumber", "RangeStatus"]

        with arcpy.da.SearchCursor(civic_result, result_fields) as civic_cur, \
             arcpy.da.InsertCursor(output_oor, oor_fields) as oor_cur:

            for civ_oid, civ_street, civ_num, civ_shp, seg_oid, status in civic_cur:
                if civ_shp is None:
                    continue
                if status in ("OutOfRange", "NoData"):
                    oor_cur.insertRow([civ_shp, civ_oid, civ_street, civ_num, status])

        messages.addMessage("=" * 50)
        messages.addMessage("Fishbone QA complete. Outputs written to:")
        messages.addMessage(f"  Civic Result   → {civic_result}")
        messages.addMessage(f"  Fishbone Lines → {output_lines}")
        messages.addMessage(f"  Out of Range   → {output_oor}")
        messages.addMessage("=" * 50)

        # ------------------------------------------------------------------
        # Add outputs to active map
        # ------------------------------------------------------------------
        try:
            aprx       = arcpy.mp.ArcGISProject("CURRENT")
            active_map = aprx.activeMap
            if active_map is not None:
                active_map.addDataFromPath(civic_result)
                active_map.addDataFromPath(output_lines)
                active_map.addDataFromPath(output_oor)
                messages.addMessage("Outputs added to active map.")
            else:
                messages.addWarningMessage(
                    "No active map found. Add outputs manually from the output GDB."
                )
        except Exception as e:
            messages.addWarningMessage(
                f"Could not add layers to map: {e}. Add outputs manually from the output GDB."
            )

        return

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
            "Matches civic address points to road segments with parity validation:\n"
            "- Address range validation (out of range detection)\n"
            "- Address parity validation (odd/even consistency)\n"
            "Outputs fishbone lines for matched points and separate layers for unmatched points."
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
        p_out_gdb.defaultEnvironmentName = "workspace"

        # 10 - Enable address parity validation
        p_parity_check = arcpy.Parameter(
            displayName="Enable Address Parity Validation (Odd/Even)",
            name="enable_parity_check",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_parity_check.value = True

        return [
            p_civic, p_civic_name, p_civic_num,
            p_road, p_road_name,
            p_fL, p_tL, p_fR, p_tR,
            p_out_gdb,
            p_parity_check
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
    # Helper functions
    # ------------------------------------------------------------------
    @staticmethod
    def determine_range_parity(from_addr, to_addr):
        """
        Determine the parity pattern of an address range.
        Returns: 'ODD', 'EVEN', 'MIXED', or None
        """
        if from_addr is None or to_addr is None:
            return None
        
        try:
            from_int = int(from_addr)
            to_int = int(to_addr)
        except:
            return None
        
        from_parity = 'EVEN' if from_int % 2 == 0 else 'ODD'
        to_parity = 'EVEN' if to_int % 2 == 0 else 'ODD'
        
        # If both endpoints have same parity, the range is that parity
        if from_parity == to_parity:
            return from_parity
        
        # If endpoints differ, the range contains both odd and even
        return 'MIXED'

    @staticmethod
    def get_address_parity(address_num):
        """
        Get the parity of a single address number.
        Returns: 'ODD', 'EVEN', or None
        """
        if address_num is None:
            return None
        
        try:
            addr_int = int(address_num)
            return 'EVEN' if addr_int % 2 == 0 else 'ODD'
        except:
            return None

    @staticmethod
    def validate_parity_match(address_num, range_from, range_to):
        """
        Check if an address number's parity matches the range's parity.
        Returns: ('MATCH', None), ('MISMATCH', error_msg), or ('UNKNOWN', reason)
        """
        addr_parity = FishboneQATool.get_address_parity(address_num)
        range_parity = FishboneQATool.determine_range_parity(range_from, range_to)
        
        if addr_parity is None or range_parity is None:
            return ('UNKNOWN', 'Missing parity data')
        
        # MIXED ranges can contain any address
        if range_parity == 'MIXED':
            return ('MATCH', None)
        
        # Check if address parity matches range parity
        if addr_parity == range_parity:
            return ('MATCH', None)
        else:
            return ('MISMATCH', f'{addr_parity} address in {range_parity}-only range')

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
        enable_parity_check = parameters[10].value

        # Output paths
        civic_result  = os.path.join(out_gdb, "Civic_QA_Result")
        output_lines  = os.path.join(out_gdb, "Fishbone_Lines")
        output_oor    = os.path.join(out_gdb, "Fishbone_OutOfRange")

        sr = arcpy.Describe(civic_fc).spatialReference

        messages.addMessage("=" * 60)
        messages.addMessage("FISHBONE QA TOOL - PARITY VALIDATION")
        messages.addMessage("=" * 60)
        messages.addMessage(f"Address parity validation: {enable_parity_check}")
        messages.addMessage("=" * 60)

        # ------------------------------------------------------------------
        # Copy civic layer to output GDB
        # ------------------------------------------------------------------
        messages.addMessage("Copying civic layer to output GDB...")
        if arcpy.Exists(civic_result):
            arcpy.Delete_management(civic_result)
        arcpy.CopyFeatures_management(civic_fc, civic_result)

        # Add QA fields to the COPY
        arcpy.AddField_management(civic_result, "MatchedSegmentOID", "LONG")
        arcpy.AddField_management(civic_result, "RangeStatus", "TEXT", field_length=30)
        arcpy.AddField_management(civic_result, "MatchedSide", "TEXT", field_length=10)
        
        if enable_parity_check:
            arcpy.AddField_management(civic_result, "AddressParity", "TEXT", field_length=10)
            arcpy.AddField_management(civic_result, "RangeParity", "TEXT", field_length=10)
            arcpy.AddField_management(civic_result, "ParityMatch", "TEXT", field_length=20)

        # ------------------------------------------------------------------
        # Build road lookup dictionary
        # ------------------------------------------------------------------
        messages.addMessage("Building road lookup dictionary and validating road ranges...")
        
        road_fields = ["OID@", road_name_fld, fL_fld, tL_fld, fR_fld, tR_fld, "SHAPE@"]
        
        road_lookup = {}
        road_detail_lookup = {}

        with arcpy.da.SearchCursor(road_fc, road_fields) as cur:
            for row in cur:
                oid = row[0]
                name = row[1]
                
                # Range fields
                try:
                    fL = float(row[2]) if row[2] is not None else None
                    tL = float(row[3]) if row[3] is not None else None
                except:
                    fL = tL = None
                
                try:
                    fR = float(row[4]) if row[4] is not None else None
                    tR = float(row[5]) if row[5] is not None else None
                except:
                    fR = tR = None
                
                shp = row[6]
                
                # Build lookup key
                lookup_key = name.upper().strip() if name else None
                
                if lookup_key:
                    entry = (oid, fL, tL, fR, tR, name, shp)
                    road_lookup.setdefault(lookup_key, []).append(entry)

                road_detail_lookup[oid] = {
                    "name_full": name,
                    "fL": fL, "tL": tL,
                    "fR": fR, "tR": tR,
                    "shape": shp
                }

        messages.addMessage(f"Road lookup built: {len(road_lookup)} unique street names.")

        # ------------------------------------------------------------------
        # Matching loop
        # ------------------------------------------------------------------
        messages.addMessage("Matching civic points to road segments...")
        
        civic_fields = ["OID@", civic_name_fld, civic_num_fld]
        civic_fields.extend(["MatchedSegmentOID", "RangeStatus", "MatchedSide"])
        
        if enable_parity_check:
            civic_fields.extend(["AddressParity", "RangeParity", "ParityMatch"])
        
        civic_fields.append("SHAPE@")

        match_stats = {
            'total': 0,
            'within_range': 0,
            'out_of_range': 0,
            'no_data': 0,
            'parity_mismatch': 0
        }

        with arcpy.da.UpdateCursor(civic_result, civic_fields) as cur:
            for row in cur:
                match_stats['total'] += 1
                
                civ_oid = row[0]
                street_name = row[1]
                street_num = row[2]
                
                # QA field indices
                matched_oid_idx = 3
                range_status_idx = 4
                matched_side_idx = 5
                
                addr_parity_idx = None
                range_parity_idx = None
                parity_match_idx = None
                shape_idx = 6
                
                if enable_parity_check:
                    addr_parity_idx = 6
                    range_parity_idx = 7
                    parity_match_idx = 8
                    shape_idx = 9

                # Handle missing data
                if street_name is None or street_num is None:
                    row[matched_oid_idx] = None
                    row[range_status_idx] = "NoData"
                    row[matched_side_idx] = None
                    match_stats['no_data'] += 1
                    cur.updateRow(row)
                    continue

                # Build lookup key
                lookup_key = street_name.upper().strip()

                candidates = road_lookup.get(lookup_key, [])
                matched_left = []
                matched_right = []

                # Find range matches
                for (oid, fL, tL, fR, tR, name_full, shp) in candidates:
                    in_left = fL is not None and tL is not None and min(fL, tL) <= street_num <= max(fL, tL)
                    in_right = fR is not None and tR is not None and min(fR, tR) <= street_num <= max(fR, tR)
                    
                    if in_left:
                        matched_left.append((oid, 'LEFT', shp, fL, tL))
                    if in_right:
                        matched_right.append((oid, 'RIGHT', shp, fR, tR))

                all_matches = matched_left + matched_right

                if not all_matches:
                    row[matched_oid_idx] = None
                    row[range_status_idx] = "OutOfRange"
                    row[matched_side_idx] = None
                    
                    # Set parity fields to None
                    if enable_parity_check:
                        addr_parity = self.get_address_parity(street_num)
                        row[addr_parity_idx] = addr_parity
                        row[range_parity_idx] = None
                        row[parity_match_idx] = None
                    
                    match_stats['out_of_range'] += 1
                else:
                    civic_shp = row[shape_idx]
                    
                    if enable_parity_check:
                        # PARITY-PREFERENCE MATCHING
                        # Match to the side with correct parity first
                        addr_parity = self.get_address_parity(street_num)
                        
                        # Collect matches by parity
                        parity_matches = []
                        non_parity_matches = []
                        
                        for (oid, side, shp, range_from, range_to) in all_matches:
                            range_parity = self.determine_range_parity(range_from, range_to)
                            
                            if range_parity == addr_parity or range_parity == 'MIXED':
                                parity_matches.append((oid, side, shp, range_from, range_to))
                            else:
                                non_parity_matches.append((oid, side, shp, range_from, range_to))
                        
                        # Prefer parity matches
                        candidates_to_use = parity_matches if parity_matches else non_parity_matches
                        
                        # Find closest match
                        min_dist = None
                        best_match = None
                        
                        for (oid, side, shp, range_from, range_to) in candidates_to_use:
                            dist = civic_shp.distanceTo(shp)
                            if min_dist is None or dist < min_dist:
                                min_dist = dist
                                best_match = (oid, side, shp, range_from, range_to)
                        
                        matched_oid, matched_side, road_shp, range_from, range_to = best_match
                        
                    else:
                        # Simple distance matching
                        min_dist = None
                        best_match = None
                        
                        for (oid, side, shp, range_from, range_to) in all_matches:
                            dist = civic_shp.distanceTo(shp)
                            if min_dist is None or dist < min_dist:
                                min_dist = dist
                                best_match = (oid, side, shp, range_from, range_to)
                        
                        matched_oid, matched_side, road_shp, range_from, range_to = best_match
                    
                    row[matched_oid_idx] = matched_oid
                    row[range_status_idx] = "WithinRange"
                    row[matched_side_idx] = matched_side
                    match_stats['within_range'] += 1
                    
                    # Parity validation
                    if enable_parity_check:
                        addr_parity = self.get_address_parity(street_num)
                        range_parity = self.determine_range_parity(range_from, range_to)
                        
                        row[addr_parity_idx] = addr_parity
                        row[range_parity_idx] = range_parity
                        
                        parity_status, parity_msg = self.validate_parity_match(street_num, range_from, range_to)
                        
                        if parity_status == 'MATCH':
                            row[parity_match_idx] = "MATCH"
                        elif parity_status == 'MISMATCH':
                            row[parity_match_idx] = "MISMATCH"
                            match_stats['parity_mismatch'] += 1
                        else:
                            row[parity_match_idx] = "UNKNOWN"

                cur.updateRow(row)

        messages.addMessage("Matching complete.")
        messages.addMessage("-" * 60)
        messages.addMessage("MATCHING STATISTICS:")
        messages.addMessage(f"  Total civic points: {match_stats['total']}")
        messages.addMessage(f"  Within range: {match_stats['within_range']}")
        messages.addMessage(f"  Out of range: {match_stats['out_of_range']}")
        messages.addMessage(f"  No data: {match_stats['no_data']}")
        if enable_parity_check:
            messages.addMessage(f"  Parity mismatches (odd/even): {match_stats['parity_mismatch']}")
        messages.addMessage("-" * 60)

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

        line_field_defs = [
            ("CivicOID",     "LONG",   None),
            ("RoadOID",      "LONG",   None),
            ("RangeStatus",  "TEXT",   30),
            ("RoadName",     "TEXT",   100),
            ("CivicNumber",  "DOUBLE", None),
            ("MatchedRange", "TEXT",   50),
            ("MatchedSide",  "TEXT",   10),
        ]
        
        if enable_parity_check:
            line_field_defs.extend([
                ("AddressParity", "TEXT", 10),
                ("RangeParity", "TEXT", 10),
                ("ParityMatch", "TEXT", 20),
            ])

        for fname, ftype, flength in line_field_defs:
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

        oor_field_defs = [
            ("CivicOID",    "LONG",   None),
            ("StreetName",  "TEXT",   100),
            ("CivicNumber", "DOUBLE", None),
            ("RangeStatus", "TEXT",   30),
        ]
        
        if enable_parity_check:
            oor_field_defs.append(("AddressParity", "TEXT", 10))

        for fname, ftype, flength in oor_field_defs:
            kwargs = {"field_length": flength} if flength else {}
            arcpy.AddField_management(output_oor, fname, ftype, **kwargs)

        # ------------------------------------------------------------------
        # Pass 1 - Fishbone lines
        # ------------------------------------------------------------------
        messages.addMessage("Drawing fishbone lines...")
        
        result_fields = ["OID@", civic_name_fld, civic_num_fld, "SHAPE@", 
                        "MatchedSegmentOID", "RangeStatus", "MatchedSide"]
        
        if enable_parity_check:
            result_fields.extend(["AddressParity", "RangeParity", "ParityMatch"])
        
        line_fields = ["SHAPE@", "CivicOID", "RoadOID", "RangeStatus", "RoadName", 
                      "CivicNumber", "MatchedRange", "MatchedSide"]
        
        if enable_parity_check:
            line_fields.extend(["AddressParity", "RangeParity", "ParityMatch"])

        with arcpy.da.SearchCursor(civic_result, result_fields) as civic_cur, \
             arcpy.da.InsertCursor(output_lines, line_fields) as line_cur:

            for row in civic_cur:
                idx = 0
                civ_oid = row[idx]; idx += 1
                civ_street = row[idx]; idx += 1
                civ_num = row[idx]; idx += 1
                civ_shp = row[idx]; idx += 1
                seg_oid = row[idx]; idx += 1
                status = row[idx]; idx += 1
                matched_side = row[idx]; idx += 1
                
                addr_parity = None
                range_parity = None
                parity_match = None
                if enable_parity_check:
                    addr_parity = row[idx]; idx += 1
                    range_parity = row[idx]; idx += 1
                    parity_match = row[idx]; idx += 1
                
                # Skip if not matched
                if civ_shp is None or status in ("OutOfRange", "NoData") or seg_oid is None:
                    continue

                road = road_detail_lookup.get(seg_oid)
                if road is None:
                    continue

                # Build range string with parity
                range_str = ""
                if road["fL"] is not None and road["tL"] is not None:
                    lo, hi = int(min(road["fL"], road["tL"])), int(max(road["fL"], road["tL"]))
                    if enable_parity_check:
                        left_parity = self.determine_range_parity(road["fL"], road["tL"])
                        range_str = f"L:{lo}-{hi} ({left_parity})"
                    else:
                        range_str = f"L:{lo}-{hi}"
                
                if road["fR"] is not None and road["tR"] is not None:
                    lo, hi = int(min(road["fR"], road["tR"])), int(max(road["fR"], road["tR"]))
                    if enable_parity_check:
                        right_parity = self.determine_range_parity(road["fR"], road["tR"])
                        range_str += f" R:{lo}-{hi} ({right_parity})" if range_str else f"R:{lo}-{hi} ({right_parity})"
                    else:
                        range_str += f" R:{lo}-{hi}" if range_str else f"R:{lo}-{hi}"

                # Create fishbone line
                civic_pt = civ_shp.centroid
                road_shp = road["shape"]
                nearest_pt = road_shp.positionAlongLine(road_shp.measureOnLine(civic_pt))

                line_geom = arcpy.Polyline(
                    arcpy.Array([civic_pt, nearest_pt.firstPoint]),
                    sr
                )

                # Build row data
                line_row = [
                    line_geom, civ_oid, seg_oid, status,
                    road["name_full"], civ_num, range_str, matched_side
                ]
                
                if enable_parity_check:
                    line_row.extend([addr_parity, range_parity, parity_match])
                
                line_cur.insertRow(line_row)

        messages.addMessage("Fishbone lines written.")

        # ------------------------------------------------------------------
        # Pass 2 - OutOfRange points
        # ------------------------------------------------------------------
        messages.addMessage("Writing OutOfRange points...")
        
        oor_fields = ["SHAPE@", "CivicOID", "StreetName", "CivicNumber", "RangeStatus"]
        if enable_parity_check:
            oor_fields.append("AddressParity")

        with arcpy.da.SearchCursor(civic_result, result_fields) as civic_cur, \
             arcpy.da.InsertCursor(output_oor, oor_fields) as oor_cur:

            for row in civic_cur:
                idx = 0
                civ_oid = row[idx]; idx += 1
                civ_street = row[idx]; idx += 1
                civ_num = row[idx]; idx += 1
                civ_shp = row[idx]; idx += 1
                seg_oid = row[idx]; idx += 1
                status = row[idx]; idx += 1
                matched_side = row[idx]; idx += 1
                
                if civ_shp is None:
                    continue
                
                if status in ("OutOfRange", "NoData"):
                    oor_row = [civ_shp, civ_oid, civ_street, civ_num, status]
                    
                    if enable_parity_check:
                        addr_parity = row[idx] if idx < len(row) else None
                        oor_row.append(addr_parity)
                    
                    oor_cur.insertRow(oor_row)

        messages.addMessage("=" * 60)
        messages.addMessage("FISHBONE QA COMPLETE")
        messages.addMessage("=" * 60)
        messages.addMessage("Outputs written to:")
        messages.addMessage(f"  Civic Result   → {civic_result}")
        messages.addMessage(f"  Fishbone Lines → {output_lines}")
        messages.addMessage(f"  Out of Range   → {output_oor}")
        messages.addMessage("=" * 60)

        # ------------------------------------------------------------------
        # Add outputs to active map
        # ------------------------------------------------------------------
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
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

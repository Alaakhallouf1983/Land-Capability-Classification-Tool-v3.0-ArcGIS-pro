# -*- coding: utf-8 -*-
"""
LandCapability_USDA.pyt
=======================
USDA Land Capability Classification (LCC) Tool for ArcGIS Pro
Based on: USDA Handbook 210 – Land Capability Classification System
Author  : Generated for ArcGIS Pro
Version : 3.0 – Full Edition

How to install:
  1. In ArcGIS Pro → Catalog pane → right-click 'Toolboxes' → Add Toolbox
  2. Browse to this .pyt file
  3. The tool appears as "Land Capability Classification (USDA)" inside the toolbox

Inputs accepted: Raster or Feature Class / Shapefile for every factor.
Output        : Polygon feature class + Interactive HTML report.
"""

import arcpy
from arcpy.sa import *
import os, sys, json, math, datetime, traceback

arcpy.env.overwriteOutput = True

# ─────────────────────────────────────────────────────────────────────────────
#  USDA LCC CLASSIFICATION TABLES
# ─────────────────────────────────────────────────────────────────────────────
CLASS_INFO = {
    1: {
        "name"    : "Class I – Excellent",
        "arabic"  : "الفئة الأولى – أرض ممتازة",
        "color"   : "#1a9641",
        "limits"  : "No significant limitations. Deep, well-drained, nearly level (0–2%).",
        "uses"    : "All field crops, orchards, vegetables, pasture, forestry, wildlife.",
        "subclass": ""
    },
    2: {
        "name"    : "Class II – Good",
        "arabic"  : "الفئة الثانية – أرض جيدة",
        "color"   : "#a6d96a",
        "limits"  : "Moderate limitations (2–6% slope, slight erosion, moderate drainage).",
        "uses"    : "Most crops with simple conservation practices.",
        "subclass": "e, w, s"
    },
    3: {
        "name"    : "Class III – Moderate",
        "arabic"  : "الفئة الثالثة – أرض متوسطة",
        "color"   : "#ffffbf",
        "limits"  : "Severe limitations (6–12% slope, erosion hazard, shallow soil, or poor drainage).",
        "uses"    : "Cultivated crops with intensive management; pasture; hay.",
        "subclass": "e, w, s, c"
    },
    4: {
        "name"    : "Class IV – Fair",
        "arabic"  : "الفئة الرابعة – أرض مقبولة",
        "color"   : "#fdae61",
        "limits"  : "Very severe limitations (12–18% slope, frequent flooding, very shallow soils).",
        "uses"    : "Limited cultivation; hay, pasture, forestry.",
        "subclass": "e, w, s, c"
    },
    5: {
        "name"    : "Class V – Not Suitable for Tillage",
        "arabic"  : "الفئة الخامسة – غير قابلة للحراثة",
        "color"   : "#fee08b",
        "limits"  : "Level/nearly level but permanently wet, stony, or subject to frequent overflow.",
        "uses"    : "Pasture, woodland, wildlife habitat, recreation.",
        "subclass": "w, s"
    },
    6: {
        "name"    : "Class VI – Unsuitable for Cultivation",
        "arabic"  : "الفئة السادسة – غير صالحة للزراعة",
        "color"   : "#f46d43",
        "limits"  : "Severe limitations (18–30% slope, severe erosion, stoniness, salinity).",
        "uses"    : "Pasture, range, woodland, wildlife.",
        "subclass": "e, w, s, c"
    },
    7: {
        "name"    : "Class VII – Very Unsuitable",
        "arabic"  : "الفئة السابعة – غير صالحة جداً",
        "color"   : "#d73027",
        "limits"  : "Very severe limitations (30–45% slope, very shallow, very stony, arid).",
        "uses"    : "Grazing (limited), forestry, wildlife, watershed protection.",
        "subclass": "e, w, s, c"
    },
    8: {
        "name"    : "Class VIII – Not Suitable for Any Use",
        "arabic"  : "الفئة الثامنة – أرض بور",
        "color"   : "#4d0000",
        "limits"  : "Extreme limitations (>45% slope, rock outcrops, deep sand, salt flats).",
        "uses"    : "Wildlife, recreation, conservation, watersheds only.",
        "subclass": ""
    }
}

# Slope → LCC Class mapping (USDA Handbook 210)
SLOPE_BREAKS = [
    (0,   2,   1),
    (2,   6,   2),
    (6,   12,  3),
    (12,  18,  4),
    (18,  30,  6),
    (30,  45,  7),
    (45,  9999, 8)
]

# Soil depth (cm) → additional class offset
DEPTH_BREAKS = [
    (150,  9999, 0),   # deep         → no penalty
    (90,   150,  0),   # moderately deep → class I/II ok
    (50,   90,   1),   # shallow      → +1 class
    (25,   50,   2),   # very shallow → +2 classes
    (0,    25,   3)    # extremely shallow → +3 classes
]

# Drainage class codes (FAO/USDA): 1=excessively, 2=well, 3=mod well, 4=imperfect, 5=poor, 6=very poor
DRAINAGE_PENALTY = {1: 1, 2: 0, 3: 0, 4: 1, 5: 2, 6: 3}

# Flooding frequency: 0=none, 1=rare, 2=occasional, 3=frequent, 4=very frequent
FLOOD_PENALTY = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3}

# Erosion hazard: 0=none/slight, 1=moderate, 2=severe, 3=very severe
EROSION_PENALTY = {0: 0, 1: 1, 2: 2, 3: 3}

# Texture: 1=loam/silt loam (best), 2=clay loam, 3=sandy loam, 4=clay/heavy clay, 5=sand/gravel
TEXTURE_PENALTY = {1: 0, 2: 0, 3: 1, 4: 1, 5: 2}

# Salinity (EC dS/m): 0–4=none, 4–8=slight, 8–16=mod, >16=severe
SALINITY_BREAKS = [
    (0,   4,   0),
    (4,   8,   1),
    (8,   16,  2),
    (16,  9999, 3)
]

# Stoniness: 0=none/few, 1=common, 2=many, 3=very stony/rocky
STONE_PENALTY = {0: 0, 1: 1, 2: 2, 3: 3}

# Climate (LGP – length growing period in days OR agro-climatic zone code)
# Code: 1=humid/subhumid (good), 2=semi-arid (moderate), 3=arid (severe), 4=hyper-arid
CLIMATE_PENALTY = {1: 0, 2: 1, 3: 2, 4: 3}


def slope_class(slope_val):
    for lo, hi, cls in SLOPE_BREAKS:
        if lo <= slope_val < hi:
            return cls
    return 8


def apply_breaks(val, breaks):
    for lo, hi, penalty in breaks:
        if lo <= val < hi:
            return penalty
    return 3


def clamp(cls, lo=1, hi=8):
    return max(lo, min(hi, cls))


# ─────────────────────────────────────────────────────────────────────────────
#  TOOLBOX DEFINITION
# ─────────────────────────────────────────────────────────────────────────────
class Toolbox:
    def __init__(self):
        self.label   = "Land Capability Classification – USDA"
        self.alias   = "LCC_USDA"
        self.tools   = [LandCapabilityTool]


class LandCapabilityTool:
    def __init__(self):
        self.label      = "Land Capability Classification (USDA)"
        self.description = (
            "Classifies land into USDA LCC Classes I–VIII using slope, soil depth, "
            "drainage, flooding, erosion, texture, salinity/pH, stoniness, and climate. "
            "Generates polygon output and an interactive HTML report."
        )
        self.canRunInBackground = True

    # ── PARAMETERS ────────────────────────────────────────────────────────────
    def getParameterInfo(self):
        params = []

        # 0 – Slope raster (required)
        p = arcpy.Parameter(
            displayName="Slope Raster (degrees or percent)",
            name="slope_raster",
            datatype=["DERasterDataset", "DERasterBand", "GPRasterLayer"],
            parameterType="Required",
            direction="Input"
        )
        params.append(p)

        # 1 – Slope unit
        p = arcpy.Parameter(
            displayName="Slope Unit",
            name="slope_unit",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        p.filter.type = "ValueList"
        p.filter.list = ["PERCENT", "DEGREE"]
        p.value = "PERCENT"
        params.append(p)

        # 2 – Soil depth
        p = arcpy.Parameter(
            displayName="Soil Depth Raster (cm) [Optional]",
            name="soil_depth",
            datatype=["DERasterDataset", "DERasterBand", "GPRasterLayer",
                      "DEFeatureClass", "GPFeatureLayer", "DEShapefile"],
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 3 – Soil depth field (if vector)
        p = arcpy.Parameter(
            displayName="Soil Depth Field (if vector input)",
            name="depth_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input"
        )
        p.parameterDependencies = ["soil_depth"]
        params.append(p)

        # 4 – Drainage class raster / feature
        p = arcpy.Parameter(
            displayName="Drainage Class Raster/Feature (1=Excess → 6=Very Poor) [Optional]",
            name="drainage",
            datatype=["DERasterDataset", "DERasterBand", "GPRasterLayer",
                      "DEFeatureClass", "GPFeatureLayer", "DEShapefile"],
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 5 – Drainage field
        p = arcpy.Parameter(
            displayName="Drainage Field (if vector)",
            name="drainage_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input"
        )
        p.parameterDependencies = ["drainage"]
        params.append(p)

        # 6 – Flooding frequency
        p = arcpy.Parameter(
            displayName="Flooding Frequency Raster/Feature (0=None → 4=Very Frequent) [Optional]",
            name="flooding",
            datatype=["DERasterDataset", "DERasterBand", "GPRasterLayer",
                      "DEFeatureClass", "GPFeatureLayer", "DEShapefile"],
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 7 – Flooding field
        p = arcpy.Parameter(
            displayName="Flooding Field (if vector)",
            name="flooding_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input"
        )
        p.parameterDependencies = ["flooding"]
        params.append(p)

        # 8 – Erosion hazard
        p = arcpy.Parameter(
            displayName="Erosion Hazard Raster/Feature (0=None → 3=Very Severe) [Optional]",
            name="erosion",
            datatype=["DERasterDataset", "DERasterBand", "GPRasterLayer",
                      "DEFeatureClass", "GPFeatureLayer", "DEShapefile"],
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 9 – Erosion field
        p = arcpy.Parameter(
            displayName="Erosion Field (if vector)",
            name="erosion_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input"
        )
        p.parameterDependencies = ["erosion"]
        params.append(p)

        # 10 – Texture
        p = arcpy.Parameter(
            displayName="Soil Texture Raster/Feature (1=Loam best → 5=Sand/Gravel) [Optional]",
            name="texture",
            datatype=["DERasterDataset", "DERasterBand", "GPRasterLayer",
                      "DEFeatureClass", "GPFeatureLayer", "DEShapefile"],
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 11 – Texture field
        p = arcpy.Parameter(
            displayName="Texture Field (if vector)",
            name="texture_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input"
        )
        p.parameterDependencies = ["texture"]
        params.append(p)

        # 12 – Salinity (EC dS/m)
        p = arcpy.Parameter(
            displayName="Salinity / EC Raster/Feature (dS/m) [Optional]",
            name="salinity",
            datatype=["DERasterDataset", "DERasterBand", "GPRasterLayer",
                      "DEFeatureClass", "GPFeatureLayer", "DEShapefile"],
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 13 – Salinity field
        p = arcpy.Parameter(
            displayName="Salinity Field (if vector)",
            name="salinity_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input"
        )
        p.parameterDependencies = ["salinity"]
        params.append(p)

        # 14 – Stoniness
        p = arcpy.Parameter(
            displayName="Stoniness/Rockiness Raster/Feature (0=None → 3=Very Stony) [Optional]",
            name="stoniness",
            datatype=["DERasterDataset", "DERasterBand", "GPRasterLayer",
                      "DEFeatureClass", "GPFeatureLayer", "DEShapefile"],
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 15 – Stoniness field
        p = arcpy.Parameter(
            displayName="Stoniness Field (if vector)",
            name="stone_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input"
        )
        p.parameterDependencies = ["stoniness"]
        params.append(p)

        # 16 – Climate
        p = arcpy.Parameter(
            displayName="Climate Zone Raster/Feature (1=Humid → 4=Hyper-Arid) [Optional]",
            name="climate",
            datatype=["DERasterDataset", "DERasterBand", "GPRasterLayer",
                      "DEFeatureClass", "GPFeatureLayer", "DEShapefile"],
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 17 – Climate field
        p = arcpy.Parameter(
            displayName="Climate Field (if vector)",
            name="climate_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input"
        )
        p.parameterDependencies = ["climate"]
        params.append(p)

        # 18 – Land units polygon (optional zonal)
        p = arcpy.Parameter(
            displayName="Land Units Polygon (for Zonal Statistics) [Optional]",
            name="land_units",
            datatype=["DEFeatureClass", "GPFeatureLayer", "DEShapefile"],
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 19 – Land unit ID field
        p = arcpy.Parameter(
            displayName="Land Unit ID Field",
            name="unit_id_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input"
        )
        p.value = "OBJECTID"
        p.parameterDependencies = ["land_units"]
        params.append(p)

        # 20 – Cell size
        p = arcpy.Parameter(
            displayName="Output Cell Size (meters)",
            name="cell_size",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input"
        )
        p.value = 30
        params.append(p)

        # 21 – Output feature class
        p = arcpy.Parameter(
            displayName="Output Feature Class",
            name="output_fc",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output"
        )
        params.append(p)

        # 22 – Report folder
        p = arcpy.Parameter(
            displayName="Output Report Folder",
            name="report_folder",
            datatype="DEFolder",
            parameterType="Optional",
            direction="Input"
        )
        params.append(p)

        # 23 – Simplify polygons
        p = arcpy.Parameter(
            displayName="Simplify Output Polygons",
            name="simplify",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p.value = True
        params.append(p)

        return params

    def isLicensed(self):
        try:
            arcpy.CheckOutExtension("Spatial")
            return True
        except:
            return False

    def updateParameters(self, params):
        return

    def updateMessages(self, params):
        if not params[0].value:
            params[0].setErrorMessage("Slope raster is required.")
        return

    # ── EXECUTE ────────────────────────────────────────────────────────────────
    def execute(self, params, messages):
        try:
            arcpy.CheckOutExtension("Spatial")
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Collect parameters
            slope_raster   = params[0].valueAsText
            slope_unit     = params[1].valueAsText        # PERCENT / DEGREE
            soil_depth     = params[2].valueAsText
            depth_field    = params[3].valueAsText
            drainage       = params[4].valueAsText
            drainage_field = params[5].valueAsText
            flooding       = params[6].valueAsText
            flood_field    = params[7].valueAsText
            erosion        = params[8].valueAsText
            erosion_field  = params[9].valueAsText
            texture        = params[10].valueAsText
            texture_field  = params[11].valueAsText
            salinity       = params[12].valueAsText
            salin_field    = params[13].valueAsText
            stoniness      = params[14].valueAsText
            stone_field    = params[15].valueAsText
            climate        = params[16].valueAsText
            climate_field  = params[17].valueAsText
            land_units     = params[18].valueAsText
            unit_id_field  = params[19].valueAsText or "OBJECTID"
            cell_size      = float(params[20].value) if params[20].value else 30
            output_fc      = params[21].valueAsText
            report_folder  = params[22].valueAsText
            simplify_poly  = params[23].value if params[23].value is not None else True

            arcpy.env.cellSize        = cell_size
            arcpy.env.overwriteOutput = True
            scratch                   = arcpy.env.scratchGDB

            msg = arcpy.AddMessage

            msg("=" * 60)
            msg("  USDA Land Capability Classification Tool  v3.0")
            msg("=" * 60)

            # ── 1. Build slope raster ──────────────────────────────────────
            msg("\n[1/7] Processing Slope...")
            slope_r = arcpy.Raster(slope_raster)

            if slope_unit == "DEGREE":
                msg("  Converting degrees → percent slope")
                # percent = tan(degree * pi/180) * 100
                slope_r = Float(slope_r) * (math.pi / 180)
                slope_r = Tan(slope_r) * 100
            else:
                slope_r = Float(slope_r)

            # Set snap raster from slope
            snap_path = os.path.join(scratch, f"snap_{ts}")
            slope_r.save(snap_path)
            arcpy.env.snapRaster = snap_path
            msg(f"  Snap raster: {snap_path}")

            # ── 2. Classify slope to LCC class ────────────────────────────
            msg("\n[2/7] Classifying Slope to LCC Classes...")
            #  Remap: [from, to, new_value]
            slope_remap = RemapRange(
                [[ 0,  2,  1],
                 [ 2,  6,  2],
                 [ 6, 12,  3],
                 [12, 18,  4],
                 [18, 30,  6],
                 [30, 45,  7],
                 [45, 9999, 8]]
            )
            lcc_raster = Reclassify(slope_r, "Value", slope_remap, missing_values="NODATA")

            # ── 3. Process optional factors ───────────────────────────────
            msg("\n[3/7] Processing Optional Limiting Factors...")

            penalty_rasters = []  # list of penalty rasters (added to lcc_raster)

            def load_factor(layer, field, convert_fn, factor_name):
                """Load a raster or vector factor and apply conversion."""
                if not layer:
                    return None
                try:
                    desc  = arcpy.Describe(layer)
                    dtype = getattr(desc, "dataType", "").lower()

                    if "raster" in dtype:
                        r = Float(arcpy.Raster(layer))
                    else:
                        if not field:
                            msg(f"  ⚠ No field specified for {factor_name}, skipping.")
                            return None
                        tmp = os.path.join(scratch, f"ftr_{factor_name}_{ts}")
                        arcpy.conversion.FeatureToRaster(layer, field, tmp, cell_size)
                        r = Float(arcpy.Raster(tmp))

                    penalty = convert_fn(r)
                    msg(f"  ✓ {factor_name} factor loaded.")
                    return penalty
                except Exception as e:
                    msg(f"  ⚠ Could not process {factor_name}: {e}")
                    return None

            # ---- Soil depth penalty ----
            def depth_penalty_fn(r):
                # Map depth values to penalty using Reclassify
                rm = RemapRange([[150, 9999, 0],[90, 150, 0],[50, 90, 1],[25, 50, 2],[0, 25, 3]])
                return Reclassify(r, "Value", rm, missing_values="NODATA")

            pen = load_factor(soil_depth, depth_field, depth_penalty_fn, "SoilDepth")
            if pen is not None:
                penalty_rasters.append(pen)

            # ---- Drainage penalty ----
            def drainage_penalty_fn(r):
                rm = RemapValue([[1, 1],[2, 0],[3, 0],[4, 1],[5, 2],[6, 3]])
                return Reclassify(r, "Value", rm, missing_values="NODATA")

            pen = load_factor(drainage, drainage_field, drainage_penalty_fn, "Drainage")
            if pen is not None:
                penalty_rasters.append(pen)

            # ---- Flooding penalty ----
            def flood_penalty_fn(r):
                rm = RemapValue([[0, 0],[1, 0],[2, 1],[3, 2],[4, 3]])
                return Reclassify(r, "Value", rm, missing_values="NODATA")

            pen = load_factor(flooding, flood_field, flood_penalty_fn, "Flooding")
            if pen is not None:
                penalty_rasters.append(pen)

            # ---- Erosion penalty ----
            def erosion_penalty_fn(r):
                rm = RemapValue([[0, 0],[1, 1],[2, 2],[3, 3]])
                return Reclassify(r, "Value", rm, missing_values="NODATA")

            pen = load_factor(erosion, erosion_field, erosion_penalty_fn, "Erosion")
            if pen is not None:
                penalty_rasters.append(pen)

            # ---- Texture penalty ----
            def texture_penalty_fn(r):
                rm = RemapValue([[1, 0],[2, 0],[3, 1],[4, 1],[5, 2]])
                return Reclassify(r, "Value", rm, missing_values="NODATA")

            pen = load_factor(texture, texture_field, texture_penalty_fn, "Texture")
            if pen is not None:
                penalty_rasters.append(pen)

            # ---- Salinity penalty ----
            def salin_penalty_fn(r):
                rm = RemapRange([[0, 4, 0],[4, 8, 1],[8, 16, 2],[16, 9999, 3]])
                return Reclassify(r, "Value", rm, missing_values="NODATA")

            pen = load_factor(salinity, salin_field, salin_penalty_fn, "Salinity")
            if pen is not None:
                penalty_rasters.append(pen)

            # ---- Stoniness penalty ----
            def stone_penalty_fn(r):
                rm = RemapValue([[0, 0],[1, 1],[2, 2],[3, 3]])
                return Reclassify(r, "Value", rm, missing_values="NODATA")

            pen = load_factor(stoniness, stone_field, stone_penalty_fn, "Stoniness")
            if pen is not None:
                penalty_rasters.append(pen)

            # ---- Climate penalty ----
            def climate_penalty_fn(r):
                rm = RemapValue([[1, 0],[2, 1],[3, 2],[4, 3]])
                return Reclassify(r, "Value", rm, missing_values="NODATA")

            pen = load_factor(climate, climate_field, climate_penalty_fn, "Climate")
            if pen is not None:
                penalty_rasters.append(pen)

            # ── 4. Combine: LCC = max(slope_class + all_penalties) ────────
            msg("\n[4/7] Combining All Limiting Factors (Maximum Limitation Principle)...")

            if penalty_rasters:
                # Sum all penalties
                total_penalty = penalty_rasters[0]
                for pr in penalty_rasters[1:]:
                    total_penalty = CellStatistics([total_penalty, pr],
                                                   statistics_type="MAXIMUM",
                                                   ignore_nodata="DATA")
                final_raster = lcc_raster + total_penalty
                # Clamp to 1–8
                final_raster = Con(final_raster < 1, 1, Con(final_raster > 8, 8, final_raster))
            else:
                msg("  No optional factors provided. Classification based on slope only.")
                final_raster = lcc_raster

            # Round to integer
            final_raster = Int(final_raster + 0.5)

            # Save intermediate raster
            lcc_rast_path = os.path.join(scratch, f"lcc_raster_{ts}")
            final_raster.save(lcc_rast_path)
            msg(f"  LCC raster saved: {lcc_rast_path}")

            # ── 5. Zonal Statistics (if land units provided) ───────────────
            msg("\n[5/7] Generating Output Feature Class...")

            class_values_all = []

            if land_units:
                msg("  Applying Zonal Statistics (MAJORITY) per Land Unit...")
                out_table = os.path.join(scratch, f"zonal_{ts}")
                arcpy.sa.ZonalStatisticsAsTable(
                    land_units, unit_id_field, final_raster,
                    out_table, "DATA", "MAJORITY"
                )
                # Add MAJORITY as LCC_CLASS
                arcpy.management.CopyFeatures(land_units, output_fc)
                if "LCC_CLASS" not in [f.name for f in arcpy.ListFields(output_fc)]:
                    arcpy.management.AddField(output_fc, "LCC_CLASS", "SHORT")
                arcpy.management.JoinField(output_fc, unit_id_field,
                                           out_table, unit_id_field, ["MAJORITY"])
                arcpy.management.CalculateField(output_fc, "LCC_CLASS", "!MAJORITY!", "PYTHON3")
                try:
                    arcpy.management.DeleteField(output_fc, "MAJORITY")
                except:
                    pass

                class_values_all = [row[0] for row in
                                    arcpy.da.SearchCursor(output_fc, ["LCC_CLASS"])
                                    if row[0] is not None]
            else:
                simp = "SIMPLIFY" if simplify_poly else "NO_SIMPLIFY"
                arcpy.conversion.RasterToPolygon(final_raster, output_fc, simp, "Value")
                # Rename gridcode → LCC_CLASS
                arcpy.management.AddField(output_fc, "LCC_CLASS", "SHORT")
                arcpy.management.CalculateField(output_fc, "LCC_CLASS", "!gridcode!", "PYTHON3")
                try:
                    arcpy.management.DeleteField(output_fc, "gridcode")
                except:
                    pass

                class_values_all = [row[0] for row in
                                    arcpy.da.SearchCursor(output_fc, ["LCC_CLASS"])
                                    if row[0] is not None]

            # ── 6. Enrich output with descriptive fields ───────────────────
            msg("  Adding descriptive fields (LCC_NAME, LCC_COLOR, LCC_LIMITS, LCC_USES)...")
            for fld, ftype, length in [("LCC_NAME",  "TEXT", 60),
                                        ("LCC_COLOR", "TEXT", 10),
                                        ("LCC_ARABIC","TEXT", 60),
                                        ("LCC_LIMITS","TEXT", 200),
                                        ("LCC_USES",  "TEXT", 200)]:
                if fld not in [f.name for f in arcpy.ListFields(output_fc)]:
                    arcpy.management.AddField(output_fc, fld, ftype, field_length=length)

            with arcpy.da.UpdateCursor(output_fc,
                                        ["LCC_CLASS","LCC_NAME","LCC_COLOR",
                                         "LCC_ARABIC","LCC_LIMITS","LCC_USES"]) as cur:
                for row in cur:
                    cls = row[0]
                    if cls in CLASS_INFO:
                        info   = CLASS_INFO[cls]
                        row[1] = info["name"][:60]
                        row[2] = info["color"]
                        row[3] = info["arabic"][:60]
                        row[4] = info["limits"][:200]
                        row[5] = info["uses"][:200]
                    cur.updateRow(row)

            msg(f"  ✓ Output feature class: {output_fc}")

            # ── 7. Compute area statistics ─────────────────────────────────
            msg("\n[6/7] Computing Area Statistics...")
            total_area  = 0.0
            class_areas = {}
            class_counts= {}

            sr = arcpy.Describe(output_fc).spatialReference
            unit_name = sr.linearUnitName if sr and sr.linearUnitName else "Meter"

            with arcpy.da.SearchCursor(output_fc, ["LCC_CLASS", "SHAPE@AREA"]) as cur:
                for row in cur:
                    cls  = row[0] if row[0] else 0
                    area = row[1] if row[1] else 0.0
                    total_area           += area
                    class_areas[cls]      = class_areas.get(cls, 0.0) + area
                    class_counts[cls]     = class_counts.get(cls, 0)  + 1

            # ── 8. Generate Interactive HTML Report ───────────────────────
            msg("\n[7/7] Generating Interactive HTML Report...")

            if report_folder and os.path.isdir(report_folder):
                base_name = os.path.basename(output_fc).replace(".shp","").replace(".gdb","")
                report_path = os.path.join(report_folder, f"LCC_Report_{ts}.html")
            else:
                out_dir = os.path.dirname(output_fc)
                if not out_dir or not os.path.isdir(out_dir):
                    out_dir = arcpy.env.scratchFolder or os.path.expanduser("~")
                report_path = os.path.join(out_dir, f"LCC_Report_{ts}.html")

            html = _build_html_report(
                ts, output_fc, cell_size,
                class_areas, class_counts, total_area,
                slope_raster, slope_unit,
                [soil_depth, drainage, flooding, erosion, texture, salinity, stoniness, climate],
                land_units
            )

            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html)

            msg(f"  ✓ HTML Report: {report_path}")
            msg("\n" + "=" * 60)
            msg("  PROCESSING COMPLETE")
            msg(f"  Output FC  : {output_fc}")
            msg(f"  HTML Report: {report_path}")
            msg("=" * 60)

        except Exception as e:
            arcpy.AddError(f"ERROR: {e}\n{traceback.format_exc()}")
        finally:
            arcpy.CheckInExtension("Spatial")


# ─────────────────────────────────────────────────────────────────────────────
#  HTML REPORT GENERATOR
# ─────────────────────────────────────────────────────────────────────────────
def _build_html_report(ts, output_fc, cell_size,
                        class_areas, class_counts, total_area,
                        slope_raster, slope_unit,
                        optional_layers, land_units):

    dt = datetime.datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%d %B %Y  %H:%M:%S")

    # Build data for charts
    labels_js   = []
    areas_js    = []
    pcts_js     = []
    colors_js   = []
    rows_html   = []

    for cls in sorted(CLASS_INFO.keys()):
        info  = CLASS_INFO[cls]
        area  = class_areas.get(cls, 0.0)
        cnt   = class_counts.get(cls, 0)
        ha    = area / 10000.0
        pct   = (area / total_area * 100) if total_area > 0 else 0.0

        if cnt == 0:
            continue

        labels_js.append(f"Class {cls}")
        areas_js.append(round(ha, 2))
        pcts_js.append(round(pct, 2))
        colors_js.append(info["color"])

        rows_html.append(f"""
        <tr>
          <td><span class="badge" style="background:{info['color']};color:{'#fff' if cls>=6 else '#333'}">
            Class {cls}</span></td>
          <td><strong>{info['name']}</strong><br>
              <small style="color:#555">{info['arabic']}</small></td>
          <td>{ha:,.1f} ha</td>
          <td>
            <div class="bar-wrap">
              <div class="bar-fill" style="width:{min(pct,100):.1f}%;background:{info['color']}"></div>
              <span class="bar-label">{pct:.1f}%</span>
            </div>
          </td>
          <td class="td-small">{info['limits']}</td>
          <td class="td-small">{info['uses']}</td>
        </tr>""")

    total_ha = total_area / 10000.0

    opt_names = ["Soil Depth","Drainage","Flooding","Erosion",
                 "Texture","Salinity","Stoniness","Climate"]
    opt_badges = ""
    for name, val in zip(opt_names, optional_layers):
        color = "#2196f3" if val else "#ccc"
        text  = "#fff"    if val else "#555"
        opt_badges += (f'<span class="badge" style="background:{color};color:{text};margin:3px">'
                       f'{"✓" if val else "✗"} {name}</span>')

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="auto">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Land Capability Classification Report – USDA</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --accent : #1a6f3c;
      --bg     : #f5f7fa;
      --card   : #ffffff;
      --radius : 12px;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      background: var(--bg);
      color: #222;
    }}
    header {{
      background: linear-gradient(135deg,#1a6f3c,#0d3d22);
      color:#fff; padding:30px 40px 20px;
    }}
    header h1 {{ font-size:1.9rem; margin-bottom:6px; }}
    header p  {{ opacity:.8; font-size:.95rem; }}
    .meta {{
      display:flex; flex-wrap:wrap; gap:16px;
      background:#fff; border-bottom:3px solid var(--accent);
      padding:16px 40px; font-size:.88rem; color:#444;
    }}
    .meta span {{ background:#eef7ee; border:1px solid #b3d9b3;
                  padding:4px 12px; border-radius:20px; }}
    .container {{ max-width:1200px; margin:30px auto; padding:0 20px; }}
    h2 {{ font-size:1.3rem; color:var(--accent); margin:0 0 16px;
          border-left:4px solid var(--accent); padding-left:10px; }}
    .card {{
      background:var(--card); border-radius:var(--radius);
      box-shadow:0 2px 12px rgba(0,0,0,.08);
      padding:24px; margin-bottom:26px;
    }}
    .charts-row {{ display:flex; gap:24px; flex-wrap:wrap; margin-bottom:26px; }}
    .chart-card {{ flex:1; min-width:280px; background:var(--card);
                   border-radius:var(--radius); padding:20px;
                   box-shadow:0 2px 12px rgba(0,0,0,.08); }}
    .chart-card h2 {{ margin-bottom:12px; }}
    canvas {{ max-height:320px; }}
    table {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
    th {{ background:var(--accent); color:#fff; padding:10px 12px;
          text-align:left; position:sticky; top:0; z-index:1; }}
    td {{ padding:9px 12px; border-bottom:1px solid #eee; vertical-align:top; }}
    tr:hover td {{ background:#f0f7f2; }}
    .badge {{
      display:inline-block; padding:4px 10px; border-radius:12px;
      font-size:.8rem; font-weight:600;
    }}
    .bar-wrap {{ position:relative; background:#eee;
                 border-radius:4px; height:22px; min-width:120px; }}
    .bar-fill  {{ height:100%; border-radius:4px; transition:width .4s; }}
    .bar-label {{ position:absolute; right:6px; top:2px;
                  font-size:.78rem; font-weight:600; }}
    .td-small  {{ font-size:.80rem; color:#555; max-width:200px; }}
    .total-box {{
      display:flex; gap:20px; flex-wrap:wrap; margin-bottom:20px;
    }}
    .kpi {{
      flex:1; min-width:140px; background:#e8f5e9; border-radius:10px;
      padding:16px 20px; text-align:center;
    }}
    .kpi .val  {{ font-size:1.8rem; font-weight:700; color:var(--accent); }}
    .kpi .lbl  {{ font-size:.82rem; color:#555; margin-top:4px; }}
    .class-card-grid {{ display:grid; gap:14px;
                        grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); }}
    .cc {{
      border-radius:10px; padding:14px 16px;
      border-left:6px solid #ccc;
    }}
    .cc h3 {{ font-size:1rem; margin-bottom:4px; }}
    .cc .sub {{ font-size:.8rem; color:#444; margin-top:6px; }}
    footer {{
      text-align:center; padding:20px; font-size:.8rem;
      color:#888; border-top:1px solid #ddd; margin-top:20px;
    }}
    @media print {{
      .charts-row {{ flex-direction:column; }}
      canvas {{ max-height:250px; }}
    }}
    @media (max-width:640px) {{
      header {{ padding:20px; }}
      .container {{ padding:0 10px; }}
    }}
  </style>
</head>
<body>
<header>
  <h1>🌱 Land Capability Classification Report</h1>
  <p>USDA System – Handbook 210 &nbsp;|&nbsp; Generated: {dt}</p>
</header>
<div class="meta">
  <span>📁 Output: {os.path.basename(output_fc)}</span>
  <span>📐 Cell Size: {cell_size} m</span>
  <span>📍 Slope input: {os.path.basename(slope_raster)} ({slope_unit})</span>
  <span>🗺 Zonal Units: {"✓ " + os.path.basename(land_units) if land_units else "✗ Cell-based"}</span>
</div>

<div class="container">

  <!-- KPIs -->
  <div class="card">
    <h2>📊 Summary Statistics</h2>
    <div class="total-box">
      <div class="kpi"><div class="val">{total_ha:,.0f}</div><div class="lbl">Total Area (ha)</div></div>
      <div class="kpi"><div class="val">{len([c for c in class_areas if class_areas[c]>0])}</div><div class="lbl">LCC Classes Present</div></div>
      <div class="kpi"><div class="val">{sum(class_counts.values()):,}</div><div class="lbl">Total Polygons</div></div>
      <div class="kpi"><div class="val">{len([l for l in optional_layers if l])}</div><div class="lbl">Limiting Factors Used</div></div>
    </div>
    <div><strong>Optional Factors Used:</strong><br><br>{opt_badges}</div>
  </div>

  <!-- Charts -->
  <div class="charts-row">
    <div class="chart-card">
      <h2>🥧 Area by LCC Class</h2>
      <canvas id="pieChart"></canvas>
    </div>
    <div class="chart-card">
      <h2>📊 Area Distribution (ha)</h2>
      <canvas id="barChart"></canvas>
    </div>
  </div>

  <!-- Detailed Table -->
  <div class="card">
    <h2>📋 Detailed Class Summary</h2>
    <div style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>Class</th><th>Name / الاسم</th><th>Area (ha)</th>
          <th>Coverage</th><th>Limitations</th><th>Suitable Uses</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows_html)}
      </tbody>
    </table>
    </div>
  </div>

  <!-- Class Reference Cards -->
  <div class="card">
    <h2>📖 USDA LCC Class Reference</h2>
    <div class="class-card-grid">
"""

    for cls, info in CLASS_INFO.items():
        text_col = "#fff" if cls >= 6 else "#222"
        html += f"""
      <div class="cc" style="border-left-color:{info['color']};background:{info['color']}18">
        <h3 style="color:{info['color']}">{info['name']}</h3>
        <div style="font-size:.82rem;color:#555">{info['arabic']}</div>
        <div class="sub"><strong>Limitations:</strong> {info['limits']}</div>
        <div class="sub"><strong>Uses:</strong> {info['uses']}</div>
      </div>"""

    # chart data
    labels_json = json.dumps(labels_js)
    areas_json  = json.dumps(areas_js)
    pcts_json   = json.dumps(pcts_js)
    colors_json = json.dumps(colors_js)

    html += f"""
    </div>
  </div>

  <!-- USDA Methodology Note -->
  <div class="card">
    <h2>📚 Methodology Note</h2>
    <p style="font-size:.9rem;line-height:1.7">
      This classification follows the <strong>USDA Land Capability Classification (LCC)</strong>
      system as described in <em>USDA Agriculture Handbook No. 210</em>.
      Land is assigned to one of eight capability classes (I–VIII) based on
      the <strong>maximum limitation principle</strong>: the most severe
      limitation of any factor determines the final class.
      Classes I–IV are suitable for cultivation (with increasing management requirements),
      Classes V–VII are not suitable for regular cultivation but support pasture/forestry/wildlife,
      and Class VIII is unsuitable for any productive use.
      <br><br>
      Subclasses denote the dominant limitation:
      <strong>e</strong> = erosion,
      <strong>w</strong> = excess water/drainage,
      <strong>s</strong> = soil limitations (depth, texture, salinity, stoniness),
      <strong>c</strong> = climate.
    </p>
  </div>

</div><!-- /container -->

<footer>
  Land Capability Classification Tool v3.0 &nbsp;•&nbsp;
  USDA Handbook 210 &nbsp;•&nbsp;
  Generated by ArcGIS Pro Python Toolbox &nbsp;•&nbsp; {dt}
</footer>

<script>
// ── Pie Chart ──────────────────────────────────────────────
const pieCtx = document.getElementById('pieChart').getContext('2d');
new Chart(pieCtx, {{
  type: 'doughnut',
  data: {{
    labels: {labels_json},
    datasets: [{{
      data: {pcts_json},
      backgroundColor: {colors_json},
      borderWidth: 2,
      borderColor: '#fff'
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'bottom', labels: {{ font: {{ size:11 }} }} }},
      tooltip: {{
        callbacks: {{
          label: ctx => ` ${{ctx.label}}: ${{ctx.parsed.toFixed(1)}}%`
        }}
      }}
    }}
  }}
}});

// ── Bar Chart ─────────────────────────────────────────────
const barCtx = document.getElementById('barChart').getContext('2d');
new Chart(barCtx, {{
  type: 'bar',
  data: {{
    labels: {labels_json},
    datasets: [{{
      label: 'Area (ha)',
      data: {areas_json},
      backgroundColor: {colors_json},
      borderRadius: 6,
      borderWidth: 0
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: ctx => ` ${{ctx.parsed.y.toLocaleString()}} ha`
        }}
      }}
    }},
    scales: {{
      y: {{
        beginAtZero: true,
        ticks: {{ callback: v => v.toLocaleString() + ' ha' }},
        grid: {{ color: '#eee' }}
      }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    return html

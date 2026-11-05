🌱 USDA Land Capability Classification (LCC) Tool for ArcGIS Pro
Land Capability Classification Tool – v3.0
📥 Installation in ArcGIS Pro
Open ArcGIS Pro
In the Catalog pane → right-click Toolboxes
Choose Add Toolbox
Browse to the LandCapability_USDA.pyt file and select it
The tool will appear under the name:
Land Capability Classification (USDA)
🔢 Tool Parameters
#
Name
Type
Description
1	Slope Raster	Required	Slope map (raster)
2	Slope Unit	Required	PERCENT or DEGREE
3	Soil Depth	Optional	Soil depth in centimeters
4	Drainage Class	Optional	Drainage class (1–6)
5	Flooding Frequency	Optional	Flooding frequency (0–4)
6	Erosion Hazard	Optional	Erosion hazard (0–3)
7	Soil Texture	Optional	Soil texture (1–5)
8	Salinity (EC)	Optional	Salinity in dS/m
9	Stoniness	Optional	Stones and rocks (0–3)
10	Climate Zone	Optional	Climate zone (1–4)
11	Land Units	Optional	Land unit polygons
12	Cell Size	Optional	Cell size (default 30 m)
13	Output Feature Class	Required	Output path
14	Report Folder	Optional	HTML report folder

📊 Codes for Optional Inputs
Drainage Class
Code
Meaning
1	Excessively drained
2	Well drained (best rating)
3	Moderately well drained
4	Imperfectly drained
5	Poorly drained
6	Very poorly drained

Flooding Frequency
| 0=None | 1=Rare | 2=Occasional | 3=Frequent | 4=Permanent |

Erosion Hazard
| 0=No hazard | 1=Moderate | 2=Severe | 3=Very severe |

Soil Texture
| 1=Loam/Silt (best) | 2=Clay Loam | 3=Sandy Loam | 4=Clay | 5=Sand/Gravel |

Climate Zone
| 1=Humid | 2=Semi-arid | 3=Arid | 4=Very arid |

🗺 Classification System (USDA Handbook 210)
Class
Description
Slope
Suitable Use
I	Excellent	0–2%	All crops
II	Good	2–6%	Most crops
III	Moderate	6–12%	Intensive cultivation
IV	Fair	12–18%	Limited cultivation
V	Not tillable	Level	Pasture, forestry
VI	Unsuitable	18–30%	Pasture, forestry
VII	Very unsuitable	30–45%	Forestry, wildlife
VIII	Completely barren	>45%	Wildlife only

⚙️ How the Tool Works
The tool uses the most-limiting-factor principle (maximum limitation):

Final class = the most restrictive limitation among all factors

Steps:

Classify the slope → initial class
Compute the penalty for each optional factor (0–3)
Add the highest penalty to the initial class
Clamp the result between 1 and 8
Convert the Raster → Polygon
Generate an interactive HTML report
📄 Outputs
Feature Class containing the following fields:
LCC_CLASS – class number (1–8)
LCC_NAME – English name
LCC_ARABIC – Arabic name
LCC_COLOR – HEX color code
LCC_LIMITS – limitations
LCC_USES – suitable uses
Interactive HTML report containing:
Pie chart of areas
Bar chart
Detailed table with percentages and hectares
Reference cards for each class
Methodological note
📋 Requirements
ArcGIS Pro 2.8 or later
Spatial Analyst license
Python 3.x (bundled with ArcGIS Pro)
USDA Land Capability Classification Tool v3.0 | Based on USDA Agriculture Handbook No. 210

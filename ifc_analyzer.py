import streamlit as st
import json
import re
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Set
import ifcopenshell
import plotly.graph_objects as go
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords
from nltk.chunk import ne_chunk
from nltk.tag import pos_tag
import spacy
import os

# Download required NLTK data with error handling
def download_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('corpora/stopwords')
        nltk.data.find('taggers/averaged_perceptron_tagger')
        nltk.data.find('corpora/wordnet')
    except LookupError:
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            nltk.download('averaged_perceptron_tagger', quiet=True)
            nltk.download('wordnet', quiet=True)
            nltk.download('maxent_ne_chunker', quiet=True)
            nltk.download('words', quiet=True)
        except Exception as e:
            st.error(f"Error downloading NLTK data: {str(e)}")

# Download NLTK data at startup
download_nltk_data()

class IFCAnalyzer:
    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))
        self.nlp = spacy.load('en_core_web_sm')
        
        # Enhanced component types with variations
        self.component_types = {
            "wall": ["wall", "partition", "barrier"],
            "door": ["door", "entrance", "exit", "gateway"],
            "window": ["window", "opening", "glazing"],
            "slab": ["slab", "floor", "ceiling", "deck"],
            "beam": ["beam", "girder", "joist"],
            "column": ["column", "pillar", "post"],
            "stair": ["stair", "stairway", "staircase", "steps"],
            "roof": ["roof", "roofing", "covering"],
            "space": ["space", "room", "area", "zone"],
            "pipe": ["pipe", "conduit", "duct"],
            "fixture": ["fixture", "fitting", "equipment"]
        }
        
        # Enhanced attribute keywords with context
        self.attribute_keywords = {
            "dimension": {
                "terms": ["height", "width", "length", "thickness", "diameter", "radius"],
                "units": ["mm", "cm", "m", "inch", "ft"],
                "comparators": ["greater than", "less than", "equal to", "at least", "at most"]
            },
            "location": {
                "terms": ["position", "placement", "coordinate", "location", "elevation"],
                "spatial": ["above", "below", "next to", "between", "adjacent"],
                "reference": ["ground", "floor", "ceiling", "wall"]
            },
            "material": {
                "terms": ["material", "composition", "made of", "constructed from"],
                "types": ["concrete", "steel", "wood", "glass", "aluminum"]
            },
            "performance": {
                "terms": ["rating", "class", "grade", "performance"],
                "metrics": ["fire", "acoustic", "thermal", "structural"]
            },
            "relationship": {
                "terms": ["connected", "adjacent", "attached", "contains", "supports"],
                "types": ["structural", "spatial", "logical", "physical"]
            }
        }
        
        # Relationship mapping for component connections
        self.relationship_mapping = {
            "supports": {"inverse": "supported by", "structural": True},
            "contains": {"inverse": "contained in", "spatial": True},
            "connects": {"inverse": "connected to", "bidirectional": True},
            "adjacent": {"inverse": "adjacent to", "bidirectional": True},
            "hosts": {"inverse": "hosted by", "physical": True}
        }
        
        # Spatial operators for location-based queries
        self.spatial_operators = {
            "above": {"axis": "z", "comparison": ">"},
            "below": {"axis": "z", "comparison": "<"},
            "next_to": {"axis": ["x", "y"], "distance": "near"},
            "between": {"type": "range", "axes": ["x", "y", "z"]},
            "inside": {"type": "containment", "check": "boundaries"}
        }
        
        self.locations = {
            "California": {
                "code_version": "2022 California Building Code",
                "jurisdiction": "California Building Standards Commission",
                "units": "imperial"
            },
            "New York": {
                "code_version": "2022 NYC Building Code",
                "jurisdiction": "NYC Department of Buildings",
                "units": "imperial"
            },
            "Texas": {
                "code_version": "2021 International Building Code with Texas Amendments",
                "jurisdiction": "Texas Department of Licensing and Regulation",
                "units": "imperial"
            },
            "International": {
                "code_version": "2021 International Building Code",
                "jurisdiction": "International Code Council",
                "units": "metric"
            }
        }
        
        self.current_location = "California"
        # Expanded IFC schema with comprehensive component information
        self.ifc_schema = {
            "IfcWall": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Height", "Width", "Length", "Material", "FireRating", "LoadBearing", "Insulation", "ThermalTransmittance", "AcousticRating", "Combustible", "SurfaceSpreadOfFlame", "ExtendToStructure", "LoadBearing", "Compartmentation"],
                "quantities": ["GrossFootprintArea", "NetVolume", "GrossVolume", "NetWeight", "GrossWeight", "GrossSideArea", "NetSideArea"],
                "relationships": ["ContainedInStructure", "HasOpenings", "ProvidesVoids", "HasCoverings", "HasProjections", "HasAssociations"],
                "requirements": {
                    "FireRating": {
                        "value": "2 hours",
                        "description": "Minimum fire rating for load-bearing walls",
                        "code_reference": "CBC Section 703.2"
                    },
                    "Insulation": {
                        "value": "R-13",
                        "description": "Minimum R-value for exterior walls",
                        "code_reference": "CBC Energy Code"
                    },
                    "Height": {
                        "value": "20 feet",
                        "description": "Maximum height between lateral supports",
                        "code_reference": "CBC Section 2109.2"
                    },
                    "Thickness": {
                        "value": "4 inches",
                        "description": "Minimum thickness for load-bearing walls",
                        "code_reference": "CBC Section 2109.1.1"
                    },
                    "AcousticRating": {
                        "value": "STC 50",
                        "description": "Minimum Sound Transmission Class rating for dwelling unit separation",
                        "code_reference": "CBC Section 1206.2"
                    }
                }
            },
            "IfcStair": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["NumberOfRiser", "NumberOfTreads", "RiserHeight", "TreadLength", "WalkingLineOffset", "TreadLengthAtOffset", "NosingLength", "WaistThickness", "Material"],
                "quantities": ["Length", "GrossVolume", "NetVolume", "GrossWeight", "NetWeight"],
                "relationships": ["ContainedInStructure", "HasCoverings", "HasAssociations"],
                "requirements": {
                    "RiserHeight": {
                        "value": "4-7 inches",
                        "description": "Maximum riser height for stairs",
                        "code_reference": "CBC Section 1011.5.2"
                    },
                    "TreadDepth": {
                        "value": "11 inches minimum",
                        "description": "Minimum tread depth",
                        "code_reference": "CBC Section 1011.5.2"
                    },
                    "Width": {
                        "value": "44 inches minimum",
                        "description": "Minimum width for public stairs",
                        "code_reference": "CBC Section 1011.2"
                    },
                    "Headroom": {
                        "value": "80 inches minimum",
                        "description": "Minimum headroom clearance",
                        "code_reference": "CBC Section 1011.3"
                    }
                }
            },
            "IfcWindow": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Height", "Width", "OperationType", "Material", "ThermalTransmittance", "GlazingAreas", "IsExternal", "FireRating", "SecurityRating", "SmokeStop"],
                "quantities": ["Area", "Weight"],
                "relationships": ["ContainedInStructure", "FillsVoid", "HasCoverings"],
                "requirements": {
                    "EmergencyEgress": {
                        "value": "5.7 sq ft minimum",
                        "description": "Minimum clear opening area for emergency escape",
                        "code_reference": "CBC Section 1030.2"
                    },
                    "SillHeight": {
                        "value": "44 inches maximum",
                        "description": "Maximum sill height from floor",
                        "code_reference": "CBC Section 1030.3"
                    },
                    "OpeningWidth": {
                        "value": "20 inches minimum",
                        "description": "Minimum clear opening width",
                        "code_reference": "CBC Section 1030.2.1"
                    },
                    "OpeningHeight": {
                        "value": "24 inches minimum",
                        "description": "Minimum clear opening height",
                        "code_reference": "CBC Section 1030.2.1"
                    }
                }
            },
            "IfcColumn": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Height", "Width", "Depth", "Material", "LoadBearing", "FireRating", "SectionProfile", "StructuralMaterial"],
                "quantities": ["Length", "CrossSectionArea", "OuterSurfaceArea", "GrossVolume", "NetVolume", "GrossWeight", "NetWeight"],
                "relationships": ["ContainedInStructure", "HasAssociations", "HasConnections"],
                "requirements": {
                    "FireProtection": {
                        "value": "1-3 hours",
                        "description": "Fire-resistance rating based on building type",
                        "code_reference": "CBC Table 601"
                    },
                    "Reinforcement": {
                        "value": "1-4% of gross area",
                        "description": "Required steel reinforcement for concrete columns",
                        "code_reference": "ACI 318-19"
                    },
                    "TieSpacing": {
                        "value": "16 bar diameters maximum",
                        "description": "Maximum spacing of lateral ties",
                        "code_reference": "ACI 318-19 Section 25.7.2"
                    }
                }
            }
        }
        
        self.property_units = {
            "Height": "mm",
            "Width": "mm",
            "Length": "mm",
            "Depth": "mm",
            "Thickness": "mm",
            "Diameter": "mm",
            "Area": "m²",
            "Volume": "m³",
            "Weight": "kg",
            "PressureRating": "psi",
            "FlowRate": "gpm",
            "LoadBearing": "boolean",
            "FireRating": "hours",
            "ThermalTransmittance": "W/(m²·K)",
            "NominalDiameter": "mm",
            "RiserHeight": "inches",
            "TreadLength": "inches",
            "NosingLength": "inches",
            "WaistThickness": "inches",
            "OpeningArea": "sq ft",
            "SillHeight": "inches",
            "OpeningWidth": "inches",
            "OpeningHeight": "inches",
            "CrossSectionArea": "sq in",
            "OuterSurfaceArea": "sq ft",
            "SectionProfile": "designation",
            "AcousticRating": "STC",
            "GlazingAreas": "sq ft"
        }
        
        self.current_file = None
        self.extracted_data = {}
        self.user_data = {}
        
        self.ifc_schema.update({
            "IfcBeam": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Height", "Width", "Length", "Material", "LoadBearing", "FireRating", "SectionProfile", "StructuralMaterial", "SpanLength", "RollRadius", "Slope"],
                "quantities": ["Length", "CrossSectionArea", "OuterSurfaceArea", "GrossVolume", "NetVolume", "GrossWeight", "NetWeight"],
                "relationships": ["ContainedInStructure", "HasAssociations", "HasConnections", "HasCoverings"],
                "requirements": {
                    "FireProtection": {
                        "value": "1-3 hours",
                        "description": "Fire-resistance rating based on building type",
                        "code_reference": "CBC Table 601"
                    },
                    "LoadBearing": {
                        "value": "Required",
                        "description": "Must be designed to support structural loads",
                        "code_reference": "CBC Section 1604"
                    },
                    "MinimumDepth": {
                        "value": "L/24",
                        "description": "Minimum depth for deflection control (L = span length)",
                        "code_reference": "ACI 318-19"
                    }
                }
            },
            "IfcRoof": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Material", "ThermalTransmittance", "IsExternal", "FireRating", "LoadBearing", "PitchAngle", "ProjectedArea", "SurfaceArea"],
                "quantities": ["GrossArea", "NetArea", "GrossVolume", "NetVolume", "Weight", "Perimeter"],
                "relationships": ["ContainedInStructure", "HasCoverings", "HasAssociations", "HasOpenings"],
                "requirements": {
                    "MinimumSlope": {
                        "value": "1/4:12",
                        "description": "Minimum slope for drainage",
                        "code_reference": "CBC Section 1507"
                    },
                    "FireRating": {
                        "value": "Class A, B, or C",
                        "description": "Required fire classification for roof assemblies",
                        "code_reference": "CBC Section 1505"
                    },
                    "ThermalValue": {
                        "value": "R-30ci",
                        "description": "Minimum thermal resistance for insulation",
                        "code_reference": "CBC Energy Code"
                    }
                }
            },
            "IfcSlab": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Material", "Thickness", "FireRating", "LoadBearing", "ThermalTransmittance", "AcousticRating", "SurfaceSpreadOfFlame"],
                "quantities": ["GrossArea", "NetArea", "GrossVolume", "NetVolume", "GrossWeight", "NetWeight", "Perimeter"],
                "relationships": ["ContainedInStructure", "HasCoverings", "HasAssociations", "HasOpenings"],
                "requirements": {
                    "MinimumThickness": {
                        "value": "4 inches",
                        "description": "Minimum thickness for structural concrete slabs",
                        "code_reference": "ACI 318-19"
                    },
                    "Reinforcement": {
                        "value": "As per design",
                        "description": "Minimum reinforcement requirements",
                        "code_reference": "ACI 318-19 Section 7.6"
                    },
                    "FireRating": {
                        "value": "2 hours",
                        "description": "Minimum fire rating for floor assemblies",
                        "code_reference": "CBC Section 711"
                    }
                }
            },
            "IfcRailing": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Height", "Material", "HandicapAccessible", "IsExternal", "LoadBearing", "FireRating"],
                "quantities": ["Length", "GrossVolume", "NetVolume", "GrossWeight", "NetWeight"],
                "relationships": ["ContainedInStructure", "HasAssociations"],
                "requirements": {
                    "Height": {
                        "value": "42 inches",
                        "description": "Minimum height for guards",
                        "code_reference": "CBC Section 1015.3"
                    },
                    "OpeningSize": {
                        "value": "4 inches maximum",
                        "description": "Maximum opening size in guards",
                        "code_reference": "CBC Section 1015.4"
                    },
                    "LoadResistance": {
                        "value": "50 pounds per linear foot",
                        "description": "Minimum load resistance for handrails",
                        "code_reference": "CBC Section 1607.8"
                    }
                }
            },
            "IfcDoor": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Height", "Width", "FireRating", "AccessibilityCompliant", "Operation", "Material", "IsExternal", "ThermalTransmittance", "SmokeControl"],
                "quantities": ["Height", "Width", "Area", "Weight"],
                "relationships": ["ContainedInStructure", "FillsOpening", "HasCoverings"],
                "requirements": {
                    "Width": {
                        "value": "32 inches",
                        "description": "Minimum clear width for accessibility",
                        "code_reference": "CBC Chapter 11B-404.2.3"
                    },
                    "Height": {
                        "value": "80 inches",
                        "description": "Minimum door height",
                        "code_reference": "CBC Section 1010.1.1"
                    },
                    "FireRating": {
                        "value": "90 minutes",
                        "description": "Required rating for exit enclosures",
                        "code_reference": "CBC Section 716.1"
                    },
                    "Threshold": {
                        "value": "0.5 inches",
                        "description": "Maximum threshold height",
                        "code_reference": "CBC Chapter 11B-404.2.5"
                    },
                    "ClosingSpeed": {
                        "value": "5 seconds",
                        "description": "Minimum time to close from 90 degrees",
                        "code_reference": "CBC Chapter 11B-404.2.8"
                    }
                }
            },
            "IfcCovering": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Material", "Thickness", "FireRating", "AcousticRating", "SurfaceSpreadOfFlame", "ThermalTransmittance"],
                "quantities": ["GrossArea", "NetArea", "GrossVolume", "NetVolume", "Weight"],
                "relationships": ["CoversSpaces", "CoversElements", "HasAssociations"],
                "requirements": {
                    "FireRating": {
                        "value": "As required",
                        "description": "Fire rating based on assembly type",
                        "code_reference": "CBC Section 703"
                    },
                    "FlameSpread": {
                        "value": "Class A, B, or C",
                        "description": "Surface burning characteristics",
                        "code_reference": "CBC Section 803"
                    },
                    "AcousticRating": {
                        "value": "NRC 0.70",
                        "description": "Minimum noise reduction coefficient for acoustic ceilings",
                        "code_reference": "ASTM C423"
                    }
                }
            },
            "IfcPipe": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["NominalDiameter", "Material", "WorkingPressure", "Temperature", "FlowDirection", "IsExternal", "HasInsulation"],
                "quantities": ["Length", "CrossSectionArea", "OuterSurfaceArea", "GrossWeight"],
                "relationships": ["ContainedInStructure", "HasPorts", "HasAssociations"],
                "requirements": {
                    "MinimumSlope": {
                        "value": "1/4 inch per foot",
                        "description": "Minimum slope for drainage pipes",
                        "code_reference": "UPC Section 708.0"
                    },
                    "Material": {
                        "value": "Approved materials",
                        "description": "Approved materials for water distribution",
                        "code_reference": "UPC Section 604.1"
                    },
                    "Insulation": {
                        "value": "R-3",
                        "description": "Minimum insulation for hot water pipes",
                        "code_reference": "Energy Code"
                    }
                }
            },
            "IfcDuctSegment": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["CrossSectionShape", "Width", "Height", "Material", "AirFlow", "Velocity", "PressureDrop", "HasInsulation"],
                "quantities": ["Length", "CrossSectionArea", "OuterSurfaceArea", "GrossWeight"],
                "relationships": ["ContainedInStructure", "HasPorts", "HasAssociations"],
                "requirements": {
                    "Velocity": {
                        "value": "2000 fpm maximum",
                        "description": "Maximum air velocity in main ducts",
                        "code_reference": "ASHRAE Fundamentals"
                    },
                    "Insulation": {
                        "value": "R-6",
                        "description": "Minimum insulation for supply ducts in unconditioned spaces",
                        "code_reference": "Energy Code"
                    },
                    "Material": {
                        "value": "Galvanized steel",
                        "description": "Standard material requirement",
                        "code_reference": "SMACNA Standards"
                    }
                }
            },
            "IfcLightFixture": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["PowerConsumption", "LightOutput", "ColorTemperature", "EmergencyBallast", "DimmingCapability", "LampType"],
                "quantities": ["GrossWeight"],
                "relationships": ["ContainedInStructure", "HasPorts", "HasAssociations"],
                "requirements": {
                    "EmergencyLighting": {
                        "value": "90 minutes",
                        "description": "Minimum emergency operation time",
                        "code_reference": "CBC Section 1008.3"
                    },
                    "IlluminationLevel": {
                        "value": "1 footcandle average",
                        "description": "Minimum illumination for egress",
                        "code_reference": "CBC Section 1008.2.1"
                    },
                    "EnergyEfficiency": {
                        "value": "90 lumens/watt",
                        "description": "Minimum luminous efficacy",
                        "code_reference": "Energy Code"
                    }
                }
            },
            "IfcSanitaryTerminal": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["Material", "MountingHeight", "WaterConsumption", "AccessibilityCompliant", "HasSensor"],
                "quantities": ["GrossWeight"],
                "relationships": ["ContainedInStructure", "HasPorts", "HasAssociations"],
                "requirements": {
                    "WaterConsumption": {
                        "value": "1.28 gpf",
                        "description": "Maximum water consumption for toilets",
                        "code_reference": "UPC Section 411.2"
                    },
                    "MountingHeight": {
                        "value": "17-19 inches",
                        "description": "Toilet seat height for accessibility",
                        "code_reference": "CBC Chapter 11B-604.4"
                    },
                    "ClearFloorSpace": {
                        "value": "60 x 56 inches",
                        "description": "Minimum clear floor space at water closets",
                        "code_reference": "CBC Chapter 11B-604.3"
                    }
                }
            },
            "IfcFireSuppressionTerminal": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["CoverageArea", "Temperature", "DischargePattern", "FlowRate", "PressureRating", "ResponseTime"],
                "quantities": ["GrossWeight"],
                "relationships": ["ContainedInStructure", "HasPorts", "HasAssociations"],
                "requirements": {
                    "Coverage": {
                        "value": "225 sq ft maximum",
                        "description": "Maximum coverage area per sprinkler",
                        "code_reference": "NFPA 13"
                    },
                    "FlowRate": {
                        "value": "0.1 gpm/sq ft",
                        "description": "Minimum design density for light hazard",
                        "code_reference": "NFPA 13"
                    },
                    "Spacing": {
                        "value": "15 feet maximum",
                        "description": "Maximum distance between sprinklers",
                        "code_reference": "NFPA 13"
                    }
                }
            },
            "IfcSpace": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["GrossFloorArea", "NetFloorArea", "GrossVolume", "NetVolume", "NetCeilingHeight", "FinishFloorHeight", "OccupancyType", "OccupancyNumber"],
                "quantities": ["Height", "FinishCeilingHeight", "GrossPerimeter", "NetPerimeter"],
                "relationships": ["ContainedInStructure", "HasCoverings", "HasOpenings", "BoundsSpaces"],
                "requirements": {
                    "MinimumArea": {
                        "value": "70 sq ft",
                        "description": "Minimum floor area for habitable rooms",
                        "code_reference": "CBC Section 1207.3"
                    },
                    "MinimumHeight": {
                        "value": "7 feet 6 inches",
                        "description": "Minimum ceiling height for habitable spaces",
                        "code_reference": "CBC Section 1207.2"
                    },
                    "Ventilation": {
                        "value": "0.35 air changes per hour",
                        "description": "Minimum ventilation rate",
                        "code_reference": "CBC Section 1202.1"
                    }
                }
            },
            "IfcZone": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["ZoneType", "OccupancyType", "SecurityLevel", "FireZone", "ThermalZone", "VentilationZone"],
                "quantities": ["GrossFloorArea", "NetFloorArea", "GrossVolume"],
                "relationships": ["ContainsSpaces", "HasAssociations"],
                "requirements": {
                    "FireCompartment": {
                        "value": "As required",
                        "description": "Fire compartment size limitations",
                        "code_reference": "CBC Section 707"
                    },
                    "OccupantLoad": {
                        "value": "Per Table 1004.5",
                        "description": "Maximum floor area allowance per occupant",
                        "code_reference": "CBC Section 1004"
                    },
                    "ExitAccess": {
                        "value": "200 feet maximum",
                        "description": "Maximum common path of egress travel",
                        "code_reference": "CBC Section 1006.2.1"
                    }
                }
            },
            "IfcStairFlight": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["NumberOfRiser", "NumberOfTreads", "RiserHeight", "TreadLength", "WalkingLineOffset", "TreadLengthAtOffset", "NosingLength"],
                "quantities": ["Length", "GrossVolume", "NetVolume", "GrossWeight"],
                "relationships": ["ContainedInStructure", "HasAssociations"],
                "requirements": {
                    "RiserHeight": {
                        "value": "4-7 inches",
                        "description": "Maximum riser height",
                        "code_reference": "CBC Section 1011.5.2"
                    },
                    "TreadDepth": {
                        "value": "11 inches minimum",
                        "description": "Minimum tread depth",
                        "code_reference": "CBC Section 1011.5.2"
                    },
                    "Uniformity": {
                        "value": "3/8 inch maximum",
                        "description": "Maximum variation in riser height or tread depth",
                        "code_reference": "CBC Section 1011.5.4"
                    }
                }
            },
            "IfcCurtainWall": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["ThermalTransmittance", "IsExternal", "FireRating", "AcousticRating", "SecurityRating", "SolarHeatGainCoefficient"],
                "quantities": ["Height", "Width", "GrossArea", "NetArea"],
                "relationships": ["ContainedInStructure", "HasOpenings", "HasCoverings"],
                "requirements": {
                    "ThermalPerformance": {
                        "value": "U-0.36",
                        "description": "Maximum U-factor for fixed fenestration",
                        "code_reference": "Energy Code Table 140.3-B"
                    },
                    "SHGC": {
                        "value": "0.25",
                        "description": "Maximum solar heat gain coefficient",
                        "code_reference": "Energy Code Table 140.3-B"
                    },
                    "FireResistance": {
                        "value": "As required",
                        "description": "Fire-resistance rating based on separation distance",
                        "code_reference": "CBC Section 705"
                    }
                }
            },
            "IfcElectricDistributionBoard": {
                "attributes": ["Name", "Description", "ObjectType", "Tag", "GlobalId"],
                "properties": ["MainVoltage", "NumberOfPhases", "NumberOfCircuits", "RatedCurrent", "IP_Rating", "HasSurgeProtection"],
                "quantities": ["GrossWeight"],
                "relationships": ["ContainedInStructure", "HasPorts", "HasAssociations"],
                "requirements": {
                    "WorkingSpace": {
                        "value": "30 inches wide minimum",
                        "description": "Minimum working space width",
                        "code_reference": "NEC Article 110.26"
                    },
                    "Height": {
                        "value": "6 feet 6 inches maximum",
                        "description": "Maximum height to operating handle",
                        "code_reference": "NEC Article 404.8"
                    },
                    "AFCI_Protection": {
                        "value": "Required",
                        "description": "Arc-fault circuit protection for specific circuits",
                        "code_reference": "NEC Article 210.12"
                    }
                }
            }
        })

        # Add new property units
        self.property_units.update({
            "GrossFloorArea": "sq ft",
            "NetFloorArea": "sq ft",
            "GrossVolume": "cu ft",
            "NetVolume": "cu ft",
            "NetCeilingHeight": "ft",
            "FinishFloorHeight": "ft",
            "OccupancyNumber": "persons",
            "SecurityLevel": "enum",
            "SHGC": "coefficient",
            "MainVoltage": "V",
            "RatedCurrent": "A",
            "IP_Rating": "IP##"
        })
        
    def set_location(self, location: str) -> bool:
        """Set the current location for building code requirements."""
        if location in self.locations:
            self.current_location = location
            return True
        return False

    def get_location_info(self) -> Dict:
        """Get information about the current location's building codes."""
        return self.locations.get(self.current_location, {})

    def convert_units(self, value: float, from_unit: str, to_unit: str) -> float:
        """Convert measurements between metric and imperial units."""
        conversions = {
            "mm_to_inches": lambda x: x / 25.4,
            "inches_to_mm": lambda x: x * 25.4,
            "m2_to_sqft": lambda x: x * 10.764,
            "sqft_to_m2": lambda x: x / 10.764,
            "m3_to_cuft": lambda x: x * 35.315,
            "cuft_to_m3": lambda x: x / 35.315,
            "kg_to_lbs": lambda x: x * 2.205,
            "lbs_to_kg": lambda x: x / 2.205
        }
        
        conversion_key = f"{from_unit}_to_{to_unit}"
        if conversion_key in conversions:
            return conversions[conversion_key](value)
        return value
        
    def load_file(self, file_data, file_type: str) -> bool:
        """Load and process uploaded file data."""
        try:
            if file_type == "ifc":
                # Save IFC file temporarily and load with ifcopenshell
                temp_path = "temp.ifc"
                with open(temp_path, "wb") as f:
                    f.write(file_data)
                self.current_file = ifcopenshell.open(temp_path)
                os.remove(temp_path)
                return self.process_ifc_file()
            elif file_type == "json":
                data = json.loads(file_data)
                self.current_file = data
                return self.process_json_file()
            return False
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
            return False
    
    def process_ifc_file(self) -> bool:
        """Process loaded IFC file and extract relevant information."""
        try:
            self.extracted_data = {}
            
            # Process each IFC entity type we're interested in
            for entity_type in self.ifc_schema.keys():
                entities = self.current_file.by_type(entity_type)
                self.extracted_data[entity_type] = []
                
                for entity in entities:
                    entity_data = {
                        "GlobalId": entity.GlobalId,
                        "Name": entity.Name if hasattr(entity, "Name") else None,
                        "Description": entity.Description if hasattr(entity, "Description") else None,
                        "Properties": {},
                        "Quantities": {},
                        "Relationships": []
                    }
                    
                    # Extract properties
                    if hasattr(entity, "IsDefinedBy"):
                        for definition in entity.IsDefinedBy:
                            if definition.is_a("IfcRelDefinesByProperties"):
                                props = definition.RelatingPropertyDefinition
                                if props.is_a("IfcPropertySet"):
                                    for prop in props.HasProperties:
                                        if hasattr(prop, "NominalValue"):
                                            entity_data["Properties"][prop.Name] = prop.NominalValue.wrappedValue
                    
                    # Extract quantities
                    if hasattr(entity, "IsDefinedBy"):
                        for definition in entity.IsDefinedBy:
                            if definition.is_a("IfcRelDefinesByProperties"):
                                props = definition.RelatingPropertyDefinition
                                if props.is_a("IfcElementQuantity"):
                                    for quantity in props.Quantities:
                                        if hasattr(quantity, "LengthValue"):
                                            entity_data["Quantities"][quantity.Name] = quantity.LengthValue
                                        elif hasattr(quantity, "AreaValue"):
                                            entity_data["Quantities"][quantity.Name] = quantity.AreaValue
                                        elif hasattr(quantity, "VolumeValue"):
                                            entity_data["Quantities"][quantity.Name] = quantity.VolumeValue
                    
                    # Extract relationships
                    if hasattr(entity, "ContainedInStructure"):
                        for rel in entity.ContainedInStructure:
                            if rel.is_a("IfcRelContainedInSpatialStructure"):
                                entity_data["Relationships"].append({
                                    "type": "ContainedIn",
                                    "related_object": rel.RelatingStructure.is_a(),
                                    "related_name": rel.RelatingStructure.Name if hasattr(rel.RelatingStructure, "Name") else None
                                })
                    
                    self.extracted_data[entity_type].append(entity_data)
            
            return len(self.extracted_data) > 0
        except Exception as e:
            st.error(f"Error processing IFC file: {str(e)}")
            return False
    
    def process_json_file(self) -> bool:
        """Process loaded JSON file and extract relevant information."""
        try:
            if isinstance(self.current_file, dict):
                self.user_data = self.current_file
                return True
            return False
        except Exception as e:
            st.error(f"Error processing JSON file: {str(e)}")
            return False
    
    def preprocess_query(self, query: str) -> Tuple[List[str], Dict[str, Any]]:
        """
        Enhanced query preprocessing with advanced NLP and pattern recognition
        """
        # Process with spaCy for advanced NLP
        doc = self.nlp(query.lower())
        
        # Extract components and their variations
        components = []
        for token in doc:
            for comp_type, variations in self.component_types.items():
                if token.text in variations or token.lemma_ in variations:
                    components.append(comp_type)
        
        # Extract numerical values with units and comparators
        numerical_patterns = []
        for token in doc:
            if token.like_num:
                next_token = token.nbor() if token.i + 1 < len(doc) else None
                if next_token and next_token.text in sum([kw["units"] for kw in self.attribute_keywords.values()], []):
                    numerical_patterns.append({
                        "value": float(token.text),
                        "unit": next_token.text,
                        "comparator": self._find_comparator(doc, token.i)
                    })
        
        # Extract spatial relationships
        spatial_relations = []
        for token in doc:
            if token.text in self.spatial_operators:
                relation = {
                    "type": token.text,
                    "components": self._find_related_components(doc, token.i)
                }
                spatial_relations.append(relation)
        
        # Extract material and performance requirements
        requirements = {
            "material": [],
            "performance": [],
            "relationship": []
        }
        
        for token in doc:
            # Check material requirements
            for material in self.attribute_keywords["material"]["types"]:
                if token.text == material or token.lemma_ == material:
                    requirements["material"].append(material)
            
            # Check performance requirements
            for metric in self.attribute_keywords["performance"]["metrics"]:
                if token.text == metric or token.lemma_ == metric:
                    requirements["performance"].append(metric)
            
            # Check relationships
            for rel_type in self.relationship_mapping:
                if token.text == rel_type or token.lemma_ == rel_type:
                    requirements["relationship"].append(rel_type)
        
        return components, {
            "numerical_patterns": numerical_patterns,
            "spatial_relations": spatial_relations,
            "requirements": requirements,
            "entities": [ent.text for ent in doc.ents]
        }
    
    def _find_comparator(self, doc, num_index: int) -> str:
        """Find comparison operators before a number"""
        comparators = sum([kw["comparators"] for kw in self.attribute_keywords.values() if "comparators" in kw], [])
        for i in range(max(0, num_index - 3), num_index):
            if doc[i].text in comparators:
                return doc[i].text
        return "equal to"
    
    def _find_related_components(self, doc, rel_index: int) -> List[Dict[str, str]]:
        """Find components related by a spatial operator"""
        related = []
        for i, token in enumerate(doc):
            if i != rel_index:
                for comp_type, variations in self.component_types.items():
                    if token.text in variations or token.lemma_ in variations:
                        related.append({
                            "type": comp_type,
                            "position": "before" if i < rel_index else "after"
                        })
        return related
    
    def search_components(self, query: str) -> List[Dict[str, Any]]:
        """
        Enhanced component search with advanced filtering and relationship analysis
        """
        components, query_info = self.preprocess_query(query)
        results = []
        
        # Search through extracted data
        for entity_type, entities in self.extracted_data.items():
            # Check if entity type matches requested components
            if not components or any(comp in entity_type.lower() for comp in components):
                for entity in entities:
                    # Initialize match score
                    match_score = 0
                    match_details = {}
                    
                    # Check numerical patterns
                    for pattern in query_info["numerical_patterns"]:
                        for prop_name, value in entity["Properties"].items():
                            if any(term in prop_name.lower() for term in self.attribute_keywords["dimension"]["terms"]):
                                match = self._check_numerical_match(value, pattern)
                                if match["matches"]:
                                    match_score += 1
                                    match_details[prop_name] = match
                    
                    # Check spatial relations
                    for relation in query_info["spatial_relations"]:
                        spatial_match = self._check_spatial_relation(entity, relation)
                        if spatial_match["matches"]:
                            match_score += 1
                            match_details["spatial"] = spatial_match
                    
                    # Check requirements
                    for req_type, req_values in query_info["requirements"].items():
                        if req_values:
                            req_match = self._check_requirements(entity, req_type, req_values)
                            if req_match["matches"]:
                                match_score += 1
                                match_details[req_type] = req_match
                    
                    # If component matches criteria, add to results
                    if match_score > 0 or not query_info["numerical_patterns"]:
                        result = {
                            "type": entity_type,
                            "id": entity["GlobalId"],
                            "name": entity["Name"],
                            "properties": entity["Properties"],
                            "quantities": entity["Quantities"],
                            "relationships": entity["Relationships"],
                            "match_score": match_score,
                            "match_details": match_details
                        }
                        results.append(result)
        
        # Sort results by match score
        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results
    
    def _check_numerical_match(self, value: float, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a value matches a numerical pattern"""
        if pattern["comparator"] == "greater than":
            matches = value > pattern["value"]
        elif pattern["comparator"] == "less than":
            matches = value < pattern["value"]
        elif pattern["comparator"] == "at least":
            matches = value >= pattern["value"]
        elif pattern["comparator"] == "at most":
            matches = value <= pattern["value"]
        else:  # equal to
            matches = abs(value - pattern["value"]) < 0.001
        
        return {
            "matches": matches,
            "value": value,
            "pattern": pattern
        }
    
    def _check_spatial_relation(self, entity: Dict[str, Any], relation: Dict[str, Any]) -> Dict[str, Any]:
        """Check if an entity satisfies a spatial relation"""
        matches = False
        details = {}
        
        if "placement" in entity["Properties"]:
            placement = entity["Properties"]["placement"]
            operator = self.spatial_operators[relation["type"]]
            
            if operator["type"] == "containment":
                # Check if entity is contained within boundaries
                matches = self._check_containment(placement, relation["components"])
                details["containment"] = "within bounds" if matches else "outside bounds"
            
            elif operator["type"] == "range":
                # Check if entity is between specified components
                matches = self._check_range(placement, relation["components"])
                details["range"] = "within range" if matches else "outside range"
            
            else:
                # Check directional relationships
                matches = self._check_direction(placement, relation["components"], operator)
                details["direction"] = relation["type"]
        
        return {
            "matches": matches,
            "relation": relation["type"],
            "details": details
        }
    
    def _check_requirements(self, entity: Dict[str, Any], req_type: str, values: List[str]) -> Dict[str, Any]:
        """Check if an entity meets specified requirements"""
        matches = False
        details = {}
        
        if req_type == "material":
            if "Material" in entity["Properties"]:
                material = entity["Properties"]["Material"].lower()
                matches = any(val in material for val in values)
                details["material"] = material
        
        elif req_type == "performance":
            for value in values:
                for prop_name, prop_value in entity["Properties"].items():
                    if value in prop_name.lower():
                        matches = True
                        details[value] = prop_value
        
        elif req_type == "relationship":
            for rel in entity["Relationships"]:
                if any(val in rel["type"].lower() for val in values):
                    matches = True
                    details[rel["type"]] = rel["related_name"]
        
        return {
            "matches": matches,
            "type": req_type,
            "details": details
        }
    
    def display_search_results(self, results: List[Dict[str, Any]]):
        """
        Enhanced search results display with detailed matching information
        """
        if not results:
            st.warning("No components found matching your search criteria.")
            return
        
        for result in results:
            with st.expander(f"{result['type']}: {result['name']} (Match Score: {result['match_score']})", expanded=True):
                # Basic Information
                st.markdown("### Basic Information")
                st.write(f"- ID: {result['id']}")
                st.write(f"- Type: {result['type']}")
                
                # Properties
                if result['properties']:
                    st.markdown("### Properties")
                    props_df = pd.DataFrame(
                        [(k, v, self.property_units.get(k, "-")) 
                         for k, v in result['properties'].items()],
                        columns=["Property", "Value", "Unit"]
                    )
                    st.table(props_df)
                
                # Match Details
                if result['match_details']:
                    st.markdown("### Match Details")
                    for category, details in result['match_details'].items():
                        st.write(f"**{category}:**")
                        if isinstance(details, dict):
                            for key, value in details.items():
                                st.write(f"- {key}: {value}")
                        else:
                            st.write(f"- {details}")
                
                # Relationships
                if result['relationships']:
                    st.markdown("### Relationships")
                    for rel in result['relationships']:
                        st.write(f"- {rel['type']} → {rel['related_name']}")
                
                # Code Compliance
                if 'requirements' in result:
                    st.markdown("### Code Compliance")
                    self.display_compliance_status(result['requirements'])

    def display_compliance_status(self, requirements: Dict[str, Any]):
        """
        Display component compliance status with building codes
        """
        st.subheader("Code Compliance Status")
        
        for req, data in requirements.items():
            status = data.get("compliance", "Unknown")
            if status == "Compliant":
                status_color = "green"
            elif status == "Non-compliant":
                status_color = "red"
            else:
                status_color = "yellow"
            
            st.markdown(f"""
                <div style='padding: 10px; border-left: 5px solid {status_color};'>
                    <strong>{req}:</strong><br>
                    Required: {data['value']}<br>
                    Status: {status}<br>
                    Reference: {data['code_reference']}
                </div>
            """, unsafe_allow_html=True)

def main():
    st.set_page_config(
        page_title="Construction Code Reference",
        page_icon="🏗️",
        layout="wide"
    )
    
    st.title("Construction Code Reference & Requirements 🏗️")
    
    # Initialize session state
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = IFCAnalyzer()
    
    # Create three main columns
    col1, col2 = st.columns([1, 2])
    
    # Left sidebar for navigation and filters
    with col1:
        st.header("Component Selection")
        
        # Location selection with immediate requirements update
        location = st.selectbox(
            "Select Location",
            options=list(st.session_state.analyzer.locations.keys()),
            index=0
        )
        st.session_state.analyzer.current_location = location
        
        # Component category selection
        component_category = st.selectbox(
            "Select Component Category",
            options=[
                "Structural Components",
                "Architectural Elements",
                "MEP Systems",
                "Fire Safety",
                "Accessibility Features"
            ]
        )
        
        # Specific component selection based on category
        component_options = {
            "Structural Components": ["Beam", "Column", "Slab", "Wall (Structural)", "Foundation"],
            "Architectural Elements": ["Wall (Partition)", "Door", "Window", "Stairs", "Railing"],
            "MEP Systems": ["HVAC", "Plumbing", "Electrical", "Fire Protection"],
            "Fire Safety": ["Fire Walls", "Fire Doors", "Sprinkler Systems", "Emergency Lighting"],
            "Accessibility Features": ["Ramps", "Accessible Routes", "Restrooms", "Signage"]
        }
        
        specific_component = st.selectbox(
            "Select Specific Component",
            options=component_options.get(component_category, [])
        )
        
        # Additional filters
        st.subheader("Additional Filters")
        occupancy_type = st.multiselect(
            "Occupancy Type",
            ["Residential", "Commercial", "Industrial", "Educational", "Healthcare"]
        )
        
        construction_type = st.selectbox(
            "Construction Type",
            ["Type I-A", "Type I-B", "Type II-A", "Type II-B", "Type III-A", "Type III-B", "Type IV", "Type V-A", "Type V-B"]
        )
    
    # Main content area
    with col2:
        if specific_component:
            st.header(f"{specific_component} Requirements")
            
            # Create tabs for different types of information
            tabs = st.tabs([
                "Dimensional Requirements",
                "Material Specifications",
                "Construction Details",
                "Code Requirements",
                "Installation Guide"
            ])
            
            # Dimensional Requirements Tab
            with tabs[0]:
                st.subheader("Dimensional Requirements")
                if specific_component in st.session_state.analyzer.ifc_schema:
                    component_data = st.session_state.analyzer.ifc_schema[specific_component]
                    if "requirements" in component_data:
                        for name, req in component_data["requirements"].items():
                            if any(dim in name.lower() for dim in ["height", "width", "depth", "thickness", "length"]):
                                st.info(f"""
                                **{name}**
                                - Required Value: {req['value']}
                                - Description: {req['description']}
                                - Code Reference: {req['code_reference']}
                                """)
            
            # Material Specifications Tab
            with tabs[1]:
                st.subheader("Material Specifications")
                st.markdown("""
                #### Approved Materials
                | Material Type | Minimum Grade | Standards Reference |
                |--------------|---------------|-------------------|
                | Concrete | 3000 PSI | ACI 318-19 |
                | Steel | Grade 50 | ASTM A992 |
                | Wood | No. 2 or Better | ANSI/AWC NDS-2018 |
                """)
                
                st.markdown("#### Material Properties")
                material_df = pd.DataFrame({
                    "Property": ["Compressive Strength", "Tensile Strength", "Fire Rating"],
                    "Requirement": ["As specified", "Per design", "2 hours minimum"],
                    "Test Method": ["ASTM C39", "ASTM A370", "UL 263"]
                })
                st.table(material_df)
            
            # Construction Details Tab
            with tabs[2]:
                st.subheader("Construction Details")
                st.markdown("#### Critical Dimensions")
                st.image("https://via.placeholder.com/400x300.png?text=Construction+Detail+Drawing")
                
                st.markdown("#### Connection Details")
                st.markdown("""
                1. **Primary Connections**
                   - Type: Bolted/Welded
                   - Specification: A325 bolts, E70XX electrodes
                   - Minimum Requirements: 2 bolts per connection
                
                2. **Secondary Connections**
                   - Type: As specified
                   - Minimum Edge Distance: 1.5 × bolt diameter
                   - Minimum Spacing: 3 × bolt diameter
                """)
            
            # Code Requirements Tab
            with tabs[3]:
                st.subheader("Code Requirements")
                code_info = st.session_state.analyzer.get_location_info()
                st.info(f"""
                **Applicable Code: {code_info['code_version']}**
                **Jurisdiction: {code_info['jurisdiction']}**
                """)
                
                if specific_component in st.session_state.analyzer.ifc_schema:
                    component_data = st.session_state.analyzer.ifc_schema[specific_component]
                    if "requirements" in component_data:
                        for name, req in component_data["requirements"].items():
                            st.success(f"""
                            #### {name}
                            - **Requirement:** {req['value']}
                            - **Description:** {req['description']}
                            - **Code Reference:** {req['code_reference']}
                            """)
            
            # Installation Guide Tab
            with tabs[4]:
                st.subheader("Installation Guide")
                st.markdown("""
                #### Pre-Installation Checklist
                1. [ ] Verify all materials meet specifications
                2. [ ] Check dimensional requirements
                3. [ ] Confirm connection details
                4. [ ] Review safety requirements
                
                #### Installation Steps
                1. **Preparation**
                   - Clean work area
                   - Verify tools and equipment
                   - Check safety equipment
                
                2. **Installation Sequence**
                   - Step-by-step guide
                   - Critical checkpoints
                   - Quality control measures
                
                3. **Post-Installation**
                   - Inspection requirements
                   - Documentation needed
                   - Testing procedures
                """)
                
                st.warning("""
                ⚠️ **Important Notes:**
                - Follow manufacturer's installation instructions
                - Comply with local building codes
                - Maintain proper documentation
                - Schedule required inspections
                """)

if __name__ == "__main__":
    main() 
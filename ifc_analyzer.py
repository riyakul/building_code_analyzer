import streamlit as st
import json
import re
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import ifcopenshell
import plotly.graph_objects as go
from sklearn.feature_extraction.text import TfidfVectorizer
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
        self.component_types = set([
            "wall", "door", "window", "slab", "beam", "column", "stair",
            "roof", "space", "zone", "pipe", "duct", "fixture"
        ])
        self.attribute_keywords = {
            "dimension": ["height", "width", "length", "thickness", "diameter", "radius"],
            "location": ["position", "placement", "coordinate", "location", "elevation"],
            "material": ["material", "composition", "made of", "constructed from"],
            "performance": ["rating", "class", "grade", "performance"],
            "relationship": ["connected", "adjacent", "attached", "contains", "supports"]
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
        Enhanced query preprocessing with entity recognition and attribute extraction
        """
        # Tokenize and lemmatize
        tokens = word_tokenize(query.lower())
        lemmatized = [self.lemmatizer.lemmatize(token) for token in tokens if token not in self.stop_words]
        
        # Extract named entities and patterns
        tagged = pos_tag(tokens)
        entities = ne_chunk(tagged)
        
        # Identify components and attributes
        components = []
        attributes = {}
        
        for token in lemmatized:
            if token in self.component_types:
                components.append(token)
        
        # Extract numerical values with units
        numerical_pattern = r'(\d+(?:\.\d+)?)\s*(feet|ft|meters|m|inches|in|mm|cm)'
        numerical_values = re.findall(numerical_pattern, query)
        
        # Identify requested attributes
        for category, keywords in self.attribute_keywords.items():
            if any(keyword in query.lower() for keyword in keywords):
                attributes[category] = True
        
        return components, {
            "attributes": attributes,
            "numerical_values": numerical_values,
            "entities": entities
        }

    def format_component_data(self, component: Dict[str, Any], include_details: bool = True) -> str:
        """
        Enhanced component data formatting with detailed information
        """
        details = []
        
        # Basic information
        if "Name" in component:
            details.append(f"**Name:** {component['Name']}")
        if "Description" in component:
            details.append(f"**Description:** {component['Description']}")
        
        # Numerical values and dimensions
        if "dimensions" in component:
            details.append("\n**Dimensions:**")
            for dim, value in component["dimensions"].items():
                details.append(f"- {dim}: {value}")
        
        # Location and placement
        if "placement" in component:
            details.append("\n**Spatial Placement:**")
            placement = component["placement"]
            details.append(f"- Location: ({placement.get('x', 0)}, {placement.get('y', 0)}, {placement.get('z', 0)})")
            if "rotation" in placement:
                details.append(f"- Rotation: {placement['rotation']} degrees")
        
        # Material properties
        if "material" in component:
            details.append("\n**Material Properties:**")
            for prop, value in component["material"].items():
                details.append(f"- {prop}: {value}")
        
        # Performance ratings
        if "ratings" in component:
            details.append("\n**Performance Ratings:**")
            for rating, value in component["ratings"].items():
                details.append(f"- {rating}: {value}")
        
        # Relationships
        if "relationships" in component:
            details.append("\n**Component Relationships:**")
            for rel in component["relationships"]:
                details.append(f"- {rel}")
        
        # Code requirements and compliance
        if "requirements" in component:
            details.append("\n**Building Code Requirements:**")
            for req, data in component["requirements"].items():
                details.append(f"- {req}:")
                details.append(f"  - Required: {data['value']}")
                details.append(f"  - Reference: {data['code_reference']}")
                if "compliance" in data:
                    details.append(f"  - Compliance: {data['compliance']}")
        
        return "\n".join(details)

    def search_components(self, query: str) -> List[Dict[str, Any]]:
        """
        Enhanced component search with detailed attribute matching
        """
        components, query_info = self.preprocess_query(query)
        results = []
        
        # Search through IFC schema and match components
        for component_type, data in self.ifc_schema.items():
            component_name = component_type.replace("Ifc", "").lower()
            if not components or component_name in components:
                # Create detailed component information
                component_info = {
                    "type": component_type,
                    "attributes": data.get("attributes", {}),
                    "properties": data.get("properties", {}),
                    "quantities": data.get("quantities", {}),
                    "relationships": data.get("relationships", []),
                    "requirements": data.get("requirements", {})
                }
                
                # Add placement information
                component_info["placement"] = {
                    "x": 0.0,  # Replace with actual values from IFC file
                    "y": 0.0,
                    "z": 0.0,
                    "rotation": 0.0
                }
                
                # Match requested attributes
                if query_info["attributes"]:
                    for category in query_info["attributes"]:
                        if category in data:
                            component_info[category] = data[category]
                
                results.append(component_info)
        
        return results

    def display_search_results(self, results: List[Dict[str, Any]]):
        """
        Enhanced search results display with detailed information
        """
        if not results:
            st.warning("No components found matching your search criteria.")
            return
        
        for i, result in enumerate(results):
            with st.expander(f"{result['type']} Details", expanded=True):
                # Display formatted component data
                st.markdown(self.format_component_data(result))
                
                # Add visual representation if available
                if "geometry" in result:
                    st.plotly_chart(self.create_3d_visualization(result))
                
                # Show compliance status
                if "requirements" in result:
                    self.display_compliance_status(result["requirements"])

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
        page_title="IFC Code Analyzer",
        page_icon="🏗️",
        layout="wide"
    )
    
    st.title("IFC Code Analyzer 🏗️")
    
    # Initialize session state
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = IFCAnalyzer()
    
    # Sidebar for location selection and file upload
    with st.sidebar:
        st.header("Settings")
        
        # Location selection
        location = st.selectbox(
            "Select Location",
            options=list(st.session_state.analyzer.locations.keys()),
            index=0
        )
        st.session_state.analyzer.current_location = location
        
        # File upload section
        st.header("File Upload")
        uploaded_file = st.file_uploader("Upload IFC or JSON file", type=['ifc', 'json'])
        
        if uploaded_file:
            try:
                if uploaded_file.type == "application/json":
                    st.session_state.analyzer.load_json_data(uploaded_file)
                else:
                    st.session_state.analyzer.load_ifc_file(uploaded_file)
                st.success("File loaded successfully!")
            except Exception as e:
                st.error(f"Error loading file: {str(e)}")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Component Search")
        search_query = st.text_input(
            "Search for components and requirements",
            placeholder="Example: 'Show me wall requirements with height greater than 10 feet'"
        )
        
        # Search help
        with st.expander("Search Help"):
            st.markdown("""
            **Search Tips:**
            - Search for specific components: "wall", "door", "window", etc.
            - Include dimensions: "walls higher than 10 feet"
            - Ask about locations: "position of beams"
            - Query materials: "concrete walls"
            - Check requirements: "fire rating requirements for doors"
            - Find relationships: "walls connected to columns"
            """)
        
        if search_query:
            with st.spinner('Searching...'):
                results = st.session_state.analyzer.search_components(search_query)
                st.session_state.analyzer.display_search_results(results)
    
    with col2:
        st.header("Building Code Reference")
        code_info = st.session_state.analyzer.locations[location]
        st.info(f"""
        **Current Building Code:**
        - Version: {code_info['code_version']}
        - Jurisdiction: {code_info['jurisdiction']}
        - Units: {code_info['units'].capitalize()}
        """)
        
        # Component quick reference
        st.subheader("Component Quick Reference")
        component_type = st.selectbox(
            "Select Component Type",
            options=[k for k in st.session_state.analyzer.ifc_schema.keys()]
        )
        
        if component_type:
            component_data = st.session_state.analyzer.ifc_schema[component_type]
            st.markdown(f"### {component_type} Requirements")
            
            if "requirements" in component_data:
                for req_name, req_data in component_data["requirements"].items():
                    st.markdown(f"""
                    **{req_name}**
                    - Value: {req_data['value']}
                    - {req_data['description']}
                    - Reference: {req_data['code_reference']}
                    """)

if __name__ == "__main__":
    main() 
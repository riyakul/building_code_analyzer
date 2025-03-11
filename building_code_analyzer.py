import streamlit as st
import json
import re
from typing import Dict, List, Optional
import pandas as pd
import csv
import io
import time
from difflib import get_close_matches
import os

class BuildingCodeAnalyzer:
    def __init__(self):
        self.components = {}
        self.quantities = {}
        self.guidelines = {}
        self.current_file = None
        self.built_in_data = {}
        self.building_codes = {}  # Store building codes by location
        self.current_location = None
        
        # Load built-in data files
        self.load_built_in_data()
        
        # Load building codes
        self.load_building_codes()
        
        self.ifc_database = {
            # Structural Elements
            "IfcFooting": {
                "name": "Foundation",
                "type": "Structural",
                "description": "Building foundation element",
                "properties": {
                    "dimensions": ["depth", "width", "length"],
                    "materials": ["concrete", "steel reinforcement"],
                    "requirements": ["minimum depth", "bearing capacity"]
                }
            },
            "IfcWall": {
                "name": "Wall",
                "type": "Structural",
                "description": "Vertical building element",
                "properties": {
                    "dimensions": ["height", "thickness", "length"],
                    "materials": ["brick", "concrete", "steel", "timber"],
                    "requirements": ["fire rating", "thermal resistance"]
                }
            },
            "IfcBeam": {
                "name": "Beam",
                "type": "Structural",
                "description": "Horizontal structural element",
                "properties": {
                    "dimensions": ["span", "depth", "width"],
                    "materials": ["steel", "concrete", "timber"],
                    "requirements": ["load capacity", "deflection limits"]
                }
            },
            "IfcColumn": {
                "name": "Column",
                "type": "Structural",
                "description": "Vertical structural element",
                "properties": {
                    "dimensions": ["height", "width", "depth"],
                    "materials": ["concrete", "steel", "timber"],
                    "requirements": ["axial load capacity", "buckling resistance"]
                }
            },
            # Building Services
            "IfcElectricalCircuit": {
                "name": "Electrical Circuit",
                "type": "Services",
                "description": "Electrical distribution system",
                "properties": {
                    "specifications": ["voltage", "current", "power"],
                    "requirements": ["circuit protection", "wire size"]
                }
            },
            "IfcDistributionSystem": {
                "name": "Distribution System",
                "type": "Services",
                "description": "Building service distribution system",
                "properties": {
                    "specifications": ["flow rate", "pressure"],
                    "requirements": ["insulation", "accessibility"]
                }
            },
            # Space Elements
            "IfcSpace": {
                "name": "Room",
                "type": "Space",
                "description": "Occupiable space",
                "properties": {
                    "dimensions": ["area", "height"],
                    "requirements": ["ventilation", "lighting"]
                }
            },
            "IfcBuildingStorey": {
                "name": "Floor",
                "type": "Space",
                "description": "Building floor level",
                "properties": {
                    "dimensions": ["height", "area"],
                    "requirements": ["fire separation", "accessibility"]
                }
            }
        }
        
        self.ifc_mapping = {
            # Structural Elements
            "foundation": "IfcFooting",
            "wall": "IfcWall",
            "beam": "IfcBeam",
            "column": "IfcColumn",
            "slab": "IfcSlab",
            "roof": "IfcRoof",
            
            # Building Services
            "electrical": "IfcElectricalCircuit",
            "plumbing": "IfcDistributionSystem",
            "hvac": "IfcDistributionSystem",
            "ventilation": "IfcDistributionSystem",
            
            # Space Elements
            "room": "IfcSpace",
            "floor": "IfcBuildingStorey",
            "building": "IfcBuilding",
            
            # Materials
            "concrete": "IfcMaterial",
            "steel": "IfcMaterial",
            "timber": "IfcMaterial",
            "brick": "IfcMaterial",
            
            # Properties
            "dimension": "IfcPropertySingleValue",
            "material": "IfcMaterialProperties",
            "thermal": "IfcThermalMaterialProperties",
            "structural": "IfcStructuralMaterialProperties"
        }
        
        # Common search terms and their related components
        self.search_aliases = {
            "structure": ["foundation", "wall", "beam", "column", "slab"],
            "services": ["electrical", "plumbing", "hvac", "ventilation"],
            "materials": ["concrete", "steel", "timber", "brick"],
            "spaces": ["room", "floor", "building"],
            "properties": ["dimension", "material", "thermal", "structural"]
        }

    def load_built_in_data(self):
        """Load all JSON files from the data directory."""
        try:
            data_dir = os.path.join(os.path.dirname(__file__), 'data')
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
                
            for filename in os.listdir(data_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(data_dir, filename)
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            # Store the data with the filename as the key (without .json extension)
                            key = os.path.splitext(filename)[0]
                            self.built_in_data[key] = data
                    except Exception as e:
                        st.warning(f"Error loading built-in file {filename}: {str(e)}")
                        continue
        except Exception as e:
            st.warning(f"Error accessing data directory: {str(e)}")

    def load_building_codes(self):
        """Load building code files from the building_codes directory."""
        try:
            codes_dir = os.path.join(os.path.dirname(__file__), 'data', 'building_codes')
            if not os.path.exists(codes_dir):
                os.makedirs(codes_dir)
                
            for filename in os.listdir(codes_dir):
                if filename.endswith('.json'):
                    location = os.path.splitext(filename)[0].replace('_', ' ').title()
                    file_path = os.path.join(codes_dir, filename)
                    try:
                        with open(file_path, 'r') as f:
                            self.building_codes[location] = json.load(f)
                    except Exception as e:
                        st.warning(f"Error loading building code for {location}: {str(e)}")
                        continue
        except Exception as e:
            st.warning(f"Error accessing building codes directory: {str(e)}")

    def load_file(self, file_data) -> bool:
        """Load and process JSON data from uploaded file."""
        try:
            data = json.loads(file_data)
            
            # Store the uploaded file data
            self.current_file = data
            
            # Clear existing data
            self.components.clear()
            self.quantities.clear()
            self.guidelines.clear()
            
            def process_node(node, path="", context=""):
                """Process each node in the JSON structure."""
                if isinstance(node, dict):
                    for key, value in node.items():
                        current_path = f"{path}.{key}" if path else key
                        current_context = f"{context} - {key}" if context else key
                        
                        # Create a component entry
                        component_info = {
                            "name": key,
                            "type": self.detect_component_type(key),
                            "path": current_path,
                            "context": current_context,
                            "details": {
                                "dimensions": [],
                                "materials": [],
                                "requirements": [],
                                "specifications": []
                            }
                        }
                        
                        # Process the value
                        if isinstance(value, dict):
                            # Extract direct properties
                            for prop_key, prop_value in value.items():
                                if prop_key in ["thickness", "height", "width", "depth", "area"]:
                                    component_info["details"]["dimensions"].append({
                                        "type": prop_key,
                                        "value": prop_value,
                                        "unit": "m" if prop_key in ["thickness", "height", "width", "depth"] else "m²"
                                    })
                                elif prop_key == "material":
                                    component_info["details"]["materials"].append({
                                        "name": prop_value,
                                        "context": current_context
                                    })
                                elif prop_key == "description":
                                    component_info["description"] = prop_value
                                    # Extract requirements from description
                                    if any(word in prop_value.lower() for word in ["must", "shall", "should", "require", "minimum", "maximum"]):
                                        component_info["details"]["requirements"].append({
                                            "requirement": prop_value,
                                            "type": "mandatory" if any(word in prop_value.lower() for word in ["must", "shall", "require"]) else "recommended",
                                            "context": current_context
                                        })
                            
                            # Store the component
                            self.components[current_path] = component_info
                            
                            # Recurse into nested structures
                            process_node(value, current_path, current_context)
                        elif isinstance(value, (int, float)):
                            # Store as quantity
                            self.quantities[current_path] = {
                                "value": value,
                                "unit": "units",
                                "component": current_path,
                                "context": current_context
                            }
                        elif isinstance(value, str):
                            # Store as guideline
                            self.guidelines[current_path] = {
                                "description": value,
                                "component": current_path,
                                "context": current_context
                            }
                
                elif isinstance(node, list):
                    for i, item in enumerate(node):
                        process_node(item, f"{path}[{i}]", context)
            
            # Process the data
            process_node(data)
            
            return len(self.components) > 0
            
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
            return False

    def detect_component_type(self, key: str) -> str:
        """Determine the type of a component based on its key."""
        try:
            key_lower = key.lower()
            if any(x in key_lower for x in ["wall", "beam", "column", "foundation", "roof", "floor", "ceiling"]):
                return "Structural"
            if any(x in key_lower for x in ["electrical", "plumbing", "hvac", "mechanical", "utility"]):
                return "Utilities"
            if any(x in key_lower for x in ["door", "window", "stairs", "elevator"]):
                return "Architectural"
            if any(x in key_lower for x in ["fire", "safety", "emergency", "exit"]):
                return "Safety"
            return "General"
        except Exception as e:
            st.warning(f"Error detecting component type for '{key}': {str(e)}")
            return "General"

    def extract_component_details(self, guideline_text: str) -> Dict:
        """Extract structured information from guideline text."""
        details = {
            "dimensions": [],
            "materials": [],
            "requirements": [],
            "placement": [],
            "specifications": []
        }
        
        # Extract numerical specifications with units
        numerical_specs = re.findall(
            r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|in|%|degrees?|MPa|PSI|kN|kPa|m²|m³|ft²|ft³|kW|A)", 
            guideline_text
        )
        
        # Common material keywords
        material_keywords = ["concrete", "steel", "timber", "wood", "brick", "metal", "aluminum", 
                           "copper", "PVC", "glass", "plasterboard", "insulation"]
        
        # Placement keywords
        placement_keywords = ["located", "installed", "mounted", "positioned", "placed", "between",
                            "above", "below", "near", "adjacent", "inside", "outside", "centers"]
        
        # Requirement keywords
        requirement_keywords = ["required", "minimum", "maximum", "must", "shall", "should",
                             "need", "necessary", "mandatory", "essential"]
        
        # Process the text line by line for better organization
        lines = guideline_text.lower().split('.')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for materials
            for material in material_keywords:
                if material in line:
                    details["materials"].append(line)
                    break
                    
            # Check for placement information
            for keyword in placement_keywords:
                if keyword in line:
                    details["placement"].append(line)
                    break
                    
            # Check for requirements
            for keyword in requirement_keywords:
                if keyword in line:
                    details["requirements"].append(line)
                    break
        
        # Process numerical specifications
        for value, unit in numerical_specs:
            spec = {"value": float(value), "unit": unit}
            if "dimension" in unit or unit in ["mm", "cm", "m", "ft", "in"]:
                details["dimensions"].append(spec)
            else:
                details["specifications"].append(spec)
        
        return details

    def get_ifc_code(self, component_key: str) -> str:
        """Get the corresponding IFC code for a component."""
        key_lower = component_key.lower()
        for term, ifc_code in self.ifc_mapping.items():
            if term in key_lower:
                return ifc_code
        return "IfcBuildingElement"  # Default fallback

    def _base_search(self, term: str) -> List[Dict]:
        """Base search implementation that works on the current analyzer's data."""
        if not self.components:
            return []

        results = []
        term_parts = term.lower().split('.')
        
        for comp_key, comp_data in self.components.items():
            comp_key_lower = comp_key.lower()
            should_include = False
            
            # Check if component matches search term
            if term.lower() == comp_key_lower:
                should_include = True
            elif all(part in comp_key_lower for part in term_parts):
                should_include = True
            elif any(part in comp_key_lower for part in term_parts):
                should_include = True
            elif comp_key in self.guidelines and any(part in str(self.guidelines[comp_key]).lower() for part in term_parts):
                should_include = True
            
            if should_include:
                result = {
                    "component": comp_key,
                    "type": self.detect_component_type(comp_key),
                    "ifc_code": self.get_ifc_code(comp_key),
                    "details": {}
                }
                
                # Add direct quantities if available
                if comp_key in self.quantities:
                    q = self.quantities[comp_key]
                    result["quantity"] = {
                        "value": q["value"],
                        "unit": q["unit"]
                    }
                
                # Extract structured information from guidelines
                if comp_key in self.guidelines:
                    result["details"] = self.extract_component_details(
                        self.guidelines[comp_key]["description"]
                    )
                
                results.append(result)
        
        return results

    def search(self, term: str) -> List[Dict]:
        """Search for components and extract structured information."""
        try:
            results = []
            if not term:
                return results

            # Clean and process the natural language query
            query = term.lower()
            
            # Extract key information from natural language query
            dimension_terms = ["width", "height", "depth", "length", "diameter", "size", "thickness", "area"]
            material_terms = ["made of", "material", "built with", "constructed with", "composition"]
            requirement_terms = ["requirement", "required", "must be", "should be", "minimum", "maximum", "at least", "no more than"]
            placement_terms = ["located", "installed", "mounted", "positioned", "placed", "between", "above", "below", "adjacent"]
            
            # Remove common question phrases
            query = re.sub(r'\b(i want to know|tell me|what is|show me|the)\b', '', query).strip()
            
            # Extract search focus
            search_focus = {
                "dimension": any(term in query for term in dimension_terms),
                "material": any(term in query for term in material_terms),
                "requirement": any(term in query for term in requirement_terms),
                "placement": any(term in query for term in placement_terms)
            }
            
            # Extract component name (last word or words after "of")
            component_name = query.split("of ")[-1].strip() if "of" in query else query.split()[-1]
            
            # Search through components
            for comp_key, comp_data in self.components.items():
                try:
                    should_include = False
                    comp_key_lower = comp_key.lower()
                    
                    # Check if component matches
                    if component_name in comp_key_lower:
                        should_include = True
                    
                    # Check guidelines and specifications
                    if comp_key in self.guidelines:
                        guideline = self.guidelines[comp_key]
                        if component_name in str(guideline).lower():
                            should_include = True
                    
                    if should_include:
                        result = {
                            "component": comp_key,
                            "type": comp_data.get("type", "Unknown"),
                            "details": {
                                "dimensions": [],
                                "materials": [],
                                "requirements": [],
                                "placement": [],
                                "specifications": []
                            }
                        }
                        
                        # Add context and path information
                        if "context" in comp_data:
                            result["context"] = comp_data["context"]
                        if "path" in comp_data:
                            result["path"] = comp_data["path"]
                        
                        # Add description if available
                        if "description" in comp_data:
                            result["description"] = comp_data["description"]
                        
                        # Extract numerical values with units
                        if comp_key in self.guidelines:
                            guideline_text = str(self.guidelines[comp_key])
                            numerical_specs = re.findall(
                                r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|in|%|degrees?|MPa|PSI|kN|kPa|m²|m³|ft²|ft³|kW|A)",
                                guideline_text
                            )
                            
                            for value, unit in numerical_specs:
                                spec = {
                                    "value": float(value),
                                    "unit": unit,
                                    "context": comp_data.get("context", "")
                                }
                                
                                # Categorize the specification
                                if unit in ["mm", "cm", "m", "ft", "in"]:
                                    result["details"]["dimensions"].append(spec)
                                elif unit in ["MPa", "PSI", "kN", "kPa"]:
                                    result["details"]["specifications"].append(spec)
                        
                        # Add dimensions from component data
                        if "dimensions" in comp_data:
                            result["details"]["dimensions"].extend(comp_data["dimensions"])
                        
                        # Add materials with context
                        if "materials" in comp_data:
                            result["details"]["materials"].extend(comp_data["materials"])
                        
                        # Add placement information
                        if "placement" in comp_data:
                            result["details"]["placement"].extend(comp_data["placement"])
                        elif comp_key in self.guidelines:
                            # Extract placement information from guidelines
                            guideline_text = str(self.guidelines[comp_key])
                            for term in placement_terms:
                                if term in guideline_text.lower():
                                    sentences = re.split(r'[.!?]+', guideline_text)
                                    for sentence in sentences:
                                        if term in sentence.lower():
                                            result["details"]["placement"].append(sentence.strip())
                        
                        # Add requirements with context
                        if "requirements" in comp_data:
                            result["details"]["requirements"].extend(comp_data["requirements"])
                        elif comp_key in self.guidelines:
                            # Extract requirements from guidelines
                            guideline_text = str(self.guidelines[comp_key])
                            for term in requirement_terms:
                                if term in guideline_text.lower():
                                    sentences = re.split(r'[.!?]+', guideline_text)
                                    for sentence in sentences:
                                        result["details"]["requirements"].append({
                                            "requirement": sentence.strip(),
                                            "type": "mandatory" if term in ["must", "required", "shall"] else "recommended",
                                            "context": comp_data.get("context", "")
                                        })
                        
                        # Add quantity information if available
                        if comp_key in self.quantities:
                            result["quantity"] = self.quantities[comp_key]
                        
                        results.append(result)
                        
                except Exception as e:
                    st.warning(f"Error processing component {comp_key}: {str(e)}")
                    continue
            
            # Search in building codes and IFC database
            try:
                building_code_results = self.search_building_codes(component_name)
                if building_code_results:
                    results.extend(building_code_results)
                    
                ifc_results = self.search_ifc_database(component_name)
                if ifc_results:
                    results.extend(ifc_results)
            except Exception as e:
                st.warning(f"Error searching external databases: {str(e)}")
            
            return results
            
        except Exception as e:
            st.error(f"Error in search function: {str(e)}")
            return []

    def display_dataset_info(self):
        """Display information about available built-in datasets."""
        if not self.built_in_data:
            st.info("No built-in datasets available.")
            return
            
        st.subheader("Available Built-in Datasets")
        for dataset_name, data in self.built_in_data.items():
            with st.expander(f"Dataset: {dataset_name}"):
                try:
                    # Create a temporary analyzer to process this dataset
                    temp_analyzer = BuildingCodeAnalyzer()
                    temp_analyzer._process_data(data)
                    
                    # Display statistics
                    st.metric("Components", len(temp_analyzer.components))
                    st.metric("Guidelines", len(temp_analyzer.guidelines))
                    st.metric("Quantities", len(temp_analyzer.quantities))
                    
                    # Display sample components
                    if temp_analyzer.components:
                        st.write("Sample components:")
                        sample_components = list(temp_analyzer.components.keys())[:5]
                        for comp in sample_components:
                            st.write(f"- {comp}")
                except Exception as e:
                    st.error(f"Error processing dataset {dataset_name}: {str(e)}")
                    continue

    def display_building_code_info(self):
        """Display information about available building codes."""
        if not self.building_codes:
            st.info("No building codes available. Please add building code files to the data/building_codes directory.")
            return
            
        st.subheader("Available Building Codes")
        for location, code_data in self.building_codes.items():
            with st.expander(f"Building Code: {location}"):
                try:
                    # Display statistics about the building code
                    sections = list(code_data.keys())
                    st.write("**Main Sections:**")
                    for section in sections:
                        st.write(f"- {section}")
                    
                    # Display sample requirements
                    st.write("\n**Sample Requirements:**")
                    def get_sample_requirements(d, max_samples=3, current=0):
                        samples = []
                        if not isinstance(d, dict) or current >= max_samples:
                            return samples
                        
                        for k, v in d.items():
                            if isinstance(v, dict):
                                if "requirement" in str(v).lower() or "minimum" in str(v).lower():
                                    samples.append(f"- {k}: {str(v)}")
                                if len(samples) >= max_samples:
                                    break
                                samples.extend(get_sample_requirements(v, max_samples, len(samples)))
                        return samples[:max_samples]
                    
                    samples = get_sample_requirements(code_data)
                    for sample in samples:
                        st.write(sample)
                        
                except Exception as e:
                    st.error(f"Error processing building code for {location}: {str(e)}")
                    continue

    def search_building_codes(self, query: str, location: Optional[str] = None) -> List[Dict]:
        """Search building codes with improved component search."""
        results = []
        query = query.lower()
        
        # Define component categories and their related terms
        component_categories = {
            "wall": {
                "terms": ["wall", "partition", "barrier", "enclosure"],
                "types": ["exterior", "interior", "fire", "load-bearing", "non-load-bearing", "shear"],
                "properties": ["height", "thickness", "width", "fire-rating", "insulation", "structural"]
            },
            "door": {
                "terms": ["door", "doorway", "entrance", "exit"],
                "types": ["exterior", "interior", "fire", "emergency", "sliding", "revolving"],
                "properties": ["width", "height", "clearance", "fire-rating", "accessibility"]
            },
            "window": {
                "terms": ["window", "glazing", "opening"],
                "types": ["exterior", "interior", "emergency", "fixed", "operable"],
                "properties": ["width", "height", "sill-height", "glazing-area", "ventilation"]
            },
            "foundation": {
                "terms": ["foundation", "footing", "base", "substructure"],
                "types": ["strip", "pad", "raft", "pile", "shallow", "deep"],
                "properties": ["depth", "width", "bearing-capacity", "reinforcement"]
            }
        }
        
        # Find matching component category
        target_category = None
        target_terms = []
        for category, info in component_categories.items():
            if any(term in query for term in info["terms"]):
                target_category = category
                target_terms = info["terms"]
                break
        
        if not target_category:
            return results
        
        def extract_requirements(data: Dict, path: str = "", context: str = "") -> List[Dict]:
            """Extract requirements from nested dictionary structure."""
            requirements = []
            
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    current_context = f"{context} - {key}" if context else key
                    
                    # Check if this node contains relevant information
                    key_lower = key.lower()
                    if any(term in key_lower for term in target_terms):
                        if isinstance(value, str):
                            # Extract numerical values with units
                            numerical = re.findall(
                                r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|in|%|degrees?|MPa|PSI|kN|kPa|m²|m³|ft²|ft³|kW|A)",
                                value.lower()
                            )
                            
                            requirement = {
                                "component": key,
                                "type": "requirement",
                                "path": current_path,
                                "context": current_context,
                                "value": value,
                                "numerical_values": [{"value": float(num), "unit": unit} for num, unit in numerical],
                                "category": "Unknown"
                            }
                            
                            # Categorize requirement
                            if any(word in value.lower() for word in ["height", "width", "thickness", "dimension"]):
                                requirement["category"] = "Dimensional"
                            elif any(word in value.lower() for word in ["fire", "safety", "emergency", "protection"]):
                                requirement["category"] = "Safety"
                            elif any(word in value.lower() for word in ["material", "concrete", "steel", "wood"]):
                                requirement["category"] = "Material"
                            elif any(word in value.lower() for word in ["install", "construct", "build", "place"]):
                                requirement["category"] = "Construction"
                            elif any(word in value.lower() for word in ["load", "strength", "capacity", "structural"]):
                                requirement["category"] = "Structural"
                            
                            requirements.append(requirement)
                        
                        elif isinstance(value, dict):
                            # If it's a dictionary, it might contain nested requirements
                            requirements.extend(extract_requirements(value, current_path, current_context))
                    
                    # Continue searching in nested structures
                    elif isinstance(value, (dict, list)):
                        requirements.extend(extract_requirements(value, current_path, current_context))
            
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, (dict, list)):
                        requirements.extend(extract_requirements(item, f"{path}[{i}]", context))
            
            return requirements
        
        # Search through each location's building codes
        if location:
            if location in self.building_codes:
                results.extend(extract_requirements(self.building_codes[location]))
        else:
            for loc, code_data in self.building_codes.items():
                location_results = extract_requirements(code_data)
                for result in location_results:
                    result["location"] = loc
                results.extend(location_results)
        
        return results

    def search_ifc_database(self, term: str) -> List[Dict]:
        """Search the IFC database for components matching the search term."""
        results = []
        term = term.lower()
        
        # Check direct IFC code matches
        for ifc_code, data in self.ifc_database.items():
            should_include = False
            
            # Check if the term matches the IFC code or name
            if term in ifc_code.lower() or term in data["name"].lower():
                should_include = True
            
            # Check if the term matches the type
            elif term in data["type"].lower():
                should_include = True
            
            # Check if the term matches any properties
            elif "properties" in data:
                for prop_type, props in data["properties"].items():
                    if isinstance(props, list) and any(term in prop.lower() for prop in props):
                        should_include = True
                        break
            
            # Check aliases
            for alias_category, aliases in self.search_aliases.items():
                if term in alias_category.lower():
                    if data["type"].lower() in [a.lower() for a in aliases]:
                        should_include = True
                        break
                elif any(term in alias.lower() for alias in aliases):
                    if any(alias.lower() in str(data).lower() for alias in aliases):
                        should_include = True
                        break
            
            if should_include:
                result = {
                    "component": data["name"],
                    "type": data["type"],
                    "ifc_code": ifc_code,
                    "description": data["description"],
                    "dataset": "IFC Database",
                    "details": {}
                }
                
                # Add properties as details
                if "properties" in data:
                    for prop_type, props in data["properties"].items():
                        if isinstance(props, list):
                            result["details"][prop_type] = [{"value": prop} for prop in props]
                
                results.append(result)
        
        return results

    def display_results(self, results: List[Dict]):
        """Display search results with comprehensive information and context."""
        try:
            if not results:
                st.warning("No matching components found.")
                return

            st.write(f"Found {len(results)} matching components:")
            
            # Display results in a more direct format
            for result in results:
                # Create a visual separator
                st.markdown("---")
                
                # Component Header with Type
                st.markdown(f"### {result.get('component', 'Unknown Component')} ({result.get('type', 'General')})")
                
                # Description if available
                if "description" in result:
                    st.markdown("**📝 Description:**")
                    st.markdown(result["description"])
                
                # Create three columns for better organization
                col1, col2, col3 = st.columns([1, 1, 1])
                
                with col1:
                    # Dimensions Section
                    if "details" in result and result["details"].get("dimensions"):
                        st.markdown("**📏 Dimensions**")
                        for dim in result["details"]["dimensions"]:
                            if isinstance(dim, dict):
                                value = dim.get("value", "N/A")
                                unit = dim.get("unit", "")
                                dim_type = dim.get("type", "dimension").replace("_", " ").title()
                                st.markdown(f"- {dim_type}: `{value} {unit}`")
                
                    # Materials Section
                    if "details" in result and result["details"].get("materials"):
                        st.markdown("\n**🧱 Materials**")
                        for material in result["details"]["materials"]:
                            if isinstance(material, dict):
                                mat_name = material.get("name", "N/A")
                                st.markdown(f"- {mat_name}")
                
                with col2:
                    # Requirements Section
                    if "details" in result and result["details"].get("requirements"):
                        st.markdown("**📋 Requirements**")
                        for req in result["details"]["requirements"]:
                            if isinstance(req, dict):
                                req_type = req.get("type", "general").upper()
                                requirement = req.get("requirement", "")
                                st.markdown(f"- [{req_type}] {requirement}")
                
                with col3:
                    # Technical Specifications
                    if "details" in result and result["details"].get("specifications"):
                        st.markdown("**⚙️ Technical Specs**")
                        for spec in result["details"]["specifications"]:
                            if isinstance(spec, dict):
                                value = spec.get("value", "N/A")
                                unit = spec.get("unit", "")
                                st.markdown(f"- `{value} {unit}`")
                
                # Quantities
                if "quantity" in result:
                    st.markdown("\n**📊 Quantity**")
                    qty = result["quantity"]
                    if isinstance(qty, dict):
                        value = qty.get("value", "N/A")
                        unit = qty.get("unit", "")
                        st.markdown(f"- Amount: `{value} {unit}`")
                
                # Bottom section for context and source
                st.markdown("**🔍 Location & Source Info**")
                if "context" in result:
                    st.markdown(f"- Location: `{result['context']}`")
                if "path" in result:
                    st.markdown(f"- Path: `{result['path']}`")
                source = result.get("dataset", "Building Database")
                st.markdown(f"- Source: `{source}`")

        except Exception as e:
            st.error(f"Error displaying results: {str(e)}")

def main():
    try:
        # Configure the page
        st.set_page_config(
            page_title="Building Code Analyzer",
            page_icon="🏗️",
            layout="wide"
        )

        st.title("Building Code Analyzer 🏗️")

        # Initialize session state safely
        if 'analyzer' not in st.session_state:
            try:
                st.session_state.analyzer = BuildingCodeAnalyzer()
                st.session_state.uploaded_file = None
                st.session_state.search_results = None
            except Exception as e:
                st.error(f"Error initializing application: {str(e)}")
                return

        # Main content area
        try:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("Search Components")
                search_query = st.text_input(
                    "Enter your search query",
                    placeholder="e.g., wall height requirements, door dimensions, foundation specifications"
                )
                
                if st.button("Search", type="primary"):
                    if search_query:
                        try:
                            with st.spinner('Searching...'):
                                results = st.session_state.analyzer.search(search_query)
                                st.session_state.analyzer.display_results(results)
                        except Exception as e:
                            st.error(f"Error during search: {str(e)}")
                    else:
                        st.warning("Please enter a search query")
                
                # Search tips
                with st.expander("💡 Search Tips"):
                    st.markdown("""
                    You can search by:
                    - Component names (wall, door, foundation)
                    - Component types (structural, utilities, architectural)
                    - Specifications (height, width, depth)
                    - Materials (concrete, steel, wood)
                    - Requirements (minimum, maximum, required)
                    
                    Examples:
                    - "wall height requirements"
                    - "door dimensions"
                    - "concrete foundation"
                    - "minimum ceiling height"
                    """)
        except Exception as e:
            st.error(f"Error in main content area: {str(e)}")
        
        # Sidebar for file upload and component overview
        try:
            with st.sidebar:
                st.header("Upload Component Data")
                uploaded_file = st.file_uploader(
                    "Upload JSON file",
                    type="json",
                    help="Upload a JSON file containing building component data"
                )
                
                if uploaded_file is not None and (st.session_state.uploaded_file != uploaded_file):
                    try:
                        with st.spinner('Processing data...'):
                            st.session_state.uploaded_file = uploaded_file
                            file_contents = uploaded_file.read().decode("utf-8")
                            if st.session_state.analyzer.load_file(file_contents):
                                st.success("File loaded successfully!")
                                
                                # Display component statistics safely
                                try:
                                    st.subheader("Component Statistics")
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.metric("Total Components", len(st.session_state.analyzer.components))
                                        st.metric("Guidelines", len(st.session_state.analyzer.guidelines))
                                    with col2:
                                        st.metric("Quantities", len(st.session_state.analyzer.quantities))
                                    
                                    # Display component types
                                    st.subheader("Component Types")
                                    component_types = {}
                                    for comp in st.session_state.analyzer.components.values():
                                        comp_type = comp.get("type", "Unknown")
                                        component_types[comp_type] = component_types.get(comp_type, 0) + 1
                                    
                                    for comp_type, count in component_types.items():
                                        st.write(f"- {comp_type}: {count} components")
                                except Exception as e:
                                    st.warning(f"Error displaying statistics: {str(e)}")
                            else:
                                st.error("Failed to process file")
                    except Exception as e:
                        st.error(f"Error processing file: {str(e)}")
        except Exception as e:
            st.error(f"Error in sidebar: {str(e)}")

    except Exception as e:
        st.error(f"Application error: {str(e)}")
        if st.button("Reset Application"):
            try:
                st.session_state.clear()
                st.rerun()
            except Exception as reset_error:
                st.error(f"Error resetting application: {str(reset_error)}")

if __name__ == "__main__":
    main() 
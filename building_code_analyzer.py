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
            return self._process_data(data)
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return False

    def _process_data(self, data) -> bool:
        """Process the JSON data and organize it into components, quantities, and guidelines."""
        try:
            # Clear existing data
            self.components.clear()
            self.quantities.clear()
            self.guidelines.clear()

            def extract_component_info(value, path):
                """Extract numerical values and requirements from a value."""
                info = {
                    "numerical_values": [],
                    "requirements": [],
                    "materials": [],
                    "dimensions": [],
                    "specifications": []
                }
                
                if isinstance(value, str):
                    # Extract numerical values with units
                    numerical = re.findall(
                        r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|in|%|degrees?|MPa|PSI|kN|kPa|m²|m³|ft²|ft³|kW|A)", 
                        value.lower()
                    )
                    for num, unit in numerical:
                        if unit in ["mm", "cm", "m", "ft", "in"]:
                            info["dimensions"].append({"value": float(num), "unit": unit})
                        else:
                            info["specifications"].append({"value": float(num), "unit": unit})
                    
                    # Extract materials
                    materials = ["concrete", "steel", "timber", "wood", "brick", "metal", 
                               "aluminum", "copper", "pvc", "glass", "plasterboard", "insulation"]
                    found_materials = [m for m in materials if m in value.lower()]
                    if found_materials:
                        info["materials"].extend(found_materials)
                    
                    # Extract requirements
                    if any(word in value.lower() for word in ["must", "shall", "should", "require", "minimum", "maximum"]):
                        info["requirements"].append(value)
                
                return info

            def recurse(d, parent=""):
                if not isinstance(d, (dict, list)):
                    return
                
                if isinstance(d, dict):
                    for k, v in d.items():
                        try:
                            key = f"{parent}.{k}" if parent else k
                            
                            # Store component info
                            component_info = {
                                "name": k,
                                "type": self.detect_component_type(k),
                                "path": key
                            }
                            
                            # Process values
                            if isinstance(v, (int, float)):
                                self.quantities[key] = {
                                    "value": v,
                                    "unit": "units",
                                    "component": key
                                }
                                component_info["quantity"] = {"value": v, "unit": "units"}
                            elif isinstance(v, str):
                                extracted_info = extract_component_info(v, key)
                                component_info.update(extracted_info)
                                self.guidelines[key] = {
                                    "description": v,
                                    "component": key,
                                    **extracted_info
                                }
                            
                            self.components[key] = component_info
                            
                            # Recurse into nested structures
                            if isinstance(v, (dict, list)):
                                recurse(v, key)
                        except Exception as e:
                            st.warning(f"Error processing key '{k}': {str(e)}")
                            continue
                            
                elif isinstance(d, list):
                    for i, item in enumerate(d):
                        try:
                            recurse(item, f"{parent}[{i}]")
                        except Exception as e:
                            st.warning(f"Error processing list item {i}: {str(e)}")
                            continue

            # Process the root data
            recurse(data)
            
            # Verify we have processed some data
            if not self.components:
                st.error("No components were processed from the data")
                return False
                
            return True
            
        except Exception as e:
            st.error(f"Error processing data: {str(e)}")
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
            dimension_terms = ["width", "height", "depth", "length", "diameter", "size"]
            material_terms = ["made of", "material", "built with", "constructed with"]
            requirement_terms = ["requirement", "required", "must be", "should be", "minimum", "maximum"]
            
            # Remove common question phrases
            query = query.replace("i want to know", "")
            query = query.replace("tell me", "")
            query = query.replace("what is", "")
            query = query.replace("show me", "")
            query = query.replace("the", "")
            query = query.strip()
            
            # Extract search focus
            search_focus = {
                "dimension": any(term in query for term in dimension_terms),
                "material": any(term in query for term in material_terms),
                "requirement": any(term in query for term in requirement_terms)
            }
            
            # Extract component name (last word or words after "of")
            component_name = query.split("of ")[-1].strip() if "of" in query else query
            
            # Create copies of data structures to prevent modification during iteration
            components_to_search = dict(self.components)
            guidelines_copy = dict(self.guidelines)
            quantities_copy = dict(self.quantities)
            
            # Search through components
            for comp_key, comp_data in components_to_search.items():
                try:
                    should_include = False
                    comp_key_lower = comp_key.lower()
                    
                    # Check if component matches
                    if component_name in comp_key_lower:
                        should_include = True
                    
                    # Check guidelines and specifications
                    if comp_key in guidelines_copy:
                        guideline = guidelines_copy[comp_key]
                        if component_name in str(guideline).lower():
                            should_include = True
                    
                    if should_include:
                        result = {
                            "component": comp_key,
                            "type": comp_data.get("type", "Unknown"),
                            "details": {}
                        }
                        
                        # Add relevant details based on search focus
                        if "details" in comp_data:
                            details = comp_data["details"]
                            if search_focus["dimension"] and "dimensions" in details:
                                result["details"]["dimensions"] = details["dimensions"]
                            if search_focus["material"] and "materials" in details:
                                result["details"]["materials"] = details["materials"]
                            if search_focus["requirement"] and "requirements" in details:
                                result["details"]["requirements"] = details["requirements"]
                        
                        # Add all details if no specific focus
                        if not any(search_focus.values()):
                            for key in ["dimensions", "materials", "requirements", "specifications"]:
                                if key in comp_data:
                                    result["details"][key] = comp_data[key]
                        
                        results.append(result)
                except Exception as e:
                    st.warning(f"Error processing component {comp_key}: {str(e)}")
                    continue
            
            # Search in IFC database with the same focus
            try:
                ifc_results = self.search_ifc_database(component_name)
                if ifc_results:
                    # Filter IFC results based on search focus
                    for result in ifc_results:
                        if "properties" in result:
                            filtered_props = {}
                            if search_focus["dimension"]:
                                filtered_props["dimensions"] = result["properties"].get("dimensions", [])
                            if search_focus["material"]:
                                filtered_props["materials"] = result["properties"].get("materials", [])
                            if search_focus["requirement"]:
                                filtered_props["requirements"] = result["properties"].get("requirements", [])
                            result["properties"] = filtered_props if any(filtered_props.values()) else result["properties"]
                    results.extend(ifc_results)
            except Exception as e:
                st.warning(f"Error searching IFC database: {str(e)}")
            
            # Search building codes with the same focus
            try:
                building_code_results = self.search_building_codes(component_name)
                if building_code_results:
                    results.extend(building_code_results)
            except Exception as e:
                st.warning(f"Error searching building codes: {str(e)}")
            
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
        
        # Expand search terms to include related terms
        component_terms = {
            "foundation": ["foundation", "footing", "base", "substructure"],
            "standpipe": ["standpipe", "stand pipe", "riser", "fire protection"],
            "door": ["door", "doorway", "entrance"],
            "window": ["window", "glazing", "opening"],
            "wall": ["wall", "partition", "barrier"],
            "ceiling": ["ceiling", "roof", "overhead"],
            "floor": ["floor", "flooring", "ground"],
            "bathroom": ["bathroom", "restroom", "toilet"],
            "kitchen": ["kitchen", "cooking", "food preparation"],
            "stair": ["stair", "stairway", "steps"],
            "elevator": ["elevator", "lift"],
            "corridor": ["corridor", "hallway", "passage"],
            "exit": ["exit", "egress", "escape"],
            "fire": ["fire", "flame", "burning", "sprinkler"]
        }
        
        # If no specific location is selected, include IFC database results
        if not location:
            # Search IFC database first
            for ifc_code, data in self.ifc_database.items():
                if any(term in query for term in component_terms.get("foundation", [])):
                    if "Foundation" in data["name"] or any(term in data["description"].lower() for term in component_terms["foundation"]):
                        results.append({
                            "component": "Foundation",
                            "type": "Structural",
                            "location": "IFC Database",
                            "value": data["description"],
                            "path": f"IFC.{ifc_code}",
                            "context": "IFC Standard Component",
                            "numerical_values": [],
                            "requirements": data["properties"].get("requirements", [])
                        })
        
        # Search through building codes
        def search_dict(d: Dict, path: str = "", context: str = None) -> None:
            if not isinstance(d, dict):
                return
                
            for k, v in d.items():
                k_lower = str(k).lower()
                new_path = f"{path}.{k}" if path else k
                new_context = k if context is None else f"{context} - {k}"
                
                # Check for foundation-related terms
                if any(term in k_lower or (isinstance(v, str) and term in v.lower()) 
                      for term in component_terms.get("foundation", [])):
                    
                    if isinstance(v, (str, int, float)):
                        results.append({
                            "component": k,
                            "type": "Structural",
                            "location": location or "Unknown Location",
                            "value": str(v),
                            "path": new_path,
                            "context": new_context,
                            "numerical_values": extract_numerical_values(str(v)),
                            "requirements": []
                        })
                    elif isinstance(v, dict):
                        # Handle nested requirements
                        for req_k, req_v in v.items():
                            if isinstance(req_v, (str, int, float)):
                                results.append({
                                    "component": k,
                                    "type": "Structural",
                                    "location": location or "Unknown Location",
                                    "requirement": req_k,
                                    "value": str(req_v),
                                    "path": f"{new_path}.{req_k}",
                                    "context": f"{new_context} - {req_k}",
                                    "numerical_values": extract_numerical_values(str(req_v)),
                                    "requirements": []
                                })
                
                # Continue searching nested structures
                search_dict(v, new_path, new_context)
        
        def extract_numerical_values(text: str) -> List[tuple]:
            """Extract numerical values with units from text."""
            if not isinstance(text, str):
                return []
            return re.findall(
                r'(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|in|%|degrees?|MPa|PSI|kN|kPa|m²|m³|ft²|ft³)',
                text.lower()
            )
        
        # Search through each location's building codes
        if location:
            if location in self.building_codes:
                search_dict(self.building_codes[location])
        else:
            for loc, code_data in self.building_codes.items():
                search_dict(code_data)
                # Update location in results
                for result in results:
                    if result["location"] == "Unknown Location":
                        result["location"] = loc
        
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
        """Display search results focusing on quantitative details."""
        try:
            if not isinstance(results, list):
                st.warning("Invalid results format")
                return
                
            if not results:
                st.warning("No matching components found.")
                return

            st.write(f"Found {len(results)} matching components:")
            
            # Group results by component type with error handling
            results_by_type = {}
            for idx, result in enumerate(results):
                try:
                    if not isinstance(result, dict):
                        continue
                        
                    comp_type = str(result.get("type", "Unknown"))
                    if comp_type not in results_by_type:
                        results_by_type[comp_type] = []
                    results_by_type[comp_type].append(result)
                except Exception as e:
                    st.warning(f"Error processing result {idx}: {str(e)}")
                    continue
            
            # Display results organized by type
            for comp_type, type_results in results_by_type.items():
                try:
                    if not isinstance(type_results, list) or not type_results:
                        continue
                        
                    st.subheader(f"{comp_type} Components")
                    
                    for result in type_results:
                        try:
                            if not isinstance(result, dict):
                                continue
                                
                            component_name = str(result.get("component", "Unknown Component"))
                            with st.expander(f"Component: {component_name}"):
                                # Display quantitative information first
                                details = result.get("details", {})
                                if not isinstance(details, dict):
                                    details = {}
                                
                                # Display dimensions with numerical values
                                dimensions = details.get("dimensions", [])
                                if isinstance(dimensions, list) and dimensions:
                                    st.write("📏 **Dimensions:**")
                                    for dim in dimensions:
                                        try:
                                            if isinstance(dim, dict):
                                                value = dim.get("value", "N/A")
                                                unit = dim.get("unit", "")
                                                st.write(f"- {value} {unit}")
                                        except Exception as e:
                                            st.warning(f"Error displaying dimension: {str(e)}")
                                
                                # Display specifications with numerical values
                                specs = details.get("specifications", [])
                                if isinstance(specs, list) and specs:
                                    st.write("⚙️ **Specifications:**")
                                    for spec in specs:
                                        try:
                                            if isinstance(spec, dict):
                                                value = spec.get("value", "N/A")
                                                unit = spec.get("unit", "")
                                                st.write(f"- {value} {unit}")
                                        except Exception as e:
                                            st.warning(f"Error displaying specification: {str(e)}")
                                
                                # Display direct quantities if available
                                quantity = result.get("quantity")
                                if isinstance(quantity, dict):
                                    st.write("🔢 **Quantity:**")
                                    try:
                                        value = quantity.get("value", "N/A")
                                        unit = quantity.get("unit", "")
                                        st.write(f"- {value} {unit}")
                                    except Exception as e:
                                        st.warning(f"Error displaying quantity: {str(e)}")
                                
                                # Display numerical values from requirements
                                requirements = details.get("requirements", [])
                                if isinstance(requirements, list) and requirements:
                                    try:
                                        numerical_reqs = []
                                        for req in requirements:
                                            if not isinstance(req, str):
                                                continue
                                            matches = re.findall(
                                                r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|in|%|degrees?|MPa|PSI|kN|kPa|m²|m³|ft²|ft³|kW|A)",
                                                str(req).lower()
                                            )
                                            if matches:
                                                numerical_reqs.extend(matches)
                                        
                                        if numerical_reqs:
                                            st.write("📋 **Quantitative Requirements:**")
                                            for value, unit in numerical_reqs:
                                                st.write(f"- {value} {unit}")
                                    except Exception as e:
                                        st.warning(f"Error processing requirements: {str(e)}")
                        except Exception as e:
                            st.warning(f"Error displaying component {component_name}: {str(e)}")
                            continue
                except Exception as e:
                    st.warning(f"Error displaying component type {comp_type}: {str(e)}")
                    continue
                    
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
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

            def recurse(d, parent=""):
                if not isinstance(d, (dict, list)):
                    return
                
                if isinstance(d, dict):
                    for k, v in d.items():
                        try:
                            key = f"{parent}.{k}" if parent else k
                            # Store component info
                            self.components[key] = {
                                "name": k,
                                "type": self.detect_component_type(k)
                            }
                            
                            # Process values
                            if isinstance(v, (int, float)):
                                self.quantities[key] = {
                                    "value": v,
                                    "unit": "units",
                                    "component": key
                                }
                            elif isinstance(v, str):
                                self.guidelines[key] = {
                                    "description": v,
                                    "component": key
                                }
                            
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
        results = []
        
        # First search in built-in data
        for dataset_name, data in self.built_in_data.items():
            try:
                # Create a temporary analyzer for this dataset
                temp_analyzer = BuildingCodeAnalyzer()
                temp_analyzer._process_data(data)
                
                # Search in this dataset
                dataset_results = temp_analyzer._base_search(term)
                
                # Add dataset name to results
                for result in dataset_results:
                    result["dataset"] = dataset_name
                    results.append(result)
            except Exception as e:
                st.warning(f"Error searching in dataset {dataset_name}: {str(e)}")
                continue
        
        # Then search in uploaded data
        if self.components:
            uploaded_results = self._base_search(term)
            for result in uploaded_results:
                result["dataset"] = "uploaded"
                results.append(result)
        
        return results

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
        """Search building codes with natural language processing."""
        results = []
        query = query.lower()
        
        # Extract key terms from the query
        component_terms = ["door", "window", "wall", "ceiling", "floor", "roof", "bathroom", "kitchen"]
        requirement_terms = ["height", "width", "depth", "distance", "clearance", "size", "dimension", 
                           "rating", "requirement", "minimum", "maximum", "spacing"]
        
        # Determine what component and requirement we're looking for
        target_component = next((term for term in component_terms if term in query), None)
        target_requirement = next((term for term in requirement_terms if term in query), None)
        
        # If location is specified, only search that location
        locations_to_search = [location] if location else self.building_codes.keys()
        
        for loc in locations_to_search:
            if loc not in self.building_codes:
                continue
                
            code_data = self.building_codes[loc]
            
            # Search through the building code data
            def search_dict(d, path="", context=None):
                if isinstance(d, dict):
                    for k, v in d.items():
                        new_path = f"{path}.{k}" if path else k
                        new_context = k if context is None else f"{context} - {k}"
                        
                        # Check if this key/value matches what we're looking for
                        k_lower = k.lower()
                        if target_component and target_component in k_lower:
                            if target_requirement:
                                # If we're looking for a specific requirement
                                if isinstance(v, dict):
                                    for req_k, req_v in v.items():
                                        if any(term in req_k.lower() for term in requirement_terms):
                                            results.append({
                                                "location": loc,
                                                "component": k,
                                                "requirement": req_k,
                                                "value": req_v,
                                                "path": new_path,
                                                "context": new_context
                                            })
                            else:
                                # If we just want component info
                                results.append({
                                    "location": loc,
                                    "component": k,
                                    "value": v,
                                    "path": new_path,
                                    "context": new_context
                                })
                        
                        # Recurse into nested structures
                        search_dict(v, new_path, new_context)
                elif isinstance(d, list):
                    for i, item in enumerate(d):
                        search_dict(item, f"{path}[{i}]", context)
            
            search_dict(code_data)
        
        return results

def export_results(results: List[Dict], format: str) -> Optional[tuple]:
    """Export results to CSV or JSON format."""
    if not results:
        return None
    
    if format == "CSV":
        output = io.StringIO()
        writer = csv.writer(output)
        # Write headers
        headers = ["Component", "Type", "Quantity", "Unit", "Guidelines", "Specifications"]
        writer.writerow(headers)
        
        # Write data
        for result in results:
            row = [
                result["component"],
                result["type"],
                result.get("quantity", {}).get("value", ""),
                result.get("quantity", {}).get("unit", ""),
                result.get("guidelines", ""),
                ", ".join([f"{s['value']} {s['unit']}" for s in result.get("specifications", [])])
            ]
            writer.writerow(row)
        
        return output.getvalue(), "text/csv"
    
    elif format == "JSON":
        return json.dumps(results, indent=2), "application/json"
    
    return None

def display_results(results: List[Dict]):
    """Display search results in a structured, easy-to-read format."""
    if not results:
        st.warning("No matching components found.")
        return

    st.write(f"Found {len(results)} components:")
    
    # Group results by dataset
    results_by_dataset = {}
    for result in results:
        dataset = result.get("dataset", "unknown")
        if dataset not in results_by_dataset:
            results_by_dataset[dataset] = []
        results_by_dataset[dataset].append(result)
    
    # Display results grouped by dataset
    for dataset, dataset_results in results_by_dataset.items():
        st.subheader(f"Results from {dataset.title()} Dataset:")
        
        for result in dataset_results:
            with st.expander(f"{result['component']} ({result['type']})"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    # Display IFC code
                    st.write(f"**🏷️ IFC Code:** {result['ifc_code']}")
                    
                    # Display description if available (from IFC database)
                    if "description" in result:
                        st.write(f"**📝 Description:** {result['description']}")
                    
                    # Display direct quantities
                    if "quantity" in result:
                        st.metric(
                            "Primary Quantity",
                            f"{result['quantity']['value']} {result['quantity']['unit']}"
                        )
                    
                    # Display dimensions
                    if "properties" in result and "dimensions" in result["properties"]:
                        st.write("**📏 Dimensions:**")
                        for dim in result["properties"]["dimensions"]:
                            st.write(f"- {dim}")
                    elif result["details"].get("dimensions"):
                        st.write("**📏 Dimensions:**")
                        for dim in result["details"]["dimensions"]:
                            st.write(f"- {dim['value']} {dim['unit']}")
                    
                    # Display materials
                    if "properties" in result and "materials" in result["properties"]:
                        st.write("**🧱 Materials:**")
                        for material in result["properties"]["materials"]:
                            st.write(f"- {material}")
                    elif result["details"].get("materials"):
                        st.write("**🧱 Materials:**")
                        for material in result["details"]["materials"]:
                            st.write(f"- {material.capitalize()}")
                
                with col2:
                    # Display specifications
                    if "properties" in result and "specifications" in result["properties"]:
                        st.write("**📊 Specifications:**")
                        for spec in result["properties"]["specifications"]:
                            st.write(f"- {spec}")
                    elif result["details"].get("specifications"):
                        st.write("**📊 Specifications:**")
                        for spec in result["details"]["specifications"]:
                            st.write(f"- {spec['value']} {spec['unit']}")
                    
                    # Display placement information
                    if result["details"].get("placement"):
                        st.write("**📍 Placement:**")
                        for placement in result["details"]["placement"]:
                            st.write(f"- {placement.capitalize()}")
                
                # Display requirements (full width)
                if "properties" in result and "requirements" in result["properties"]:
                    st.write("**⚠️ Requirements:**")
                    for req in result["properties"]["requirements"]:
                        st.write(f"- {req}")
                elif result["details"].get("requirements"):
                    st.write("**⚠️ Requirements:**")
                    for req in result["details"]["requirements"]:
                        st.write(f"- {req.capitalize()}")
    
    # Add export options
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.write("Export detailed analysis:")
    with col2:
        export_format = st.selectbox("Format", ["CSV", "JSON"], key="export_format")
    with col3:
        if st.button("Export", key="export_button"):
            if export_format == "CSV":
                # Create a structured CSV
                output = io.StringIO()
                writer = csv.writer(output)
                headers = ["Dataset", "Component", "Type", "Category", "Detail"]
                writer.writerow(headers)
                
                for result in results:
                    component = result["component"]
                    comp_type = result["type"]
                    dataset = result.get("dataset", "unknown")
                    
                    # Write quantities
                    if "quantity" in result:
                        writer.writerow([
                            dataset, component, comp_type, "Quantity",
                            f"{result['quantity']['value']} {result['quantity']['unit']}"
                        ])
                    
                    # Write details
                    for category, items in result["details"].items():
                        if items:
                            for item in items:
                                if isinstance(item, dict):
                                    detail = f"{item['value']} {item['unit']}"
                                else:
                                    detail = item.capitalize()
                                writer.writerow([dataset, component, comp_type, category.capitalize(), detail])
                
                st.download_button(
                    label="Download CSV",
                    data=output.getvalue(),
                    file_name="component_analysis.csv",
                    mime="text/csv"
                )
            else:
                st.download_button(
                    label="Download JSON",
                    data=json.dumps(results, indent=2),
                    file_name="component_analysis.json",
                    mime="application/json"
                )

def main():
    try:
        st.set_page_config(
            page_title="Building Code Analyzer",
            page_icon="🏗️",
            layout="wide"
        )

        st.title("Building Code Analyzer 🏗️")

        # Initialize session state safely
        if 'analyzer' not in st.session_state:
            st.session_state.analyzer = BuildingCodeAnalyzer()
            st.session_state.uploaded_file = None
            st.session_state.search_results = None
            st.session_state.last_search = None
            st.session_state.selected_location = None

        # Main content - Search interface first
        st.subheader("Search Building Requirements")
        
        # Location selector and search
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            search_term = st.text_input(
                "Enter your question",
                placeholder="e.g., what are the height requirements for a door in California?",
                help="You can ask about specific requirements like height, width, or any other specifications for building components."
            )
        
        with col2:
            locations = ["All Locations"] + sorted(list(st.session_state.analyzer.building_codes.keys()))
            selected_location = st.selectbox(
                "Select Location",
                locations,
                index=0
            )
            st.session_state.selected_location = None if selected_location == "All Locations" else selected_location
        
        with col3:
            search_button = st.button("Search", type="primary", use_container_width=True)
        
        # Add search tips
        with st.expander("💡 Search Tips"):
            st.markdown("""
            You can search by asking questions like:
            - What are the height requirements for doors in California?
            - What is the minimum ceiling height for bedrooms?
            - What are the window specifications for bathrooms?
            - What are the fire rating requirements for walls?
            
            Include specific details in your question:
            - Component (door, window, wall, etc.)
            - Requirement (height, width, rating, etc.)
            - Location (if specific to a region)
            """)
        
        if search_button and search_term:
            try:
                # Search building codes
                results = st.session_state.analyzer.search_building_codes(
                    search_term,
                    st.session_state.selected_location
                )
                
                if results:
                    st.session_state.search_results = results
                    display_results(results)
                else:
                    st.info(f"No specific requirements found for your query. Try rephrasing or check the search tips.")
            except Exception as e:
                st.error(f"Search error: {str(e)}")
                st.info("Please try rephrasing your question or check the search tips.")

        # Sidebar - Show available building codes and upload option
        with st.sidebar:
            # Show available building codes
            st.header("Available Building Codes")
            st.session_state.analyzer.display_building_code_info()
            
            st.markdown("---")
            
            # Upload option for new building codes
            st.header("Add Building Code")
            st.markdown("""
            You can add new building code files in JSON format.
            The file name should be the location (e.g., `california.json`).
            """)
            
            new_code_file = st.file_uploader("Upload Building Code (JSON)", type="json", key="code_uploader")
            
            if new_code_file is not None:
                try:
                    with st.spinner('Loading building code...'):
                        file_contents = new_code_file.read().decode("utf-8")
                        # Save to building_codes directory
                        filename = new_code_file.name
                        location = os.path.splitext(filename)[0].replace('_', ' ').title()
                        
                        # Save the file
                        codes_dir = os.path.join(os.path.dirname(__file__), 'data', 'building_codes')
                        if not os.path.exists(codes_dir):
                            os.makedirs(codes_dir)
                        
                        file_path = os.path.join(codes_dir, filename)
                        with open(file_path, 'w') as f:
                            f.write(file_contents)
                        
                        # Reload building codes
                        st.session_state.analyzer.load_building_codes()
                        st.success(f"Building code for {location} loaded successfully!")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error loading building code: {str(e)}")
            
            # Add IFC database statistics
            st.markdown("---")
            st.header("IFC Database")
            try:
                st.metric("Available IFC Components", len(st.session_state.analyzer.ifc_database))
            except Exception as e:
                st.error("Error accessing IFC database")
                st.session_state.analyzer = BuildingCodeAnalyzer()

    except Exception as e:
        st.error(f"Application error occurred: {str(e)}")
        st.info("Please refresh the page to restart the application.")
        if st.button("Clear Session State and Refresh"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main() 
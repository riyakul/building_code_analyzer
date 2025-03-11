import streamlit as st
import json
import re
from typing import Dict, List, Optional
import pandas as pd
import csv
import io
import time
from difflib import get_close_matches

class BuildingCodeAnalyzer:
    def __init__(self):
        self.components = {}
        self.quantities = {}
        self.guidelines = {}
        self.current_file = None
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

    def smart_search(self, query: str) -> List[Dict]:
        """Enhanced search with IFC database priority and natural language processing."""
        results = []
        query = query.lower()
        
        # First, search IFC database
        ifc_results = self.search_ifc_database(query)
        if ifc_results:
            return ifc_results
            
        # If no IFC results, check uploaded data
        if not self.components:
            st.warning("No data loaded. Please upload a file first.")
            return []

        # Check for category-based searches
        for category, components in self.search_aliases.items():
            if category in query:
                for comp in components:
                    if comp in self.components:
                        results.extend(self.search(comp))
                return results

        # Check for IFC code searches
        if "ifc" in query:
            for comp_key, comp_data in self.components.items():
                ifc_code = self.get_ifc_code(comp_key)
                if ifc_code.lower() in query:
                    results.extend(self.search(comp_key))
            return results

        # Fuzzy matching for component names
        component_names = list(self.components.keys())
        matches = get_close_matches(query, component_names, n=3, cutoff=0.6)
        
        for match in matches:
            results.extend(self.search(match))

        # If no fuzzy matches, try direct search
        if not results:
            results = self.search(query)

        return results

    def search(self, term: str) -> List[Dict]:
        """Search for components and extract structured information."""
        if not self.components:
            st.warning("No data loaded. Please upload a file first.")
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

    def search_ifc_database(self, query: str) -> List[Dict]:
        """Search the IFC database for matching components."""
        results = []
        query = query.lower()
        
        # Direct IFC code search
        if query.startswith("ifc"):
            for ifc_code, data in self.ifc_database.items():
                if ifc_code.lower() == query:
                    results.append({
                        "component": data["name"],
                        "type": data["type"],
                        "ifc_code": ifc_code,
                        "description": data["description"],
                        "properties": data["properties"]
                    })
                    return results
        
        # Search by component name or description
        for ifc_code, data in self.ifc_database.items():
            if (query in data["name"].lower() or 
                query in data["description"].lower() or
                query in data["type"].lower()):
                results.append({
                    "component": data["name"],
                    "type": data["type"],
                    "ifc_code": ifc_code,
                    "description": data["description"],
                    "properties": data["properties"]
                })
            
            # Search in properties
            for category, props in data["properties"].items():
                if isinstance(props, list) and any(query in prop.lower() for prop in props):
                    if not any(r["ifc_code"] == ifc_code for r in results):  # Avoid duplicates
                        results.append({
                            "component": data["name"],
                            "type": data["type"],
                            "ifc_code": ifc_code,
                            "description": data["description"],
                            "properties": data["properties"]
                        })
        
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
    
    for result in results:
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
                headers = ["Component", "Type", "Category", "Detail"]
                writer.writerow(headers)
                
                for result in results:
                    component = result["component"]
                    comp_type = result["type"]
                    
                    # Write quantities
                    if "quantity" in result:
                        writer.writerow([
                            component, comp_type, "Quantity",
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
                                writer.writerow([component, comp_type, category.capitalize(), detail])
                
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

        # Main content - Search interface first
        st.subheader("Search Building Components")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            search_term = st.text_input(
                "Enter search term",
                placeholder="e.g., foundation, wall, electrical, or IFC code",
                help="You can search by component name, category, or IFC code. Try natural language queries like 'show me all structural elements' or 'find electrical components'"
            )
        
        with col2:
            search_button = st.button("Search", type="primary", use_container_width=True)
        
        # Add search tips
        with st.expander("💡 Search Tips"):
            st.markdown("""
            You can search using:
            - Component names (e.g., 'foundation', 'wall')
            - Categories (e.g., 'structure', 'services', 'materials')
            - IFC codes (e.g., 'IfcWall', 'IfcBeam')
            - Natural language (e.g., 'show me all structural elements')
            - Properties (e.g., 'dimensions', 'materials')
            """)
        
        if search_button and search_term:
            try:
                # First try searching the IFC database
                results = st.session_state.analyzer.search_ifc_database(search_term)
                
                # If we have uploaded data, also search that
                if hasattr(st.session_state.analyzer, 'components') and len(st.session_state.analyzer.components) > 0:
                    user_data_results = st.session_state.analyzer.smart_search(search_term)
                    if user_data_results:
                        results.extend(user_data_results)
                
                st.session_state.search_results = results
                st.session_state.last_search = search_term
                
                if results:
                    display_results(results)
                else:
                    st.info(f"No results found for '{search_term}'. Try a different search term or check the search tips.")
            except Exception as e:
                st.error(f"Search error: {str(e)}")
                st.info("Please try a different search term or check the search tips.")

        # Sidebar - Move file upload to sidebar
        with st.sidebar:
            st.header("Additional Data")
            st.markdown("""
            The search works with the built-in IFC database by default.
            You can optionally upload your own building data for more detailed analysis.
            """)
            
            uploaded_file = st.file_uploader("Upload Additional Data (JSON)", type="json", key="json_uploader")
            
            if uploaded_file is not None and (st.session_state.uploaded_file != uploaded_file):
                try:
                    with st.spinner('Loading file...'):
                        st.session_state.uploaded_file = uploaded_file
                        file_contents = uploaded_file.read().decode("utf-8")
                        st.info("File read successfully, processing data...")
                        if st.session_state.analyzer.load_file(file_contents):
                            st.success("File loaded successfully!")
                            time.sleep(1)  # Give UI time to update
                            st.rerun()
                        else:
                            st.error("Failed to process the file. Please check the file format.")
                except json.JSONDecodeError as je:
                    st.error("Invalid JSON file. Please check the file format.")
                    st.session_state.analyzer = BuildingCodeAnalyzer()
                except Exception as e:
                    st.error(f"Error loading file: {str(e)}")
                    st.session_state.analyzer = BuildingCodeAnalyzer()
            
            if hasattr(st.session_state.analyzer, 'components') and len(st.session_state.analyzer.components) > 0:
                st.markdown("---")
                st.header("Uploaded Data Statistics")
                try:
                    st.metric("Components", len(st.session_state.analyzer.components))
                    st.metric("Guidelines", len(st.session_state.analyzer.guidelines))
                    st.metric("Quantities", len(st.session_state.analyzer.quantities))
                except Exception as e:
                    st.error("Error displaying statistics")
                    st.session_state.analyzer = BuildingCodeAnalyzer()

            # Add IFC database statistics
            st.markdown("---")
            st.header("IFC Database")
            try:
                st.metric("Available IFC Components", len(st.session_state.analyzer.ifc_database))
            except Exception as e:
                st.error("Error accessing IFC database")
                st.session_state.analyzer = BuildingCodeAnalyzer()
            
            # Component type filter
            st.markdown("---")
            st.header("Filter by Type")
            try:
                component_types = {"All", "Structural", "Services", "Space"}
                selected_type = st.selectbox("Select component type", sorted(list(component_types)))
                
                if selected_type != "All":
                    filtered_results = []
                    for ifc_code, data in st.session_state.analyzer.ifc_database.items():
                        if data["type"] == selected_type:
                            filtered_results.append({
                                "component": data["name"],
                                "type": data["type"],
                                "ifc_code": ifc_code,
                                "description": data["description"],
                                "properties": data["properties"]
                            })
                    
                    if filtered_results:
                        st.session_state.search_results = filtered_results
                        display_results(filtered_results)
                    else:
                        st.warning(f"No components found of type: {selected_type}")
            except Exception as e:
                st.error("Error in component filtering")
                st.info("Please try searching for components instead.")

    except Exception as e:
        st.error(f"Application error occurred: {str(e)}")
        st.info("Please refresh the page to restart the application.")
        if st.button("Clear Session State and Refresh"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main() 
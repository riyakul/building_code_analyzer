import streamlit as st
import json
import re
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import ifcopenshell
import plotly.graph_objects as go
from sklearn.feature_extraction.text import TfidfVectorizer
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import os

# Download required NLTK data with error handling
def download_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        try:
            nltk.download('punkt', quiet=True)
        except Exception as e:
            st.error(f"Error downloading NLTK punkt: {str(e)}")
            
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        try:
            nltk.download('stopwords', quiet=True)
        except Exception as e:
            st.error(f"Error downloading NLTK stopwords: {str(e)}")

# Download NLTK data at startup
download_nltk_data()

class IFCAnalyzer:
    def __init__(self):
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
        # Extended IFC schema with more components and their requirements
        self.ifc_schema = {
            "IfcWall": {
                "attributes": ["Name", "Description", "ObjectType"],
                "properties": ["Height", "Width", "Length", "Material", "FireRating", "LoadBearing", "Insulation"],
                "quantities": ["GrossFootprintArea", "NetVolume", "GrossVolume"],
                "relationships": ["ContainedInStructure", "HasOpenings"],
                "requirements": {
                    "FireRating": "Minimum 2 hours for load-bearing walls",
                    "Insulation": "R-value minimum 13 for exterior walls",
                    "Height": "Maximum height between supports: 20 feet",
                    "Thickness": "Minimum 4 inches for load-bearing walls"
                }
            },
            "IfcStandpipe": {
                "attributes": ["Name", "Description", "ObjectType"],
                "properties": ["Diameter", "Material", "PressureRating", "FlowRate"],
                "quantities": ["Length", "Weight"],
                "relationships": ["ServesFloor", "ConnectedTo"],
                "requirements": {
                    "Diameter": "Minimum 4 inches for Class I and III systems",
                    "PressureRating": "Minimum working pressure 175 psi",
                    "FlowRate": "Minimum 500 GPM for first standpipe, 250 GPM for each additional",
                    "Spacing": "Maximum 200 feet between standpipes"
                }
            },
            "IfcDoor": {
                "attributes": ["Name", "Description", "ObjectType"],
                "properties": ["Height", "Width", "FireRating", "AccessibilityCompliant"],
                "quantities": ["Area"],
                "relationships": ["ContainedInStructure", "FillsOpening"],
                "requirements": {
                    "Width": "Minimum 32 inches clear width",
                    "Height": "Minimum 80 inches",
                    "FireRating": "90 minutes for exit enclosures",
                    "Threshold": "Maximum 0.5 inches height"
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
            "FireRating": "hours"
        }
        
        self.current_file = None
        self.extracted_data = {}
        self.user_data = {}  # Store uploaded JSON data separately
        
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
    
    def search(self, query: str) -> List[Dict]:
        """Search through both IFC schema and uploaded data based on natural language query."""
        try:
            results = []
            
            # Clean and process query
            query = query.lower()
            try:
                tokens = word_tokenize(query)
                stop_words = set(stopwords.words('english'))
                tokens = [w for w in tokens if w not in stop_words]
            except LookupError:
                tokens = query.split()
                stop_words = {'a', 'an', 'the', 'in', 'on', 'at', 'for', 'to', 'of', 'with', 'by'}
                tokens = [w for w in tokens if w not in stop_words]
            
            # Extract key terms
            component_terms = sum([[k.lower(), k[3:].lower()] for k in self.ifc_schema.keys()], [])
            property_terms = list(set(sum([schema["properties"] for schema in self.ifc_schema.values()], [])))
            property_terms = [p.lower() for p in property_terms]
            
            # Search in IFC schema
            for component_type, schema in self.ifc_schema.items():
                component_name = component_type[3:].lower()  # Remove 'Ifc' prefix
                if any(term in component_name for term in tokens):
                    result = {
                        "type": component_type,
                        "name": f"Standard {component_name}",
                        "properties": {},
                        "requirements": schema.get("requirements", {}),
                        "source": "Building Code"
                    }
                    
                    # Add relevant properties based on query
                    for prop in schema["properties"]:
                        if prop.lower() in query or "dimension" in query:
                            result["properties"][prop] = f"See requirements: {schema['requirements'].get(prop, 'No specific requirement')}"
                    
                    results.append(result)
            
            # Search in uploaded JSON data
            if self.user_data:
                for key, value in self.user_data.items():
                    if isinstance(value, dict) and any(term in key.lower() for term in tokens):
                        result = {
                            "type": "UserComponent",
                            "name": key,
                            "properties": value,
                            "source": "Uploaded Data"
                        }
                        results.append(result)
            
            return results
        except Exception as e:
            st.error(f"Error in search: {str(e)}")
            return []
    
    def get_component_template(self, component_type: str) -> Dict:
        """Get template information for a specific component type."""
        try:
            if component_type in self.ifc_schema:
                return {
                    "type": component_type,
                    "required_properties": self.ifc_schema[component_type]["properties"],
                    "required_quantities": self.ifc_schema[component_type]["quantities"],
                    "relationships": self.ifc_schema[component_type]["relationships"],
                    "units": {prop: self.property_units.get(prop, "undefined") 
                            for prop in self.ifc_schema[component_type]["properties"]}
                }
            return {}
        except Exception as e:
            st.error(f"Error getting component template: {str(e)}")
            return {}

def main():
    st.set_page_config(page_title="IFC Code Analyzer", page_icon="🏗️", layout="wide")
    
    st.title("IFC Code Analyzer 🏗️")
    
    # Initialize session state
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = IFCAnalyzer()
    
    # Sidebar
    st.sidebar.header("Settings")
    
    # Location selector
    location = st.sidebar.selectbox(
        "Select Location",
        options=list(st.session_state.analyzer.locations.keys()),
        index=list(st.session_state.analyzer.locations.keys()).index(st.session_state.analyzer.current_location)
    )
    
    # Update location if changed
    if location != st.session_state.analyzer.current_location:
        if st.session_state.analyzer.set_location(location):
            st.sidebar.success(f"Location updated to {location}")
            
    # Display current building code information
    location_info = st.session_state.analyzer.get_location_info()
    st.sidebar.markdown("---")
    st.sidebar.subheader("Building Code Information")
    st.sidebar.write(f"**Version:** {location_info['code_version']}")
    st.sidebar.write(f"**Jurisdiction:** {location_info['jurisdiction']}")
    st.sidebar.write(f"**Units:** {location_info['units'].title()}")
    
    st.sidebar.markdown("---")
    st.sidebar.header("Upload Files")
    
    # File upload section
    uploaded_file = st.sidebar.file_uploader(
        "Upload JSON file with additional specifications",
        type=["json"],
        help="Upload a JSON file containing additional building component data"
    )
    
    if uploaded_file is not None:
        file_type = uploaded_file.name.split(".")[-1].lower()
        with st.spinner('Processing file...'):
            file_contents = uploaded_file.read()
            if st.session_state.analyzer.load_file(file_contents, file_type):
                st.sidebar.success("File loaded successfully!")
            else:
                st.sidebar.error("Failed to process file")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Search Building Components")
        search_query = st.text_input(
            "Enter your search query",
            placeholder="e.g., show me standpipe dimensions, wall requirements, door specifications"
        )
        
        if st.button("Search", type="primary"):
            if search_query:
                with st.spinner('Searching...'):
                    results = st.session_state.analyzer.search(search_query)
                    if results:
                        st.write(f"Found {len(results)} matching components:")
                        
                        # Group results by source
                        code_results = [r for r in results if r['source'] == 'Building Code']
                        user_results = [r for r in results if r['source'] == 'Uploaded Data']
                        
                        # Display building code requirements
                        if code_results:
                            st.subheader("Building Code Requirements")
                            for result in code_results:
                                with st.expander(f"{result['name']} Requirements"):
                                    # Display requirements
                                    if result.get('requirements'):
                                        st.write("**Code Requirements:**")
                                        for req_name, req_value in result['requirements'].items():
                                            st.write(f"- **{req_name}:** {req_value}")
                                    
                                    # Display properties if any
                                    if result.get('properties'):
                                        st.write("\n**Properties:**")
                                        props_df = pd.DataFrame(
                                            [(k, v) for k, v in result['properties'].items()],
                                            columns=["Property", "Requirement"]
                                        )
                                        st.table(props_df)
                        
                        # Display user-uploaded data
                        if user_results:
                            st.subheader("Additional Specifications (from uploaded data)")
                            for result in user_results:
                                with st.expander(f"{result['name']} Specifications"):
                                    if isinstance(result['properties'], dict):
                                        props_df = pd.DataFrame(
                                            [(k, v) for k, v in result['properties'].items()],
                                            columns=["Property", "Value"]
                                        )
                                        st.table(props_df)
                    else:
                        st.warning("No matching components found.")
            else:
                st.warning("Please enter a search query")
    
    with col2:
        st.subheader("Available Components")
        st.write("The following components can be searched:")
        
        for component_type in st.session_state.analyzer.ifc_schema.keys():
            component_name = component_type[3:]  # Remove 'Ifc' prefix
            with st.expander(component_name):
                schema = st.session_state.analyzer.ifc_schema[component_type]
                
                st.write("**Properties:**")
                st.write(", ".join(schema['properties']))
                
                if schema.get('requirements'):
                    st.write("\n**Requirements:**")
                    for req_name, req_value in schema['requirements'].items():
                        st.write(f"- **{req_name}:** {req_value}")

if __name__ == "__main__":
    main() 
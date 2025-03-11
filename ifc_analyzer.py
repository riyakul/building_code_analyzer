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

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class IFCAnalyzer:
    def __init__(self):
        self.ifc_schema = {
            "IfcWall": {
                "attributes": ["Name", "Description", "ObjectType"],
                "properties": ["Height", "Width", "Length", "Material"],
                "quantities": ["GrossFootprintArea", "NetVolume", "GrossVolume"],
                "relationships": ["ContainedInStructure", "HasOpenings"]
            },
            "IfcBeam": {
                "attributes": ["Name", "Description", "ObjectType"],
                "properties": ["Span", "Depth", "Width", "Material", "LoadBearing"],
                "quantities": ["Length", "CrossSectionArea", "NetWeight"],
                "relationships": ["ContainedInStructure"]
            },
            "IfcColumn": {
                "attributes": ["Name", "Description", "ObjectType"],
                "properties": ["Height", "Width", "Depth", "Material", "LoadBearing"],
                "quantities": ["Length", "CrossSectionArea", "NetWeight"],
                "relationships": ["ContainedInStructure"]
            },
            "IfcSlab": {
                "attributes": ["Name", "Description", "ObjectType"],
                "properties": ["Thickness", "Material", "LoadBearing", "FireRating"],
                "quantities": ["GrossArea", "NetArea", "GrossVolume"],
                "relationships": ["ContainedInStructure", "HasOpenings"]
            }
        }
        
        self.property_units = {
            "Height": "mm",
            "Width": "mm",
            "Length": "mm",
            "Depth": "mm",
            "Thickness": "mm",
            "Area": "m²",
            "Volume": "m³",
            "Weight": "kg",
            "LoadBearing": "boolean",
            "FireRating": "hours"
        }
        
        self.current_file = None
        self.extracted_data = {}
        
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
            self.extracted_data = self.current_file
            return len(self.extracted_data) > 0
        except Exception as e:
            st.error(f"Error processing JSON file: {str(e)}")
            return False
    
    def search(self, query: str) -> List[Dict]:
        """Search through extracted data based on natural language query."""
        try:
            results = []
            if not query or not self.extracted_data:
                return results
            
            # Clean and process query
            query = query.lower()
            tokens = word_tokenize(query)
            stop_words = set(stopwords.words('english'))
            tokens = [w for w in tokens if w not in stop_words]
            
            # Extract key terms
            component_terms = ["wall", "beam", "column", "slab", "foundation"]
            property_terms = ["height", "width", "length", "depth", "thickness", "material"]
            quantity_terms = ["area", "volume", "weight"]
            
            # Identify search focus
            search_components = [term for term in tokens if term in component_terms]
            search_properties = [term for term in tokens if term in property_terms]
            search_quantities = [term for term in tokens if term in quantity_terms]
            
            # Search through extracted data
            for entity_type, entities in self.extracted_data.items():
                if not search_components or any(comp in entity_type.lower() for comp in search_components):
                    for entity in entities:
                        should_include = True
                        
                        # Check properties
                        if search_properties:
                            has_property = False
                            for prop in search_properties:
                                if any(prop in key.lower() for key in entity["Properties"].keys()):
                                    has_property = True
                                    break
                            should_include = should_include and has_property
                        
                        # Check quantities
                        if search_quantities:
                            has_quantity = False
                            for qty in search_quantities:
                                if any(qty in key.lower() for key in entity["Quantities"].keys()):
                                    has_quantity = True
                                    break
                            should_include = should_include and has_quantity
                        
                        if should_include:
                            result = {
                                "type": entity_type,
                                "id": entity.get("GlobalId", "Unknown"),
                                "name": entity.get("Name", "Unnamed"),
                                "properties": entity["Properties"],
                                "quantities": entity["Quantities"],
                                "relationships": entity["Relationships"]
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
    
    # File upload section
    st.sidebar.header("Upload Files")
    uploaded_file = st.sidebar.file_uploader(
        "Upload IFC or JSON file",
        type=["ifc", "json"],
        help="Upload an IFC file or JSON file containing building component data"
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
        st.subheader("Search Components")
        search_query = st.text_input(
            "Enter your search query",
            placeholder="e.g., show me walls with height greater than 3m"
        )
        
        if st.button("Search", type="primary"):
            if search_query:
                with st.spinner('Searching...'):
                    results = st.session_state.analyzer.search(search_query)
                    if results:
                        st.write(f"Found {len(results)} matching components:")
                        for result in results:
                            with st.expander(f"{result['type']}: {result['name']}"):
                                # Properties
                                if result['properties']:
                                    st.write("**Properties:**")
                                    props_df = pd.DataFrame(
                                        [(k, v, st.session_state.analyzer.property_units.get(k, "-")) 
                                         for k, v in result['properties'].items()],
                                        columns=["Property", "Value", "Unit"]
                                    )
                                    st.table(props_df)
                                
                                # Quantities
                                if result['quantities']:
                                    st.write("**Quantities:**")
                                    qty_df = pd.DataFrame(
                                        [(k, v, st.session_state.analyzer.property_units.get(k, "-")) 
                                         for k, v in result['quantities'].items()],
                                        columns=["Quantity", "Value", "Unit"]
                                    )
                                    st.table(qty_df)
                                
                                # Relationships
                                if result['relationships']:
                                    st.write("**Relationships:**")
                                    for rel in result['relationships']:
                                        st.write(f"- {rel['type']}: {rel['related_object']} ({rel['related_name']})")
                    else:
                        st.warning("No matching components found.")
            else:
                st.warning("Please enter a search query")
    
    with col2:
        st.subheader("Component Templates")
        component_type = st.selectbox(
            "Select component type",
            options=list(st.session_state.analyzer.ifc_schema.keys())
        )
        
        if component_type:
            template = st.session_state.analyzer.get_component_template(component_type)
            if template:
                st.write("**Required Properties:**")
                props_df = pd.DataFrame(
                    [(prop, template['units'][prop]) for prop in template['required_properties']],
                    columns=["Property", "Unit"]
                )
                st.table(props_df)
                
                st.write("**Required Quantities:**")
                st.write(", ".join(template['required_quantities']))
                
                st.write("**Possible Relationships:**")
                st.write(", ".join(template['relationships']))

if __name__ == "__main__":
    main() 
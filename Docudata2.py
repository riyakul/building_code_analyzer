import streamlit as st
import json
import re
from typing import Dict, List, Optional
import pandas as pd
import csv
import io

class BuildingCodeAnalyzer:
    def __init__(self):
        self.components = {}
        self.quantities = {}
        self.guidelines = {}
        self.current_file = None

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
                if isinstance(d, dict):
                    for k, v in d.items():
                        key = f"{parent}.{k}" if parent else k
                        self.components[key] = {
                            "name": k,
                            "type": self.detect_component_type(k)
                        }
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
                        recurse(v, key)
                elif isinstance(d, list):
                    for i, item in enumerate(d):
                        recurse(item, f"{parent}[{i}]")

            recurse(data)
            return True
        except Exception as e:
            st.error(f"Error processing data: {e}")
            return False

    def detect_component_type(self, key: str) -> str:
        """Determine the type of a component based on its key."""
        key_lower = key.lower()
        if any(x in key_lower for x in ["wall", "beam", "column", "foundation"]):
            return "Structural"
        if any(x in key_lower for x in ["electrical", "plumbing", "hvac"]):
            return "Utilities"
        return "General"

    def search(self, term: str) -> List[Dict]:
        """Search for components matching the given term."""
        if not self.components:
            st.warning("No data loaded. Please upload a file first.")
            return []

        results = []
        term_parts = term.lower().split('.')
        
        for comp_key, comp_data in self.components.items():
            comp_key_lower = comp_key.lower()
            should_include = False
            
            # Check various matching conditions
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
                    "type": self.detect_component_type(comp_key)
                }
                
                if comp_key in self.quantities:
                    q = self.quantities[comp_key]
                    result["quantity"] = {
                        "value": q["value"],
                        "unit": q["unit"]
                    }
                
                if comp_key in self.guidelines:
                    result["guidelines"] = self.guidelines[comp_key]["description"]
                
                    # Extract numerical specifications from guidelines
                    numerical_specs = re.findall(
                        r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|in|%|degrees?|MPa|PSI|kN|kPa|m²|m³|ft²|ft³)", 
                        str(self.guidelines[comp_key])
                    )
                    if numerical_specs:
                        result["specifications"] = [
                            {"value": float(value), "unit": unit}
                            for value, unit in numerical_specs
                        ]
                
                results.append(result)
        
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
    """Display search results in Streamlit."""
    if not results:
        st.warning("No results found.")
        return

    st.write(f"Found {len(results)} results:")
    
    # Add export options
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Export results:")
    with col2:
        export_format = st.selectbox("Format", ["CSV", "JSON"], key="export_format")
        
        if st.button("Export", key="export_button"):
            export_data = export_results(results, export_format)
            if export_data:
                content, mime_type = export_data
                filename = f"building_codes_results.{export_format.lower()}"
                st.download_button(
                    label="Download",
                    data=content,
                    file_name=filename,
                    mime=mime_type
                )
    
    for result in results:
        with st.expander(f"{result['component']} ({result['type']})"):
            if "quantity" in result:
                st.metric(
                    "Quantity",
                    f"{result['quantity']['value']} {result['quantity']['unit']}"
                )
            
            if "guidelines" in result:
                st.write("**Guidelines:**")
                st.write(result["guidelines"])
            
            if "specifications" in result:
                st.write("**Specifications:**")
                specs_df = pd.DataFrame(result["specifications"])
                st.dataframe(specs_df, hide_index=True)

def main():
    st.set_page_config(
        page_title="Building Code Analyzer",
        page_icon="🏗️",
        layout="wide"
    )

    st.title("Building Code Analyzer 🏗️")

    # Initialize session state
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = BuildingCodeAnalyzer()

    # Sidebar
    with st.sidebar:
        st.header("Statistics")
        st.metric("Components", len(st.session_state.analyzer.components))
        st.metric("Guidelines", len(st.session_state.analyzer.guidelines))
        st.metric("Quantities", len(st.session_state.analyzer.quantities))

        st.markdown("---")
        st.header("Upload Data")
        uploaded_file = st.file_uploader("Choose a JSON file", type="json")
        
        if uploaded_file:
            file_contents = uploaded_file.read().decode("utf-8")
            if st.session_state.analyzer.load_file(file_contents):
                st.success("File loaded successfully!")
                st.rerun()

    # Main content
    if len(st.session_state.analyzer.components) > 0:
        # Search interface
        st.subheader("Search Components")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            search_term = st.text_input(
                "Enter search term",
                placeholder="e.g., foundation.material",
                help="You can use dot notation for nested components"
            )
        
        with col2:
            search_button = st.button("Search", type="primary", use_container_width=True)
        
        if search_button and search_term:
            results = st.session_state.analyzer.search(search_term)
            display_results(results)
            
        # Component type filter
        st.subheader("Filter by Type")
        component_types = ["All"] + list(set(comp["type"] for comp in st.session_state.analyzer.components.values()))
        selected_type = st.selectbox("Select component type", component_types)
        
        if selected_type != "All":
            filtered_components = {
                k: v for k, v in st.session_state.analyzer.components.items()
                if v["type"] == selected_type
            }
            
            if filtered_components:
                st.write(f"Found {len(filtered_components)} {selected_type} components:")
                for key, comp in filtered_components.items():
                    with st.expander(key):
                        st.write(f"**Type:** {comp['type']}")
                        if key in st.session_state.analyzer.quantities:
                            q = st.session_state.analyzer.quantities[key]
                            st.metric("Quantity", f"{q['value']} {q['unit']}")
                        if key in st.session_state.analyzer.guidelines:
                            st.write("**Guidelines:**")
                            st.write(st.session_state.analyzer.guidelines[key]["description"])
            else:
                st.warning(f"No components found of type: {selected_type}")
    else:
        st.info("👈 Please upload a JSON file to get started!")

if __name__ == "__main__":
    main() 
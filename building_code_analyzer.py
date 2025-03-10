import streamlit as st
import json
import re
from typing import Dict, List, Optional
import pandas as pd
import csv
import io
import time

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

    def search(self, term: str) -> List[Dict]:
        """Search for components with quantitative data or placement information."""
        if not self.components:
            st.warning("No data loaded. Please upload a file first.")
            return []

        results = []
        term_parts = term.lower().split('.')
        
        # Location/placement related keywords
        placement_keywords = [
            "location", "placement", "position", "installed", "mounted", "located",
            "between", "above", "below", "near", "adjacent", "inside", "outside",
            "spacing", "distance", "interval", "centers", "layout"
        ]
        
        for comp_key, comp_data in self.components.items():
            comp_key_lower = comp_key.lower()
            should_include = False
            data_type = set()  # Track what kind of data this component has
            
            # Check if component has any quantitative data
            has_quantities = comp_key in self.quantities
            if has_quantities:
                data_type.add("quantitative")
            
            # Check for numerical specifications and placement info in guidelines
            has_numerical_specs = False
            has_placement_info = False
            numerical_specs = []
            placement_info = None
            
            if comp_key in self.guidelines:
                guideline_text = str(self.guidelines[comp_key]["description"]).lower()
                
                # Extract numerical specifications
                numerical_specs = re.findall(
                    r"(\d+(?:\.\d+)?)\s*(mm|cm|m|ft|in|%|degrees?|MPa|PSI|kN|kPa|m²|m³|ft²|ft³|kW|A)", 
                    str(self.guidelines[comp_key]["description"])
                )
                has_numerical_specs = len(numerical_specs) > 0
                if has_numerical_specs:
                    data_type.add("quantitative")
                
                # Check for placement information
                if any(keyword in guideline_text for keyword in placement_keywords):
                    has_placement_info = True
                    placement_info = self.guidelines[comp_key]["description"]
                    data_type.add("placement")
            
            # Determine if component should be included
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
                    "data_types": list(data_type)
                }
                
                # Include quantity data if available
                if has_quantities:
                    q = self.quantities[comp_key]
                    result["quantity"] = {
                        "value": q["value"],
                        "unit": q["unit"]
                    }
                
                # Include numerical specifications from guidelines
                if has_numerical_specs:
                    result["specifications"] = [
                        {"value": float(value), "unit": unit, "description": self.guidelines[comp_key]["description"]}
                        for value, unit in numerical_specs
                    ]
                
                # Include placement information if available
                if has_placement_info:
                    result["placement"] = placement_info
                
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
    """Display search results with both quantitative and placement data."""
    if not results:
        st.warning("No matching components found.")
        return

    st.write(f"Found {len(results)} components:")
    
    # Organize results by data type
    quantitative_results = []
    placement_results = []
    
    for result in results:
        # Handle quantitative data
        if "quantitative" in result["data_types"]:
            component_data = {
                "Component": result["component"],
                "Type": result["type"]
            }
            
            if "quantity" in result:
                quantitative_results.append({
                    **component_data,
                    "Value": result["quantity"]["value"],
                    "Unit": result["quantity"]["unit"],
                    "Description": "Direct measurement"
                })
            
            if "specifications" in result:
                for spec in result["specifications"]:
                    quantitative_results.append({
                        **component_data,
                        "Value": spec["value"],
                        "Unit": spec["unit"],
                        "Description": spec["description"]
                    })
        
        # Handle placement data
        if "placement" in result["data_types"]:
            placement_results.append({
                "Component": result["component"],
                "Type": result["type"],
                "Placement Guidelines": result["placement"]
            })
    
    # Display quantitative data
    if quantitative_results:
        st.subheader("Quantitative Specifications")
        df_quant = pd.DataFrame(quantitative_results)
        st.dataframe(df_quant, hide_index=True)
    
    # Display placement data
    if placement_results:
        st.subheader("Placement Guidelines")
        df_place = pd.DataFrame(placement_results)
        st.dataframe(df_place, hide_index=True)
    
    # Add export options
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.write("Export data:")
    with col2:
        export_format = st.selectbox("Format", ["CSV", "JSON"], key="export_format")
    with col3:
        if st.button("Export", key="export_button"):
            export_data = {
                "quantitative_data": quantitative_results if quantitative_results else [],
                "placement_data": placement_results if placement_results else []
            }
            
            if export_format == "CSV":
                # Create a combined CSV with sections
                output = io.StringIO()
                writer = csv.writer(output)
                
                if quantitative_results:
                    writer.writerow(["QUANTITATIVE SPECIFICATIONS"])
                    writer.writerow(df_quant.columns.tolist())
                    writer.writerows(df_quant.values.tolist())
                    writer.writerow([])  # Empty row as separator
                
                if placement_results:
                    writer.writerow(["PLACEMENT GUIDELINES"])
                    writer.writerow(df_place.columns.tolist())
                    writer.writerows(df_place.values.tolist())
                
                st.download_button(
                    label="Download CSV",
                    data=output.getvalue(),
                    file_name="building_codes_analysis.csv",
                    mime="text/csv"
                )
            else:
                st.download_button(
                    label="Download JSON",
                    data=json.dumps(export_data, indent=2),
                    file_name="building_codes_analysis.json",
                    mime="application/json"
                )
    
    # Show detailed view
    st.subheader("Detailed View")
    for result in results:
        with st.expander(f"{result['component']} ({result['type']})"):
            # Show data types
            st.write("**Data Types:**", ", ".join(result["data_types"]))
            
            # Display quantities
            if "quantity" in result:
                st.metric(
                    "Quantity",
                    f"{result['quantity']['value']} {result['quantity']['unit']}"
                )
            
            # Display specifications in a table
            if "specifications" in result:
                st.write("**Numerical Specifications:**")
                specs_df = pd.DataFrame(result["specifications"])
                st.dataframe(specs_df[["value", "unit", "description"]], hide_index=True)
            
            # Display placement information
            if "placement" in result:
                st.write("**Placement Guidelines:**")
                st.info(result["placement"])

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

        # Sidebar
        with st.sidebar:
            st.header("Statistics")
            try:
                st.metric("Components", len(st.session_state.analyzer.components))
                st.metric("Guidelines", len(st.session_state.analyzer.guidelines))
                st.metric("Quantities", len(st.session_state.analyzer.quantities))
            except Exception as e:
                st.error("Error displaying statistics")
                st.session_state.analyzer = BuildingCodeAnalyzer()  # Reset analyzer

            st.markdown("---")
            st.header("Upload Data")
            uploaded_file = st.file_uploader("Choose a JSON file", type="json", key="json_uploader")
            
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
                    st.session_state.analyzer = BuildingCodeAnalyzer()  # Reset analyzer

        # Main content
        if len(st.session_state.analyzer.components) > 0:
            try:
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
                    st.session_state.search_results = results
                    display_results(results)
                
                # Component type filter
                st.subheader("Filter by Type")
                try:
                    # Get unique component types safely
                    component_types = {"General", "Structural", "Utilities"}  # Default types
                    for comp in st.session_state.analyzer.components.values():
                        if isinstance(comp, dict) and "type" in comp:
                            component_types.add(comp["type"])
                    
                    filter_options = ["All"] + sorted(list(component_types))
                    selected_type = st.selectbox("Select component type", filter_options)
                    
                    if selected_type != "All":
                        filtered_components = {
                            k: v for k, v in st.session_state.analyzer.components.items()
                            if isinstance(v, dict) and "type" in v and v["type"] == selected_type
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
                except Exception as e:
                    st.error("Error in component filtering")
                    st.info("Please try searching for components instead.")
            except Exception as e:
                st.error("Error in main content")
                st.info("Please try refreshing the page")
        else:
            st.info("👈 Please upload a JSON file to get started!")
    except Exception as e:
        st.error("Application error occurred. Please refresh the page.")
        st.session_state.clear()  # Clear session state on critical error

if __name__ == "__main__":
    main() 
import streamlit as st
import json
import re
from collections import defaultdict

def extract_measurements(text):
    """Extract measurements with their units."""
    pattern = r'(\d+(?:\.\d+)?)\s*(mm|m|cm|inches|ft|MPa|dB|hours?|Pa|L/s/m²)'
    return re.findall(pattern, text)

def extract_component_data(data, query_terms):
    """Extract relevant component data based on query terms."""
    results = defaultdict(list)
    
    def process_item(item, path=""):
        if isinstance(item, dict):
            # Check if this is a component with a name
            if "name" in item:
                # Score this component's relevance to the query
                score = sum(term.lower() in str(item).lower() for term in query_terms)
                if score > 0:
                    component_type = path.split('.')[-1] if path else "component"
                    results[component_type].append({
                        "name": item.get("name", ""),
                        "measurements": {
                            k: v for k, v in item.items() 
                            if isinstance(v, (int, float)) or 
                               any(unit in str(v).lower() for unit in ["mm", "m", "cm", "mpa", "db", "hour", "pa"])
                        },
                        "specifications": item.get("specifications", {}),
                        "other_details": {
                            k: v for k, v in item.items() 
                            if k not in ["name", "specifications"] and not isinstance(v, (int, float))
                        }
                    })
            # Recursively process nested dictionaries
            for key, value in item.items():
                new_path = f"{path}.{key}" if path else key
                process_item(value, new_path)
        elif isinstance(item, list):
            # Process each item in the list
            for i, value in enumerate(item):
                process_item(value, path)

    process_item(data)
    return results

st.title("Building Component Analyzer")

st.write("""
Upload your building components JSON file to analyze specifications, measurements, and other details.
Search for specific components or attributes using natural language queries.
""")

# Sidebar upload area
st.sidebar.header("Upload Building Data")
uploaded_file = st.sidebar.file_uploader("Choose a JSON file with building components", type=["json"])

if uploaded_file is not None:
    try:
        # Load JSON data
        data = json.load(uploaded_file)
        st.success("Building data successfully loaded!")
        
        # Search section
        st.subheader("Natural Language Query")
        query = st.text_input("Enter your search (e.g., 'walls with fire rating', 'concrete thickness', 'window height'):")
        
        if query:
            # Process query into terms
            query_terms = query.lower().split()
            
            # Extract relevant components and their data
            results = extract_component_data(data, query_terms)
            
            if results:
                st.write(f"Found matching components:")
                
                # Display results by component type
                for component_type, components in results.items():
                    with st.expander(f"{component_type.title()} ({len(components)} found)"):
                        for component in components:
                            # Component name as subheader
                            st.markdown(f"**{component['name']}**")
                            
                            # Display measurements in columns
                            if component['measurements']:
                                st.markdown("*Measurements and Values:*")
                                cols = st.columns(len(component['measurements']))
                                for col, (key, value) in zip(cols, component['measurements'].items()):
                                    col.metric(
                                        key.replace('_', ' ').title(),
                                        f"{value}" if isinstance(value, str) else f"{value:,}"
                                    )
                            
                            # Display specifications
                            if component['specifications']:
                                st.markdown("*Specifications:*")
                                st.json(component['specifications'])
                            
                            # Display other relevant details
                            if component['other_details']:
                                st.markdown("*Other Details:*")
                                st.json(component['other_details'])
                            
                            st.markdown("---")
            else:
                st.warning("No matching components found.")
                st.info("Try different search terms or check the available fields in the sidebar.")
        
        # Display available fields and search tips in sidebar
        st.sidebar.subheader("Search Guide")
        st.sidebar.markdown("""
        **Try searching for:**
        - Component types (walls, windows, doors)
        - Materials (concrete, steel, glass)
        - Measurements (height, width, thickness)
        - Specifications (fire rating, thermal, soundproofing)
        """)
        
        # Display sample queries
        st.sidebar.subheader("Sample Queries")
        st.sidebar.markdown("""
        - "external walls"
        - "fire rated components"
        - "window dimensions"
        - "concrete specifications"
        """)
    
    except Exception as e:
        st.error(f"Error processing building data: {e}")
else:
    st.info("Please upload a JSON file with building component data to begin analysis.")

import streamlit as st
import pandas as pd
import json
import os
from typing import Dict, List, Any
import spacy
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import re

class BuildingAnalyzer:
    def __init__(self):
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
            nltk.data.find('averaged_perceptron_tagger')
            nltk.data.find('wordnet')
        except LookupError:
            nltk.download('punkt')
            nltk.download('stopwords')
            nltk.download('averaged_perceptron_tagger')
            nltk.download('wordnet')
        
        # Load spaCy model
        try:
            self.nlp = spacy.load('en_core_web_sm')
        except:
            os.system('python -m spacy download en_core_web_sm')
            self.nlp = spacy.load('en_core_web_sm')
        
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))
        
        # Add domain-specific terms to NLP
        self.component_terms = {
            "wall": ["wall", "partition", "barrier"],
            "door": ["door", "entrance", "exit", "doorway"],
            "window": ["window", "opening", "glazing"],
            "stair": ["stair", "stairway", "staircase", "steps"],
            "structural": ["load-bearing", "structural", "supporting"],
            "fire": ["fire-rated", "fire-resistant", "fireproof"],
            "dimension": ["width", "height", "thickness", "length", "depth"],
            "material": ["concrete", "steel", "wood", "glass", "metal"],
            "rating": ["rating", "grade", "class", "performance"],
            "compliance": ["compliant", "complies", "meets", "satisfies"]
        }
        
        # Initialize existing attributes
        self.building_codes = {
            "California": {
                "version": "2022 California Building Code",
                "jurisdiction": "California Building Standards Commission"
            },
            "New York": {
                "version": "2022 NYC Building Code",
                "jurisdiction": "NYC Department of Buildings"
            },
            "Texas": {
                "version": "2021 International Building Code with Texas Amendments",
                "jurisdiction": "Texas Department of Licensing and Regulation"
            }
        }
        
        # Standard component requirements
        self.component_requirements = {
            "walls": {
                "structural": {
                    "min_thickness": "8 inches for concrete, 6 inches for CMU",
                    "reinforcement": "As per structural calculations",
                    "fire_rating": "2-4 hours depending on occupancy",
                    "references": ["CBC Chapter 19", "ACI 318-19"]
                },
                "partition": {
                    "min_thickness": "4 inches",
                    "sound_rating": "STC 50 between units",
                    "fire_rating": "1-2 hours depending on location",
                    "references": ["CBC Section 708", "ASTM E90"]
                }
            },
            "doors": {
                "exterior": {
                    "min_width": "36 inches",
                    "min_height": "80 inches",
                    "fire_rating": "90 minutes for exits",
                    "references": ["CBC Section 1010"]
                },
                "interior": {
                    "min_width": "32 inches",
                    "min_height": "80 inches",
                    "accessibility": "ADA compliant hardware",
                    "references": ["CBC Chapter 11B"]
                }
            },
            "windows": {
                "egress": {
                    "min_width": "20 inches",
                    "min_height": "24 inches",
                    "min_area": "5.7 sq ft",
                    "max_sill_height": "44 inches",
                    "references": ["CBC Section 1030"]
                },
                "non_egress": {
                    "glazing": "Safety glazing required in hazardous locations",
                    "energy": "U-factor ≤ 0.30, SHGC ≤ 0.23",
                    "references": ["CBC Section 2406", "Energy Code"]
                }
            },
            "stairs": {
                "public": {
                    "min_width": "44 inches",
                    "riser_height": "4-7 inches",
                    "tread_depth": "11 inches minimum",
                    "headroom": "80 inches minimum",
                    "references": ["CBC Section 1011"]
                },
                "private": {
                    "min_width": "36 inches",
                    "riser_height": "4-7.75 inches",
                    "tread_depth": "10 inches minimum",
                    "references": ["CBC Section 1011.5"]
                }
            }
        }

    def analyze_file(self, file_data: Dict) -> Dict[str, Any]:
        """Analyze uploaded building data and return compliance results"""
        results = {
            "compliant": [],
            "non_compliant": [],
            "warnings": []
        }
        
        # Analyze each component in the file
        for component_type, items in file_data.items():
            if component_type in self.component_requirements:
                for item in items:
                    compliance = self.check_compliance(component_type, item)
                    results[compliance["status"]].append({
                        "component": component_type,
                        "id": item.get("id", "Unknown"),
                        "details": compliance["details"],
                        "recommendations": compliance["recommendations"]
                    })
        
        return results

    def check_compliance(self, component_type: str, item: Dict) -> Dict[str, Any]:
        """Check if a component meets requirements"""
        requirements = self.component_requirements.get(component_type, {})
        subtype = item.get("type", "standard")
        
        if subtype in requirements:
            result = {
                "status": "compliant",
                "details": [],
                "recommendations": []
            }
            
            for req_name, req_value in requirements[subtype].items():
                if req_name != "references":
                    item_value = item.get(req_name)
                    if item_value:
                        if not self.meets_requirement(req_name, item_value, req_value):
                            result["status"] = "non_compliant"
                            result["details"].append(f"{req_name}: Required {req_value}, Found {item_value}")
                            result["recommendations"].append(
                                f"Adjust {req_name} to meet {req_value} requirement per {requirements[subtype]['references'][0]}"
                            )
            
            return result
        
        return {
            "status": "warnings",
            "details": ["Unknown component subtype"],
            "recommendations": ["Verify component classification"]
        }

    def meets_requirement(self, req_name: str, value: Any, requirement: str) -> bool:
        """Check if a value meets a specific requirement"""
        # Convert string measurements to numbers for comparison
        if isinstance(value, (int, float)) and isinstance(requirement, str):
            if "inches" in requirement:
                req_value = float(requirement.split()[0])
                return value >= req_value
            elif "sq ft" in requirement:
                req_value = float(requirement.split()[0])
                return value >= req_value
        
        # Handle string requirements
        if isinstance(value, str) and isinstance(requirement, str):
            if "minimum" in requirement.lower():
                req_value = requirement.split()[0]
                return float(value) >= float(req_value)
            elif "maximum" in requirement.lower():
                req_value = requirement.split()[0]
                return float(value) <= float(req_value)
        
        # Default comparison
        return str(value) == str(requirement)

    def process_query(self, query: str, data: Dict) -> List[Dict]:
        """Process natural language query and return matching components"""
        # Process query with spaCy
        doc = self.nlp(query.lower())
        
        # Extract key information
        component_types = self._extract_component_types(doc)
        properties = self._extract_properties(doc)
        measurements = self._extract_measurements(doc)
        comparisons = self._extract_comparisons(doc)
        
        # Search through components
        results = []
        for component_type, components in data.items():
            if not component_types or any(ct in component_type.lower() for ct in component_types):
                for component in components:
                    score = self._calculate_match_score(component, properties, measurements, comparisons)
                    if score > 0:
                        results.append({
                            "component_type": component_type,
                            "component": component,
                            "score": score,
                            "matches": self._get_match_details(component, properties, measurements, comparisons)
                        })
        
        # Sort results by score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
    
    def _extract_component_types(self, doc) -> List[str]:
        """Extract component types from query"""
        component_types = []
        for token in doc:
            for component, variations in self.component_terms.items():
                if token.lemma_ in variations:
                    component_types.append(component)
        return list(set(component_types))
    
    def _extract_properties(self, doc) -> List[str]:
        """Extract property requirements from query"""
        properties = []
        for token in doc:
            if token.pos_ in ['ADJ', 'NOUN']:
                properties.append(token.lemma_)
        return properties
    
    def _extract_measurements(self, doc) -> List[Dict]:
        """Extract measurements and units from query"""
        measurements = []
        number = None
        for token in doc:
            if token.like_num:
                number = float(token.text)
            elif number and token.text in ['inches', 'inch', 'in', 'feet', 'ft', 'meters', 'm']:
                measurements.append({
                    'value': number,
                    'unit': token.text
                })
                number = None
        return measurements
    
    def _extract_comparisons(self, doc) -> List[Dict]:
        """Extract comparison operators from query"""
        comparisons = []
        comparison_terms = {
            'greater': '>', 'more': '>', 'larger': '>', 'higher': '>',
            'less': '<', 'smaller': '<', 'lower': '<',
            'equal': '=', 'exactly': '='
        }
        
        for token in doc:
            if token.lemma_ in comparison_terms:
                comparisons.append({
                    'operator': comparison_terms[token.lemma_],
                    'position': token.i
                })
        return comparisons
    
    def _calculate_match_score(self, component: Dict, properties: List[str], 
                             measurements: List[Dict], comparisons: List[Dict]) -> float:
        """Calculate how well a component matches the query criteria"""
        score = 0.0
        
        # Check properties
        for prop in properties:
            if any(prop in str(value).lower() for value in component.values()):
                score += 1.0
        
        # Check measurements
        for measurement in measurements:
            for key, value in component.items():
                if isinstance(value, (int, float)):
                    if self._compare_measurements(value, measurement):
                        score += 2.0
        
        return score
    
    def _compare_measurements(self, component_value: float, measurement: Dict) -> bool:
        """Compare component measurements with query measurements"""
        # Convert units if necessary
        converted_value = self._convert_units(measurement['value'], measurement['unit'])
        return abs(component_value - converted_value) < 0.1
    
    def _convert_units(self, value: float, unit: str) -> float:
        """Convert measurements to standard units"""
        conversions = {
            'inches': 1,
            'inch': 1,
            'in': 1,
            'feet': 12,
            'ft': 12,
            'meters': 39.37,
            'm': 39.37
        }
        return value * conversions.get(unit, 1)
    
    def _get_match_details(self, component: Dict, properties: List[str],
                          measurements: List[Dict], comparisons: List[Dict]) -> Dict:
        """Get detailed information about why a component matched"""
        details = {
            "matching_properties": [],
            "matching_measurements": [],
            "matching_comparisons": []
        }
        
        # Record matching properties
        for prop in properties:
            for key, value in component.items():
                if prop in str(value).lower():
                    details["matching_properties"].append({
                        "property": key,
                        "value": value,
                        "matched_term": prop
                    })
        
        # Record matching measurements
        for measurement in measurements:
            for key, value in component.items():
                if isinstance(value, (int, float)):
                    if self._compare_measurements(value, measurement):
                        details["matching_measurements"].append({
                            "property": key,
                            "component_value": value,
                            "query_value": measurement
                        })
        
        return details

def main():
    st.set_page_config(
        page_title="Building Code Analyzer",
        page_icon="🏗️",
        layout="wide"
    )
    
    st.title("Building Code Analyzer 🏗️")
    
    # Initialize analyzer
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = BuildingAnalyzer()
    if 'uploaded_data' not in st.session_state:
        st.session_state.uploaded_data = None
    
    # File upload section
    st.header("Upload Building Data")
    uploaded_file = st.file_uploader("Upload JSON file with building components", type=['json'])
    
    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            st.session_state.uploaded_data = data
            
            # Display raw data in expandable section
            with st.expander("View Raw JSON Data", expanded=False):
                st.json(data)
            
            # Natural Language Query Section
            st.header("Search Components")
            query = st.text_input(
                "Enter your query in natural language",
                placeholder="Example: Show me all doors wider than 36 inches"
            )
            
            if query:
                results = st.session_state.analyzer.process_query(query, data)
                
                if results:
                    st.subheader("Search Results")
                    for result in results:
                        with st.expander(
                            f"{result['component_type'].title()} - ID: {result['component'].get('id', 'N/A')} (Score: {result['score']:.2f})",
                            expanded=True
                        ):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown("#### Component Details")
                                details_df = pd.DataFrame([
                                    {"Property": k, "Value": v}
                                    for k, v in result['component'].items()
                                ])
                                st.table(details_df)
                            
                            with col2:
                                st.markdown("#### Match Details")
                                if result['matches']['matching_properties']:
                                    st.markdown("**Matching Properties:**")
                                    for match in result['matches']['matching_properties']:
                                        st.markdown(f"- {match['property']}: {match['value']}")
                                
                                if result['matches']['matching_measurements']:
                                    st.markdown("**Matching Measurements:**")
                                    for match in result['matches']['matching_measurements']:
                                        st.markdown(f"- {match['property']}: {match['component_value']}")
                else:
                    st.info("No components found matching your query.")
            
            # Example queries
            with st.expander("Example Queries"):
                st.markdown("""
                Try these example queries:
                - Show me all doors wider than 36 inches
                - Find windows with fire rating
                - Which walls are structural?
                - Show me stairs with riser height between 4 and 7 inches
                - Find all exterior components
                - Show components with specific fire ratings
                - Which elements are made of concrete?
                """)
            
            # Display results in tabs
            tabs = st.tabs(["Component Overview", "Compliance Summary", "Detailed Analysis", "Code References"])
            
            # Component Overview Tab
            with tabs[0]:
                st.header("Component Overview")
                
                for component_type, components in data.items():
                    st.subheader(f"{component_type.title()}")
                    
                    # Create a DataFrame for better visualization
                    if components:
                        df = pd.json_normalize(components)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info(f"No {component_type} found in the data")
            
            # Compliance Summary Tab
            with tabs[1]:
                st.header("Compliance Summary")
                
                # Display compliant items
                st.subheader("✅ Compliant Components")
                if results["compliant"]:
                    for item in results["compliant"]:
                        st.success(f"""
                        **{item['component'].title()} (ID: {item['id']})**
                        - All requirements met
                        """)
                else:
                    st.info("No fully compliant components found")
                
                # Display non-compliant items
                st.subheader("❌ Non-Compliant Components")
                if results["non_compliant"]:
                    for item in results["non_compliant"]:
                        st.error(f"""
                        **{item['component'].title()} (ID: {item['id']})**
                        Issues:
                        {"".join([f'- {detail}\\n' for detail in item['details']])}
                        
                        Recommendations:
                        {"".join([f'- {rec}\\n' for rec in item['recommendations']])}
                        """)
                else:
                    st.info("No non-compliant components found")
            
            # Detailed Analysis Tab
            with tabs[2]:
                st.header("Detailed Analysis")
                
                for component_type, components in data.items():
                    with st.expander(f"{component_type.title()} Details", expanded=True):
                        for component in components:
                            st.markdown(f"### {component_type.title()} ID: {component.get('id', 'N/A')}")
                            
                            # Create three columns for better organization
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown("#### Specifications")
                                specs_table = []
                                for key, value in component.items():
                                    if key != 'id' and not isinstance(value, dict):
                                        specs_table.append({"Property": key, "Value": value})
                                if specs_table:
                                    st.table(pd.DataFrame(specs_table))
                            
                            with col2:
                                st.markdown("#### Requirements")
                                if component_type in st.session_state.analyzer.component_requirements:
                                    component_subtype = component.get('type', 'standard')
                                    if component_subtype in st.session_state.analyzer.component_requirements[component_type]:
                                        reqs = st.session_state.analyzer.component_requirements[component_type][component_subtype]
                                        req_table = []
                                        for key, value in reqs.items():
                                            if key != 'references':
                                                req_table.append({"Requirement": key, "Value": value})
                                        if req_table:
                                            st.table(pd.DataFrame(req_table))
                            
                            # Display code references
                            if component_type in st.session_state.analyzer.component_requirements:
                                component_subtype = component.get('type', 'standard')
                                if component_subtype in st.session_state.analyzer.component_requirements[component_type]:
                                    refs = st.session_state.analyzer.component_requirements[component_type][component_subtype].get('references', [])
                                    if refs:
                                        st.markdown("#### Code References")
                                        for ref in refs:
                                            st.markdown(f"- {ref}")
            
            # Code References Tab
            with tabs[3]:
                st.header("Code References")
                
                # Location selection
                location = st.selectbox(
                    "Select Location",
                    options=list(st.session_state.analyzer.building_codes.keys())
                )
                
                if location:
                    code_info = st.session_state.analyzer.building_codes[location]
                    st.info(f"""
                    **Building Code: {code_info['version']}**
                    **Jurisdiction: {code_info['jurisdiction']}**
                    """)
                    
                    # Add relevant code sections
                    st.markdown("""
                    ### Key Code Sections
                    1. **Chapter 3: Occupancy Classification**
                    2. **Chapter 5: General Building Heights and Areas**
                    3. **Chapter 6: Types of Construction**
                    4. **Chapter 7: Fire and Smoke Protection Features**
                    5. **Chapter 10: Means of Egress**
                    6. **Chapter 11: Accessibility**
                    """)
        
        except Exception as e:
            st.error(f"Error analyzing file: {str(e)}")
            st.info("Please ensure your JSON file follows the required format")
            
            # Show example format
            st.markdown("""
            ### Expected JSON Format:
            ```json
            {
                "walls": [
                    {
                        "id": "W1",
                        "type": "structural",
                        "thickness": 8,
                        "fire_rating": "2 hours"
                    }
                ],
                "doors": [
                    {
                        "id": "D1",
                        "type": "exterior",
                        "width": 36,
                        "height": 80
                    }
                ]
            }
            ```
            """)

if __name__ == "__main__":
    main() 
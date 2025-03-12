import streamlit as st
import json

st.title("JSON-Based Search Website")

st.write("""
This app lets you upload a JSON file and then query it using natural language.
Later, you can replace the upload functionality with built-in JSON files.
""")

# Sidebar upload area
st.sidebar.header("Upload Your JSON File")
uploaded_file = st.sidebar.file_uploader("Choose a JSON file", type=["json"])

if uploaded_file is not None:
    try:
        # Load JSON data
        data = json.load(uploaded_file)
        st.success("JSON file successfully loaded!")
        
        # Natural language query section
        st.subheader("Natural Language Query")
        query = st.text_input("Enter your query in natural language:")
        
        if query:
            # For demonstration, we simply search the JSON string for the query substring.
            # More advanced natural language processing can be added here.
            json_str = json.dumps(data, indent=2)
            if query.lower() in json_str.lower():
                st.write("The query was found in the JSON data.")
                # Optionally, you could extract and display a snippet of matching content.
            else:
                st.write("No match found for your query.")
        
        # Display a sidebar for searching by available keys
        st.sidebar.subheader("Search by Key")
        if isinstance(data, dict):
            keys = list(data.keys())
            selected_key = st.sidebar.selectbox("Select a key", keys)
            st.write(f"Data for key '{selected_key}':")
            st.json(data[selected_key])
        elif isinstance(data, list):
            # If the JSON is a list of dictionaries, get keys from the first item.
            if data and isinstance(data[0], dict):
                keys = list(data[0].keys())
                selected_key = st.sidebar.selectbox("Select a key", keys)
                st.write(f"Values for key '{selected_key}':")
                values = [item.get(selected_key, None) for item in data]
                st.write(values)
            else:
                st.write("The uploaded JSON list does not contain dictionaries.")
        else:
            st.write("Uploaded JSON structure not recognized for key search.")
    
    except Exception as e:
        st.error(f"Error loading JSON file: {e}")
else:
    st.info("Please upload a JSON file to get started.")    

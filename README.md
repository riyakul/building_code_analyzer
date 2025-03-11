# Building Code Analyzer 🏗️

A Python-based tool for analyzing and searching building codes and component specifications.

## Features

- Upload and analyze JSON-formatted building component data
- Search through components by name, type, specifications, and requirements
- Extract and display structured information including:
  - 📏 Dimensions (height, width, depth)
  - ⚙️ Specifications (technical values)
  - 🔨 Materials
  - 📋 Requirements
  - 🔢 Quantities

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/building_code_analyzer.git
cd building_code_analyzer
```

2. Install required packages:
```bash
pip install streamlit pandas
```

## Usage

1. Run the Streamlit app:
```bash
streamlit run building_code_analyzer.py
```

2. Upload your JSON file containing building component data
3. Use the search interface to find components and their specifications

## JSON Data Format

Your JSON file should contain building component information in a structured format. Example:

```json
{
  "wall": {
    "type": "Structural",
    "height": "3000 mm",
    "materials": ["concrete", "steel reinforcement"],
    "requirements": "Must have minimum thickness of 200 mm"
  }
}
```

## Component Types

The analyzer automatically categorizes components into:
- Structural (walls, beams, foundations)
- Architectural (doors, windows, stairs)
- Utilities (electrical, plumbing, HVAC)
- Safety (fire protection, emergency exits)

## Search Examples

- "wall height requirements"
- "door dimensions"
- "concrete foundation"
- "minimum ceiling height"

## Contributing

Feel free to submit issues and enhancement requests! 
# IFC Code Analyzer

A Streamlit web application for analyzing IFC (Industry Foundation Classes) files and extracting building component information.

## Features

- Upload and analyze IFC files
- Upload and analyze JSON files with building component data
- Natural language search queries for components
- Extract quantitative information and specifications
- View component templates and requirements
- Display relationships between building elements

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ifc-code-analyzer.git
cd ifc-code-analyzer
```

2. Create a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Streamlit app:
```bash
streamlit run ifc_analyzer.py
```

2. Open your web browser and navigate to the URL shown in the terminal (usually http://localhost:8501)

3. Use the application:
   - Upload an IFC or JSON file using the sidebar
   - Enter natural language queries in the search box
   - View component templates and requirements
   - Explore extracted information in tables and expandable sections

## Query Examples

- "Show me all walls with height greater than 3m"
- "Find beams with specific material properties"
- "List columns with load-bearing capacity"
- "Display slab thickness requirements"

## Supported Components

- Walls (IfcWall)
- Beams (IfcBeam)
- Columns (IfcColumn)
- Slabs (IfcSlab)

Each component includes:
- Properties (dimensions, materials)
- Quantities (area, volume, weight)
- Relationships with other building elements

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
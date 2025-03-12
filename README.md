# IFC Code Analyzer 🏗️

A Streamlit web application for analyzing building components from IFC files and building codes. The application provides a comprehensive interface to search and view building code requirements, component specifications, and relationships based on IFC schema.

## Features

- **Component Search**: Natural language search for building components and their requirements
- **Building Code Integration**: Access building code requirements for various components
- **Multiple Locations**: Support for different jurisdictions (California, New York, Texas, International)
- **IFC Schema Support**: Comprehensive IFC schema implementation including:
  - Architectural Elements (Walls, Windows, Doors, etc.)
  - MEP Components (Pipes, Ducts, Light Fixtures, etc.)
  - Spatial Elements (Spaces, Zones)
  - Structural Elements (Beams, Columns, Slabs)
- **Code Requirement Display**: Detailed view of building code requirements with references
- **Unit Management**: Automatic unit conversion between metric and imperial systems
- **File Upload**: Support for IFC and JSON file uploads with custom specifications

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/building_code_analyzer.git
cd building_code_analyzer
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

1. Start the Streamlit application:
```bash
streamlit run ifc_analyzer.py
```

2. Open your web browser and navigate to the provided URL (typically http://localhost:8501)

3. Use the application:
   - Select your location from the sidebar
   - Enter search queries in the search box
   - Upload IFC or JSON files for custom specifications
   - View component requirements and specifications

## Search Examples

- "Show me wall requirements"
- "What are the door dimensions"
- "Show me fire rating requirements for columns"
- "What are the ventilation requirements for spaces"
- "Show me sprinkler spacing requirements"

## Component Types

The application supports various IFC components including:

### Architectural
- IfcWall
- IfcWindow
- IfcDoor
- IfcStair
- IfcRoof
- IfcSlab
- IfcRailing
- IfcCurtainWall

### MEP
- IfcPipe
- IfcDuctSegment
- IfcLightFixture
- IfcSanitaryTerminal
- IfcFireSuppressionTerminal
- IfcElectricDistributionBoard

### Spatial
- IfcSpace
- IfcZone

### Structural
- IfcBeam
- IfcColumn

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- buildingSMART for IFC specifications
- Various building code authorities for requirements and specifications 
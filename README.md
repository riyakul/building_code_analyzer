# Building Code Analyzer

A simple tool to analyze building components against code requirements and provide compliance reports.

## Features

1. **Component Analysis**
   - Walls (structural and partition)
   - Doors (exterior and interior)
   - Windows (egress and non-egress)
   - Stairs (public and private)

2. **Code Compliance**
   - Dimensional requirements
   - Material specifications
   - Fire ratings
   - Accessibility requirements

3. **Multiple Jurisdictions**
   - California Building Code
   - NYC Building Code
   - Texas Building Code (IBC with amendments)

## Usage

1. **Install Requirements**
   ```bash
   pip install streamlit pandas
   ```

2. **Run the Application**
   ```bash
   streamlit run building_analyzer.py
   ```

3. **Upload Building Data**
   - Prepare a JSON file with your building components
   - Use the example format shown in `example_building.json`
   - Upload through the web interface

4. **View Results**
   - Compliance Summary
   - Component Details
   - Code References

## JSON Format

Your building data should follow this structure:
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

## Requirements

- Python 3.7+
- Streamlit
- Pandas

## Example Files

1. `building_analyzer.py` - Main application
2. `example_building.json` - Example building data 
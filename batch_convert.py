#!/usr/bin/env python3
"""
Batch JSON to XOSC Converter
Converts all JSON scenario files in generated_scenarios to XOSC files in converted_scenarios
"""

import os
import sys
import json
import glob
import logging
from pathlib import Path

# Mock carla module to avoid import errors
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

# Now import the converter
from xosc_json import JsonToXoscConverter, ValidationError

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def find_json_files(input_dir: str) -> list:
    """Find all JSON files in the input directory"""
    json_files = []
    pattern = os.path.join(input_dir, "*.json")
    
    for file_path in glob.glob(pattern):
        # Skip backup files
        if file_path.endswith('.bak'):
            continue
        json_files.append(file_path)
    
    return sorted(json_files)

def convert_file(input_file: str, output_dir: str, converter: JsonToXoscConverter, logger) -> bool:
    """Convert a single JSON file to XOSC"""
    try:
        # Load JSON data
        with open(input_file, 'r') as f:
            json_data = json.load(f)
        
        # Create output filename
        input_name = os.path.basename(input_file)
        output_name = os.path.splitext(input_name)[0] + '.xosc'
        output_path = os.path.join(output_dir, output_name)
        
        logger.info(f"Converting {input_name} -> {output_name}")
        
        # Convert
        xosc_content = converter.convert(json_data)
        
        # Write output
        with open(output_path, 'w') as f:
            f.write(xosc_content)
        
        logger.info(f"Successfully converted {input_name}")
        return True
        
    except ValidationError as e:
        logger.error(f"Validation error in {input_file}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error converting {input_file}: {e}")
        return False

def debug_json_file(file_path: str, logger) -> dict:
    """Debug a JSON file to check its structure"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        debug_info = {
            'file': os.path.basename(file_path),
            'has_map': 'map_name' in data,
            'map_name': data.get('map_name', 'Not specified'),
            'has_ego': 'ego_spawn' in data,
            'actor_count': len(data.get('actors', [])),
            'has_weather': 'weather' in data,
            'weather': data.get('weather', 'Not specified'),
            'scenario_type': data.get('scenario_type', 'Not specified')
        }
        
        return debug_info
        
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return {'file': os.path.basename(file_path), 'error': str(e)}

def main():
    """Main batch conversion function"""
    logger = setup_logging()
    
    input_dir = "generated_scenarios"
    output_dir = "converted_scenarios"
    
    # Check if directories exist
    if not os.path.exists(input_dir):
        logger.error(f"Input directory {input_dir} does not exist")
        sys.exit(1)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"Created output directory {output_dir}")
    
    # Find JSON files
    json_files = find_json_files(input_dir)
    logger.info(f"Found {len(json_files)} JSON files to convert")
    
    if not json_files:
        logger.warning("No JSON files found for conversion")
        return
    
    # Create converter
    converter = JsonToXoscConverter()
    
    # Debug first few files
    logger.info("Debugging sample files:")
    for i, file_path in enumerate(json_files[:5]):
        debug_info = debug_json_file(file_path, logger)
        logger.info(f"  {debug_info}")
    
    # Convert all files
    successful = 0
    failed = 0
    
    for file_path in json_files:
        if convert_file(file_path, output_dir, converter, logger):
            successful += 1
        else:
            failed += 1
    
    logger.info(f"Conversion complete: {successful} successful, {failed} failed")
    
    # List converted files
    xosc_files = glob.glob(os.path.join(output_dir, "*.xosc"))
    logger.info(f"Generated {len(xosc_files)} XOSC files in {output_dir}")
    
    # Show sample of converted files
    if xosc_files:
        logger.info("Sample converted files:")
        for xosc_file in sorted(xosc_files)[:5]:
            logger.info(f"  {os.path.basename(xosc_file)}")

if __name__ == '__main__':
    main()
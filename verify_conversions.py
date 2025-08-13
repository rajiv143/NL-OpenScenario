#!/usr/bin/env python3
"""
Conversion Verification Script
Tests that the JSON to XOSC conversion worked correctly by analyzing converted files
"""

import os
import sys
import glob
import json
import xml.etree.ElementTree as ET
import logging
from pathlib import Path

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def parse_xosc_file(file_path: str) -> dict:
    """Parse an XOSC file and extract key information"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        info = {
            'file': os.path.basename(file_path),
            'valid_xml': True,
            'is_openscenario': root.tag == 'OpenSCENARIO',
            'has_file_header': root.find('FileHeader') is not None,
            'has_road_network': root.find('RoadNetwork') is not None,
            'has_entities': root.find('Entities') is not None,
            'has_storyboard': root.find('Storyboard') is not None,
            'map_name': None,
            'entity_count': 0,
            'weather_conditions': None
        }
        
        # Extract map name
        road_network = root.find('RoadNetwork')
        if road_network is not None:
            logic_file = road_network.find('LogicFile')
            if logic_file is not None:
                info['map_name'] = logic_file.get('filepath')
        
        # Count entities
        entities = root.find('Entities')
        if entities is not None:
            info['entity_count'] = len(entities.findall('ScenarioObject'))
        
        # Check for weather in environment (under Properties)
        properties = root.find('.//Properties')
        if properties is not None:
            for prop in properties.findall('Property'):
                if prop.get('name') == 'weather':
                    info['weather_conditions'] = prop.get('value')
                    break
        
        return info
        
    except ET.ParseError as e:
        return {
            'file': os.path.basename(file_path),
            'valid_xml': False,
            'error': f"XML Parse Error: {e}"
        }
    except Exception as e:
        return {
            'file': os.path.basename(file_path),
            'valid_xml': False,
            'error': f"Error: {e}"
        }

def load_original_json(json_file: str) -> dict:
    """Load the original JSON file to compare with XOSC"""
    try:
        with open(json_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {'error': str(e)}

def verify_conversion_pair(json_file: str, xosc_file: str) -> dict:
    """Verify that a JSON->XOSC conversion is correct"""
    json_data = load_original_json(json_file)
    xosc_info = parse_xosc_file(xosc_file)
    
    if not xosc_info.get('valid_xml', False):
        return {
            'pair': f"{os.path.basename(json_file)} -> {os.path.basename(xosc_file)}",
            'valid': False,
            'issues': [f"XOSC file invalid: {xosc_info.get('error', 'Unknown error')}"]
        }
    
    issues = []
    
    # Check basic structure
    if not xosc_info['is_openscenario']:
        issues.append("Not a valid OpenSCENARIO file")
    
    if not xosc_info['has_file_header']:
        issues.append("Missing FileHeader")
    
    if not xosc_info['has_road_network']:
        issues.append("Missing RoadNetwork")
    
    if not xosc_info['has_entities']:
        issues.append("Missing Entities")
    
    if not xosc_info['has_storyboard']:
        issues.append("Missing Storyboard")
    
    # Check map consistency
    if 'map_name' in json_data and json_data['map_name'] != xosc_info['map_name']:
        issues.append(f"Map mismatch: JSON has {json_data['map_name']}, XOSC has {xosc_info['map_name']}")
    
    # Check entity count (ego + actors)
    expected_entities = 1  # ego
    if 'actors' in json_data:
        expected_entities += len(json_data['actors'])
    
    if xosc_info['entity_count'] != expected_entities:
        issues.append(f"Entity count mismatch: expected {expected_entities}, got {xosc_info['entity_count']}")
    
    # Check weather consistency
    if 'weather' in json_data and json_data['weather'] != xosc_info['weather_conditions']:
        issues.append(f"Weather mismatch: JSON has {json_data['weather']}, XOSC has {xosc_info['weather_conditions']}")
    
    return {
        'pair': f"{os.path.basename(json_file)} -> {os.path.basename(xosc_file)}",
        'valid': len(issues) == 0,
        'issues': issues,
        'json_data': {
            'map': json_data.get('map_name', 'Unknown'),
            'weather': json_data.get('weather', 'Unknown'),
            'actors': len(json_data.get('actors', []))
        },
        'xosc_data': {
            'map': xosc_info['map_name'],
            'weather': xosc_info['weather_conditions'],
            'entities': xosc_info['entity_count']
        }
    }

def main():
    """Main verification function"""
    logger = setup_logging()
    
    json_dir = "generated_scenarios"
    xosc_dir = "converted_scenarios"
    
    # Check if directories exist
    if not os.path.exists(json_dir):
        logger.error(f"JSON directory {json_dir} does not exist")
        sys.exit(1)
    
    if not os.path.exists(xosc_dir):
        logger.error(f"XOSC directory {xosc_dir} does not exist")
        sys.exit(1)
    
    # Find all XOSC files
    xosc_files = glob.glob(os.path.join(xosc_dir, "*.xosc"))
    logger.info(f"Found {len(xosc_files)} XOSC files to verify")
    
    # Verify each conversion
    valid_conversions = 0
    invalid_conversions = 0
    
    for xosc_file in sorted(xosc_files)[:10]:  # Test first 10 files
        # Find corresponding JSON file
        base_name = os.path.splitext(os.path.basename(xosc_file))[0]
        json_file = os.path.join(json_dir, f"{base_name}.json")
        
        if not os.path.exists(json_file):
            logger.warning(f"No corresponding JSON file for {os.path.basename(xosc_file)}")
            continue
        
        # Verify the conversion
        result = verify_conversion_pair(json_file, xosc_file)
        
        if result['valid']:
            valid_conversions += 1
            logger.info(f"✓ {result['pair']} - VALID")
        else:
            invalid_conversions += 1
            logger.error(f"✗ {result['pair']} - INVALID")
            for issue in result['issues']:
                logger.error(f"  - {issue}")
        
        # Show details for first few files
        if valid_conversions + invalid_conversions <= 3:
            logger.info(f"  JSON: {result['json_data']}")
            logger.info(f"  XOSC: {result['xosc_data']}")
    
    logger.info(f"\nVerification Summary:")
    logger.info(f"  Valid conversions: {valid_conversions}")
    logger.info(f"  Invalid conversions: {invalid_conversions}")
    logger.info(f"  Success rate: {valid_conversions/(valid_conversions+invalid_conversions)*100:.1f}%")
    
    # Show a sample XOSC content
    if xosc_files:
        sample_file = xosc_files[0]
        logger.info(f"\nSample XOSC content from {os.path.basename(sample_file)}:")
        try:
            with open(sample_file, 'r') as f:
                content = f.read()
                # Show first 20 lines
                lines = content.split('\n')[:20]
                for i, line in enumerate(lines, 1):
                    logger.info(f"  {i:2d}: {line}")
                if len(content.split('\n')) > 20:
                    logger.info("  ... (truncated)")
        except Exception as e:
            logger.error(f"Error reading sample file: {e}")

if __name__ == '__main__':
    main()
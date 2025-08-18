#!/usr/bin/env python3
"""Quick test of a few conversions to see debug output"""

import os
import sys
import json
import glob
import logging

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter, ValidationError

def test_few_conversions():
    """Test conversion of first 5 files to see debug output"""
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # Get first 5 JSON files
    json_files = sorted(glob.glob("generated_scenarios/*.json"))[:5]
    
    output_dir = "test_conversions"
    os.makedirs(output_dir, exist_ok=True)
    
    converter = JsonToXoscConverter()
    
    for json_file in json_files:
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Converting {os.path.basename(json_file)}")
            logger.info(f"{'='*60}")
            
            # Load and examine JSON
            with open(json_file, 'r') as f:
                json_data = json.load(f)
            
            logger.info(f"Has map_name: {'map_name' in json_data}")
            logger.info(f"Has ego_spawn: {'ego_spawn' in json_data}")
            logger.info(f"Actor count: {len(json_data.get('actors', []))}")
            
            # Convert
            xosc_content = converter.convert(json_data)
            
            # Write output
            output_name = os.path.splitext(os.path.basename(json_file))[0] + '.xosc'
            output_path = os.path.join(output_dir, output_name)
            
            with open(output_path, 'w') as f:
                f.write(xosc_content)
            
            logger.info(f"✅ Successfully converted {os.path.basename(json_file)}")
            
        except Exception as e:
            logger.error(f"❌ Failed to convert {os.path.basename(json_file)}: {e}")
    
    # Summary
    xosc_files = glob.glob(os.path.join(output_dir, "*.xosc"))
    logger.info(f"\nGenerated {len(xosc_files)} XOSC files in {output_dir}/")

if __name__ == '__main__':
    test_few_conversions()
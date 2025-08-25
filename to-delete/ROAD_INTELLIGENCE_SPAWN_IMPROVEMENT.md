# Road Intelligence-Based Spawn Generation

## Summary

Successfully implemented a hybrid spawn generation system that prioritizes road intelligence data over pre-computed spawn points. This provides more reliable and accurate spawn positioning based on actual road geometry.

## Implementation Details

### New Method: `_generate_spawn_from_road_intelligence()`

This method generates spawn points directly from road geometry by:

1. **Filtering roads** based on criteria:
   - Lane types (Driving, Shoulder, Parking, etc.)
   - Road context (urban/town, highway, rural)
   - Speed limits
   - Road relationships (same_road, different_road)

2. **Calculating positions** from road geometry:
   - Selects appropriate road segments
   - Calculates position along road centerline
   - Applies lateral offsets for specific lanes
   - Ensures distance constraints are met

3. **Handling lane positioning**:
   - Uses actual lane width data
   - Calculates proper lateral offsets
   - Supports all lane types defined in road intelligence

### Hybrid Approach

The system now uses a two-tier approach:

1. **Primary**: Try to generate from road intelligence (most reliable)
2. **Fallback**: Use enhanced spawn files if road intelligence fails

### Key Improvements

1. **Accuracy**: Spawn points are calculated from actual road geometry
2. **Reliability**: Always generates valid positions on actual roads
3. **Lane Awareness**: Knows exact lane types and positions
4. **Context Mapping**: Maps between different naming conventions (urban ↔ town)
5. **Distance Control**: Better distance calculations along road paths

### Example Usage

```python
# The system automatically uses road intelligence when available
converter = JsonToXoscConverter()
scenario = {
    'map_name': 'Town01',
    'actors': [{
        'spawn': {
            'criteria': {
                'lane_type': 'Driving',
                'road_context': 'urban',
                'distance_to_ego': {'min': 20, 'max': 50}
            }
        }
    }]
}
xosc = converter.convert(scenario)
```

## Benefits Over Previous System

| Aspect | Old System | New System |
|--------|------------|------------|
| Data Source | Pre-computed spawn points | Real road geometry |
| Accuracy | Limited to pre-defined points | Mathematically precise |
| Lane Types | Approximate | Exact from road data |
| Flexibility | Fixed positions | Dynamic generation |
| Reliability | Depends on spawn file quality | Always valid on roads |

## Files Modified

- `xosc_json.py`:
  - Added `_generate_spawn_from_road_intelligence()` method
  - Modified `_choose_spawn()` to prioritize road intelligence
  - Added road context mapping for compatibility
  - Fixed None value handling in speed limit checks

## Testing

The system has been tested with:
- Multiple lane types (Driving, Shoulder, Parking)
- Different road contexts (urban, highway)
- Road relationships (same_road, different_road)
- Distance constraints
- Complex multi-actor scenarios

All tests confirm that the road intelligence-based generation is working correctly and provides more reliable spawn positioning than the previous system.

#!/usr/bin/env python3
"""
JSON to OpenSCENARIO (XOSC) Converter for CARLA
Converts flat, LLM-friendly JSON to valid OpenSCENARIO XML files
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom
import jsonschema
import os
import math
import argparse
import copy

# CARLA-specific model catalogs for validation
CARLA_VEHICLES = {
    # Generation 2 vehicles
    'vehicle.dodge.charger_2020', 'vehicle.lincoln.mkz_2020', 'vehicle.mercedes.coupe_2020',
    'vehicle.mini.cooper_s_2021', 'vehicle.nissan.patrol_2021', 'vehicle.carlamotors.european_hgv',
    'vehicle.tesla.cybertruck', 'vehicle.dodge.charger_police_2020', 'vehicle.carlamotors.firetruck',
    'vehicle.ford.ambulance', 'vehicle.mercedes.sprinter', 'vehicle.volkswagen.t2_2021',
    'vehicle.mitsubishi.fusorosa',
    # Generation 1 vehicles
    'vehicle.audi.a2', 'vehicle.audi.etron', 'vehicle.audi.tt', 'vehicle.bmw.grandtourer',
    'vehicle.chevrolet.impala', 'vehicle.citroen.c3', 'vehicle.dodge.charger_police',
    'vehicle.ford.crown', 'vehicle.ford.mustang', 'vehicle.jeep.wrangler_rubicon',
    'vehicle.lincoln.mkz_2017', 'vehicle.mercedes.coupe', 'vehicle.micro.microlino',
    'vehicle.nissan.micra', 'vehicle.nissan.patrol', 'vehicle.seat.leon',
    'vehicle.tesla.model3', 'vehicle.toyota.prius', 'vehicle.volkswagen.t2',
    # Motorcycles and bicycles
    'vehicle.harley-davidson.low_rider', 'vehicle.kawasaki.ninja', 'vehicle.vespa.zx125',
    'vehicle.yamaha.yzf', 'vehicle.bh.crossbike', 'vehicle.diamondback.century',
    'vehicle.gazelle.omafiets'
}

CARLA_PEDESTRIANS = {f'walker.pedestrian.{i:04d}' for i in range(1, 52)}

CARLA_MAPS = {
    'Town01', 'Town02', 'Town03', 'Town04', 'Town05', 
    'Town06', 'Town07', 'Town10', 'Town11', 'Town12', 'Town13', 'Town15'
}

# Weather presets mapping
WEATHER_PRESETS = {
    'clear': {'cloudiness': 0, 'precipitation': 0, 'sun_intensity': 0.85},
    'cloudy': {'cloudiness': 80, 'precipitation': 0, 'sun_intensity': 0.35},
    'wet': {'cloudiness': 20, 'precipitation': 20, 'sun_intensity': 0.65},
    'wet_cloudy': {'cloudiness': 80, 'precipitation': 20, 'sun_intensity': 0.35},
    'soft_rain': {'cloudiness': 70, 'precipitation': 30, 'sun_intensity': 0.35},
    'mid_rain': {'cloudiness': 80, 'precipitation': 60, 'sun_intensity': 0.25},
    'hard_rain': {'cloudiness': 90, 'precipitation': 90, 'sun_intensity': 0.15},
    'clear_noon': {'cloudiness': 0, 'precipitation': 0, 'sun_intensity': 1.0},
    'clear_sunset': {'cloudiness': 0, 'precipitation': 0, 'sun_intensity': 0.35}
}


class ValidationError(Exception):
    """Raised when JSON validation fails"""
    pass


class JsonToXoscConverter:
    def __init__(self, schema_path: Optional[str] = None):
        """Initialize converter with optional schema path"""
        self.schema = None
        if schema_path and os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                self.schema = json.load(f)
    
    def validate_json(self, data: Dict[str, Any]) -> None:
        """Validate JSON data against schema and CARLA-specific requirements"""
        # Schema validation if available
        if self.schema:
            try:
                jsonschema.validate(data, self.schema)
            except jsonschema.ValidationError as e:
                raise ValidationError(f"Schema validation failed: {e.message}")
        
        # CARLA-specific validation
        if data.get('map_name') not in CARLA_MAPS:
            raise ValidationError(f"Invalid map: {data.get('map_name')}")
        
        # Validate ego vehicle model
        ego_model = data.get('ego_vehicle_model', 'vehicle.tesla.model3')
        if ego_model not in CARLA_VEHICLES:
            raise ValidationError(f"Invalid ego vehicle model: {ego_model}")
        
        # Validate actors
        for actor in data.get('actors', []):
            if actor['type'] == 'vehicle':
                if actor['model'] not in CARLA_VEHICLES:
                    raise ValidationError(f"Invalid vehicle model: {actor['model']}")
            elif actor['type'] in ['pedestrian', 'cyclist']:
                if actor['model'] not in CARLA_PEDESTRIANS:
                    raise ValidationError(f"Invalid pedestrian model: {actor['model']}")
            
            # Validate color format if present
            if 'color' in actor:
                try:
                    r, g, b = map(int, actor['color'].split(','))
                    if not all(0 <= c <= 255 for c in [r, g, b]):
                        raise ValueError
                except:
                    raise ValidationError(f"Invalid color format: {actor['color']}")
    
    def parse_position(self, pos_str: str) -> Tuple[float, float, float, float]:
        """Parse position string 'x,y,z,yaw' with defaults"""
        parts = pos_str.split(',')
        x = float(parts[0])
        y = float(parts[1])
        z = float(parts[2]) if len(parts) > 2 else 0.5
        yaw = float(parts[3]) if len(parts) > 3 else 0.0
        # Convert yaw from degrees to radians
        yaw_rad = math.radians(yaw)
        return x, y, z, yaw_rad
    
    def create_file_header(self) -> ET.Element:
        """Create FileHeader element"""
        header = ET.Element('FileHeader')
        header.set('revMajor', '1')
        header.set('revMinor', '0')
        header.set('date', datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
        header.set('description', 'CARLA:GeneratedFromJSON')
        header.set('author', 'JSON2XOSC Converter')
        return header
    
    def create_environment(self, weather: str) -> ET.Element:
        """Create Environment element with weather settings"""
        env = ET.Element('Environment')
        env.set('name', 'Environment1')
        
        # TimeOfDay
        tod = ET.SubElement(env, 'TimeOfDay')
        tod.set('animation', 'false')
        tod.set('dateTime', '2020-01-01T12:00:00')
        
        # Weather
        weather_elem = ET.SubElement(env, 'Weather')
        weather_elem.set('cloudState', 'free')
        
        preset = WEATHER_PRESETS.get(weather, WEATHER_PRESETS['clear'])
        
        sun = ET.SubElement(weather_elem, 'Sun')
        sun.set('intensity', str(preset['sun_intensity']))
        sun.set('azimuth', '0')
        sun.set('elevation', '1.31')
        
        fog = ET.SubElement(weather_elem, 'Fog')
        fog.set('visualRange', '100000.0')
        
        precip = ET.SubElement(weather_elem, 'Precipitation')
        precip.set('precipitationType', 'rain' if preset['precipitation'] > 0 else 'dry')
        precip.set('intensity', str(preset['precipitation'] / 100.0))
        
        # RoadCondition
        road = ET.SubElement(env, 'RoadCondition')
        road.set('frictionScaleFactor', '1.0')
        
        return env
    
    def create_entities(self, data: Dict[str, Any]) -> ET.Element:
        """Create Entities section"""
        entities = ET.Element('Entities')
        
        # Ego vehicle
        ego = ET.SubElement(entities, 'ScenarioObject')
        ego.set('name', 'hero')
        
        ego_vehicle = ET.SubElement(ego, 'Vehicle')
        ego_vehicle.set('name', data.get('ego_vehicle_model', 'vehicle.tesla.model3'))
        ego_vehicle.set('vehicleCategory', 'car')
        
        # Standard vehicle elements
        ET.SubElement(ego_vehicle, 'ParameterDeclarations')
        
        perf = ET.SubElement(ego_vehicle, 'Performance')
        perf.set('maxSpeed', '69.444')
        perf.set('maxAcceleration', '200')
        perf.set('maxDeceleration', '10.0')
        
        bbox = ET.SubElement(ego_vehicle, 'BoundingBox')
        center = ET.SubElement(bbox, 'Center')
        center.set('x', '1.5')
        center.set('y', '0.0')
        center.set('z', '0.9')
        dim = ET.SubElement(bbox, 'Dimensions')
        dim.set('width', '2.1')
        dim.set('length', '4.5')
        dim.set('height', '1.8')
        
        axles = ET.SubElement(ego_vehicle, 'Axles')
        front = ET.SubElement(axles, 'FrontAxle')
        front.set('maxSteering', '0.5')
        front.set('wheelDiameter', '0.6')
        front.set('trackWidth', '1.8')
        front.set('positionX', '3.1')
        front.set('positionZ', '0.3')
        rear = ET.SubElement(axles, 'RearAxle')
        rear.set('maxSteering', '0.0')
        rear.set('wheelDiameter', '0.6')
        rear.set('trackWidth', '1.8')
        rear.set('positionX', '0.0')
        rear.set('positionZ', '0.3')
        
        props = ET.SubElement(ego_vehicle, 'Properties')
        prop = ET.SubElement(props, 'Property')
        prop.set('name', 'type')
        prop.set('value', 'ego_vehicle')
        
        # Other actors
        for actor in data.get('actors', []):
            obj = ET.SubElement(entities, 'ScenarioObject')
            obj.set('name', actor['id'])
            
            if actor['type'] in ['vehicle', 'cyclist']:
                vehicle = ET.SubElement(obj, 'Vehicle')
                vehicle.set('name', actor['model'])
                vehicle.set('vehicleCategory', 'bicycle' if actor['type'] == 'cyclist' else 'car')
                
                # Copy standard vehicle elements
                ET.SubElement(vehicle, 'ParameterDeclarations')
                vehicle.append(copy.deepcopy(perf))
                vehicle.append(copy.deepcopy(bbox))
                vehicle.append(copy.deepcopy(axles))
                
                props = ET.SubElement(vehicle, 'Properties')
                prop = ET.SubElement(props, 'Property')
                prop.set('name', 'type')
                prop.set('value', 'simulation')
                
                if 'color' in actor:
                    color_prop = ET.SubElement(props, 'Property')
                    color_prop.set('name', 'color')
                    color_prop.set('value', actor['color'])
                    
            elif actor['type'] == 'pedestrian':
                ped = ET.SubElement(obj, 'Pedestrian')
                ped.set('model', actor['model'])
                ped.set('mass', '90.0')
                ped.set('name', actor['model'])
                ped.set('pedestrianCategory', 'pedestrian')
                
                ET.SubElement(ped, 'ParameterDeclarations')
                ped.append(copy.deepcopy(bbox))
                
                props = ET.SubElement(ped, 'Properties')
                prop = ET.SubElement(props, 'Property')
                prop.set('name', 'type')
                prop.set('value', 'simulation')
                
            elif actor['type'] == 'static_object':
                misc = ET.SubElement(obj, 'MiscObject')
                misc.set('mass', '500.0')
                misc.set('name', actor['model'])
                misc.set('miscObjectCategory', 'obstacle')
                
                ET.SubElement(misc, 'ParameterDeclarations')
                misc.append(copy.deepcopy(bbox))
                
                props = ET.SubElement(misc, 'Properties')
                prop = ET.SubElement(props, 'Property')
                prop.set('name', 'type')
                prop.set('value', 'simulation')
        
        return entities
    
    def create_init(self, data: Dict[str, Any]) -> ET.Element:
        """Create Init section with positions and environment"""
        init = ET.Element('Init')
        actions = ET.SubElement(init, 'Actions')
        
        # Global actions (environment)
        global_action = ET.SubElement(actions, 'GlobalAction')
        env_action = ET.SubElement(global_action, 'EnvironmentAction')
        env_action.append(self.create_environment(data.get('weather', 'clear')))
        
        # Ego vehicle position
        ego_private = ET.SubElement(actions, 'Private')
        ego_private.set('entityRef', 'hero')
        
        ego_action = ET.SubElement(ego_private, 'PrivateAction')
        teleport = ET.SubElement(ego_action, 'TeleportAction')
        position = ET.SubElement(teleport, 'Position')
        world_pos = ET.SubElement(position, 'WorldPosition')
        
        x, y, z, yaw = self.parse_position(data['ego_start_position'])
        world_pos.set('x', str(x))
        world_pos.set('y', str(y))
        world_pos.set('z', str(z))
        world_pos.set('h', str(yaw))
        
        # Controller assignment
        ctrl_action = ET.SubElement(ego_private, 'PrivateAction')
        ctrl = ET.SubElement(ctrl_action, 'ControllerAction')
        assign = ET.SubElement(ctrl, 'AssignControllerAction')
        controller = ET.SubElement(assign, 'Controller')
        controller.set('name', 'HeroAgent')
        ctrl_props = ET.SubElement(controller, 'Properties')
        ctrl_prop = ET.SubElement(ctrl_props, 'Property')
        ctrl_prop.set('name', 'module')
        ctrl_prop.set('value', 'external_control')
        
        override = ET.SubElement(ctrl, 'OverrideControllerValueAction')
        for control in ['Throttle', 'Brake', 'Clutch', 'ParkingBrake', 'SteeringWheel', 'Gear']:
            elem = ET.SubElement(override, control)
            if control == 'Gear':
                elem.set('number', '0')
            else:
                elem.set('value', '0')
            elem.set('active', 'false')
        
        # Other actors positions
        for actor in data.get('actors', []):
            private = ET.SubElement(actions, 'Private')
            private.set('entityRef', actor['id'])
            
            action = ET.SubElement(private, 'PrivateAction')
            teleport = ET.SubElement(action, 'TeleportAction')
            position = ET.SubElement(teleport, 'Position')
            world_pos = ET.SubElement(position, 'WorldPosition')
            
            x, y, z, yaw = self.parse_position(actor['start_position'])
            world_pos.set('x', str(x))
            world_pos.set('y', str(y))
            world_pos.set('z', str(z))
            world_pos.set('h', str(yaw))
        
        return init
    
    def create_storyboard(self, data: Dict[str, Any]) -> ET.Element:
        """Create Storyboard with Init + one Story/Act + ManeuverGroups + valid StopTrigger"""
        sb = ET.Element('Storyboard')
        sb.append(self.create_init(data))

        # --- one Story with one Act ---
        story = ET.SubElement(sb, 'Story', {'name': 'MyStory'})
        act   = ET.SubElement(story, 'Act',   {'name': 'Behavior'})

        # group actions by actor
        actor_groups: Dict[str, List[Dict[str,Any]]] = {}
        for action in data.get('actions', []):
            actor_groups.setdefault(action['actor_id'], []).append(action)

        for actor_id, actions in actor_groups.items():
            mg = ET.SubElement(act, 'ManeuverGroup', {
                'maximumExecutionCount': '1',
                'name':                  f'{actor_id}ManeuverGroup'
            })
            actors = ET.SubElement(mg, 'Actors', {
                'selectTriggeringEntities': 'false'
            })
            ET.SubElement(actors, 'EntityRef', {
                'entityRef': 'hero' if actor_id=='ego' else actor_id
            })

            man = ET.SubElement(mg, 'Maneuver', {
                'name': f'{actor_id}Maneuver'
            })

            # iterate and chain events
            for i, action in enumerate(actions):
                ev_name = f"{actor_id}Event{i}"
                ac_name = f"{actor_id}Action{i}"

                ev = ET.SubElement(man, 'Event', {
                    'name':     ev_name,
                    'priority': 'overwrite'
                })
                ac = ET.SubElement(ev, 'Action', {'name': ac_name})
                pa = ET.SubElement(ac, 'PrivateAction')

                # --- build the PrivateAction body ---
                atype = action['action_type']
                if atype == 'wait':
                    la = ET.SubElement(pa, 'LongitudinalAction')
                    sa = ET.SubElement(la, 'SpeedAction')
                    ET.SubElement(sa, 'SpeedActionDynamics', {
                        'dynamicsDimension': action.get('dynamics_dimension','time'),
                        'dynamicsShape':     action.get('dynamics_shape','step'),
                        'value':             str(action.get('wait_duration',0))
                    })
                    tgt = ET.SubElement(sa, 'SpeedActionTarget')
                    ET.SubElement(tgt, 'AbsoluteTargetSpeed', {'value':'0'})

                elif atype in ('speed','stop'):
                    la = ET.SubElement(pa, 'LongitudinalAction')
                    sa = ET.SubElement(la, 'SpeedAction')
                    speed_val = 0 if atype=='stop' else action.get('speed_value',0)
                    ET.SubElement(sa, 'SpeedActionDynamics', {
                        'dynamicsDimension': action.get('dynamics_dimension','time'),
                        'dynamicsShape':     action.get('dynamics_shape','step'),
                        'value':             str(action.get('dynamics_value',0))
                    })
                    tgt = ET.SubElement(sa, 'SpeedActionTarget')
                    ET.SubElement(tgt, 'AbsoluteTargetSpeed', {'value': str(speed_val)})

                elif atype == 'lane_change':
                    la = ET.SubElement(pa, 'LateralAction')
                    lc = ET.SubElement(la, 'LaneChangeAction')
                    ET.SubElement(lc, 'LaneChangeActionDynamics', {
                        'dynamicsDimension':'distance',
                        'dynamicsShape':    'linear',
                        'value':            str(action.get('dynamics_value',1))
                    })
                    tgt = ET.SubElement(lc, 'LaneChangeTarget')
                    ET.SubElement(tgt, 'RelativeTargetLane', {
                        'entityRef': 'hero' if actor_id=='ego' else actor_id,
                        'value':     '-1' if action.get('lane_direction')=='left' else '1'
                    })

                # --- StartTrigger under this Event ---
                st = ET.SubElement(ev, 'StartTrigger')
                cg = ET.SubElement(st, 'ConditionGroup')
                cond = ET.SubElement(cg, 'Condition', {
                    'name':         f'StartCondition{i}',
                    'delay':        '0',
                    'conditionEdge':'rising'
                })

                ttype = action['trigger_type']
                if ttype=='time':
                    bv = ET.SubElement(cond, 'ByValueCondition')
                    ET.SubElement(bv, 'SimulationTimeCondition', {
                        'value': str(action.get('trigger_value',0)),
                        'rule':  'greaterThan'
                    })

                elif ttype=='distance_to_ego':
                    be = ET.SubElement(cond, 'ByEntityCondition')
                    te = ET.SubElement(be, 'TriggeringEntities', {
                        'triggeringEntitiesRule':'any'
                    })
                    ET.SubElement(te, 'EntityRef', {'entityRef':'hero'})
                    ec = ET.SubElement(be, 'EntityCondition')
                    ET.SubElement(ec, 'RelativeDistanceCondition', {
                        'entityRef':            actor_id,
                        'relativeDistanceType': 'longitudinal',
                        'value':                str(action.get('trigger_value',10)),
                        'freespace':            'false',
                        'rule':                 {'<':'lessThan','>':'greaterThan'}.get(
                                                action.get('trigger_comparison','<'),
                                                'lessThan')
                    })

                elif ttype=='after_previous':
                    # chain on previous action completion
                    prev_ref = f"{actor_id}Action{i-1}"
                    bv = ET.SubElement(cond, 'ByValueCondition')
                    ET.SubElement(bv, 'StoryboardElementStateCondition', {
                        'storyboardElementType': 'action',
                        'storyboardElementRef':  prev_ref,
                        'state':                 'completeState'
                    })

        # --- Act-level StartTrigger ---
        ast = ET.SubElement(act, 'StartTrigger')
        acg = ET.SubElement(ast, 'ConditionGroup')
        aco = ET.SubElement(acg, 'Condition', {
            'name':'OverallStartCondition','delay':'0','conditionEdge':'rising'
        })
        bv = ET.SubElement(aco, 'ByValueCondition')
        ET.SubElement(bv, 'SimulationTimeCondition', {
            'value':'0','rule':'greaterThan'
        })

        # --- Act-level StopTrigger: only driven distance ---
        astp = ET.SubElement(act, 'StopTrigger')
        scg  = ET.SubElement(astp, 'ConditionGroup')
        sco  = ET.SubElement(scg, 'Condition', {
            'name':'EndCondition','delay':'0','conditionEdge':'rising'
        })
        be   = ET.SubElement(sco, 'ByEntityCondition')
        te   = ET.SubElement(be, 'TriggeringEntities', {'triggeringEntitiesRule':'any'})
        ET.SubElement(te, 'EntityRef', {'entityRef':'hero'})
        ec   = ET.SubElement(be, 'EntityCondition')
        ET.SubElement(ec, 'TraveledDistanceCondition', {
            'value': str(data.get('success_distance', 100))
        })

        # --- Storyboard-level StopTrigger: timeout + collision ---
        sbt = ET.SubElement(sb, 'StopTrigger')
        scg2 = ET.SubElement(sbt, 'ConditionGroup')
        # timeout
        timeout = data.get('timeout')
        if timeout is not None:
            cond = ET.SubElement(scg2, 'Condition', {
                'name':'Timeout','delay':'0','conditionEdge':'rising'
            })
            bv2 = ET.SubElement(cond, 'ByValueCondition')
            ET.SubElement(bv2, 'SimulationTimeCondition', {
                'value': str(timeout),
                'rule':  'greaterThan'
            })
        # collision
        if not data.get('collision_allowed', True):
            cond = ET.SubElement(scg2, 'Condition', {
                'name':'criteria_CollisionTest','delay':'0','conditionEdge':'rising'
            })
            bec = ET.SubElement(cond, 'ByEntityCondition')
            te2 = ET.SubElement(bec, 'TriggeringEntities', {'triggeringEntitiesRule':'any'})
            ET.SubElement(te2, 'EntityRef', {'entityRef':'hero'})
            ec2 = ET.SubElement(bec, 'EntityCondition')
            cc  = ET.SubElement(ec2, 'CollisionCondition')
            ET.SubElement(cc, 'EntityRef', {'entityRef':'hero'})

        return sb



    
    def convert(self, json_data: Dict[str, Any]) -> str:
        """Convert JSON to OpenSCENARIO XML string"""
        # Validate first
        self.validate_json(json_data)
        
        # Create root element
        root = ET.Element('OpenSCENARIO')
        
        # Add main sections
        root.append(self.create_file_header())
        ET.SubElement(root, 'ParameterDeclarations')
        ET.SubElement(root, 'CatalogLocations')
        
        # RoadNetwork
        road_network = ET.SubElement(root, 'RoadNetwork')
        logic_file = ET.SubElement(road_network, 'LogicFile')
        logic_file.set('filepath', json_data['map_name'])
        ET.SubElement(road_network, 'SceneGraphFile').set('filepath', '')
        
        # Entities
        root.append(self.create_entities(json_data))
        
        # Storyboard
        root.append(self.create_storyboard(json_data))
        
        # Pretty print
        return self.prettify_xml(root)
    
    def prettify_xml(self, elem: ET.Element) -> str:
        """Return a pretty-printed XML string"""
        rough_string = ET.tostring(elem, 'unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Convert JSON to OpenSCENARIO')
    parser.add_argument('input', help='Input JSON file')
    parser.add_argument('-o', '--output', help='Output XOSC file (default: input.xosc)')
    parser.add_argument('-s', '--schema', help='JSON schema file for validation')
    parser.add_argument('-v', '--validate-only', action='store_true', 
                       help='Only validate, do not convert')
    
    args = parser.parse_args()
    
    # Load JSON
    try:
        with open(args.input, 'r') as f:
            json_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        sys.exit(1)
    
    # Create converter
    converter = JsonToXoscConverter(args.schema)
    
    # Validate only mode
    if args.validate_only:
        try:
            converter.validate_json(json_data)
            print("Validation successful!")
            sys.exit(0)
        except ValidationError as e:
            print(f"Validation failed: {e}")
            sys.exit(1)
    
    # Convert
    try:
        xosc_content = converter.convert(json_data)
        
        # Determine output file
        output_file = args.output
        if not output_file:
            base_name = os.path.splitext(args.input)[0]
            output_file = f"{base_name}.xosc"
        
        # Write output
        with open(output_file, 'w') as f:
            f.write(xosc_content)
        
        print(f"Successfully converted to {output_file}")
        
    except ValidationError as e:
        print(f"Validation error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Conversion error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
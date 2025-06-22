import json
import xml.etree.ElementTree as ET

def generate_xosc_from_json(json_input, output_path):
    # Load JSON data (json_input can be a dict or JSON string)
    if isinstance(json_input, str):
        scenario_data = json.loads(json_input)
    else:
        scenario_data = json_input

    # Helper function to create a sub-element with text or attributes
    def create_element(parent, tag, text=None, attrib=None):
        if attrib is None: attrib = {}
        elem = ET.SubElement(parent, tag, attrib)
        if text:
            elem.text = str(text)
        return elem

        # 1) Root
    root = ET.Element('OpenScenario')

    # 2) FileHeader
    create_element(root, 'FileHeader', attrib={
        'author': 'ScenarioGenerator',
        'date': '2025-01-01T00:00:00',
        'description': 'Generated scenario'
    })

    # 3) Empty ParameterDeclarations (required by schema)
    create_element(root, 'ParameterDeclarations')

    # 4) CatalogLocations (not <Catalogs>)
    catalog_locs = create_element(root, 'CatalogLocations')
    create_element(catalog_locs, 'VehicleCatalog', attrib={
        'catalogName': 'VehicleCatalog',
        'filepath': 'catalogs/VehicleCatalog.xosc'
    })
    create_element(catalog_locs, 'ControllerCatalog', attrib={
        'catalogName': 'ControllerCatalog',
        'filepath': 'catalogs/ControllerCatalog.xosc'
    })

    # 5) RoadNetwork
    rn = create_element(root, 'RoadNetwork')
    town_map = scenario_data['RoadNetwork']['town']
    create_element(rn, 'LogicFile', attrib={
        'filepath': f'maps/{town_map}.xodr',
        'databaseType': 'OpenDRIVE'
    })

    # 6) Entities
    entities_elem = create_element(root, 'Entities')
    for ent in scenario_data['Entities']:
        obj = create_element(entities_elem, 'ScenarioObject', attrib={'name': ent['name']})
        # vehicle catalog reference
        create_element(obj, 'CatalogReference', attrib={
            'catalogName': 'VehicleCatalog',
            'entryName': ent['vehicle_type']
        })
        # controller, if provided
        if ent.get('controller'):
            ctrl = create_element(obj, 'Controller')
            create_element(ctrl, 'CatalogReference', attrib={
                'catalogName': 'ControllerCatalog',
                'entryName': ent['controller']
            })

    # 7) Storyboard (rest of your script continues here)…
    storyboard = create_element(root, 'Storyboard')

    # Init phase: initial actions (teleports and initial speeds)
    init_elem = create_element(storyboard, 'Init')
    init_actions = create_element(init_elem, 'Actions')
    # Create a teleport action and (optionally) speed action for each entity
    for ent in scenario_data['Entities']:
        # Private actions are used for entity-specific init actions
        private = create_element(init_actions, 'Private', attrib={'entityRef': ent['name']})
        # TeleportAction to initial position
        teleport_action = create_element(private, 'PrivateAction')
        teleport = create_element(teleport_action, 'TeleportAction')
        world_pos = create_element(teleport, 'Position')
        create_element(world_pos, 'WorldPosition', attrib={
            'x': str(ent['position']['x']),
            'y': str(ent['position']['y']),
            'z': str(ent['position']['z']),
            'h': str(ent['position']['yaw'])  # 'h' is heading (yaw) in OpenScenario
        })
        # If an initial speed is specified, set a SpeedAction
        if ent.get('initialSpeed', 0) > 0:
            speed_action = create_element(private, 'PrivateAction')
            longitudinal = create_element(speed_action, 'LongitudinalAction')
            speed = create_element(longitudinal, 'SpeedAction')
            # Setting speed with absolute target value
            create_element(speed, 'SpeedActionDynamics', attrib={
                'speedDynamicsType': 'step',      # instantaneous change
                'dynamicsShape': 'step',
                'value': '0'                     # no transition time
            })
            create_element(speed, 'SpeedActionTarget').append(
                ET.Element('AbsoluteTargetSpeed', {"value": str(ent['initialSpeed'])})
            )

    # Story definition(s)
    stories = scenario_data.get('Storyboard', {}).get('Story', [])
    # Ensure we have at least one story in JSON; if not, create a default story wrapper
    if not stories:
        stories = [ {"name": "MainStory", "Acts": scenario_data.get('Storyboard', {}).get('Acts', [])} ]
    for story_def in stories:
        story_elem = create_element(storyboard, 'Story', attrib={'name': story_def['name']})
        # Each Story contains Acts
        for act_def in story_def['Acts']:
            act_elem = create_element(story_elem, 'Act', attrib={'name': act_def['name']})
            # StartTrigger for the Act
            start_trigger = create_element(act_elem, 'StartTrigger')
            cond_group = create_element(start_trigger, 'ConditionGroup')
            # Parse the startTrigger condition from JSON
            trig = act_def.get('startTrigger', {})
            if trig:
                cond = create_element(cond_group, 'Condition', attrib={'conditionEdge': 'rising'})
                trig_type = trig.get('type', 'simulation_time')
                if trig_type == 'simulation_time':
                    # e.g., condition: {"value": 2.0} meaning start after 2 seconds
                    sim_time = trig.get('condition', {}).get('value', 0)
                    sim_cond = create_element(cond, 'ByValueCondition')
                    create_element(sim_cond, 'SimulationTimeCondition', attrib={
                        'value': str(sim_time), 'rule': 'greaterThan'
                    })
                # (Additional trigger types like distance or state can be handled similarly)
            else:
                # If no trigger specified, default to start at time 0
                cond = create_element(cond_group, 'Condition', attrib={'conditionEdge': 'rising'})
                sim_cond = create_element(cond, 'ByValueCondition')
                create_element(sim_cond, 'SimulationTimeCondition', attrib={
                    'value': '0', 'rule': 'greaterThan'
                })

            # ManeuverGroups
            for mg_def in act_def.get('ManeuverGroups', []):
                actors = " ".join(mg_def.get('actors', []))
                mg_elem = create_element(act_elem, 'ManeuverGroup', attrib={'actors': actors})
                for man_def in mg_def.get('maneuvers', []):
                    maneuver_elem = create_element(mg_elem, 'Maneuver', attrib={'name': man_def['name']})
                    for evt_def in man_def.get('events', []):
                        event_elem = create_element(maneuver_elem, 'Event', attrib={
                            'name': evt_def['name'], 'priority': 'overwrite'
                        })
                        # Event trigger
                        event_trigger = create_element(event_elem, 'StartTrigger')
                        cg = create_element(event_trigger, 'ConditionGroup')
                        cond = create_element(cg, 'Condition', attrib={'conditionEdge': 'rising'})
                        evt_trig = evt_def.get('trigger', {})
                        # Handle a couple of trigger types for example
                        if evt_trig.get('type') == 'simulation_time':
                            sim_time = evt_trig.get('condition', {}).get('value', 0)
                            sim_cond = create_element(cond, 'ByValueCondition')
                            create_element(sim_cond, 'SimulationTimeCondition', attrib={
                                'value': str(sim_time), 'rule': 'greaterThan'
                            })
                        elif evt_trig.get('type') == 'entity_distance':
                            dist = evt_trig.get('condition', {}).get('distance', 0)
                            target = evt_trig.get('condition', {}).get('entity', '')
                            ent_cond = create_element(cond, 'ByEntityCondition')
                            rel_dist_cond = create_element(ent_cond, 'RelativeDistanceCondition', attrib={
                                'entityRef': target,
                                'value': str(dist),
                                'freespace': 'true',
                                'relativeDistanceType': 'longitudinal',
                                'rule': 'lessThan'
                            })
                        # ... other condition types (position reach, etc.) could be added ...

                        # Event actions
                        actions_elem = create_element(event_elem, 'Action')
                        for act in evt_def.get('actions', []):
                            action_type = act.get('type')
                            if action_type == 'SpeedAction':
                                # Longitudinal Speed Action
                                long_act = create_element(actions_elem, 'PrivateAction')
                                speed_act = create_element(create_element(long_act, 'LongitudinalAction'), 'SpeedAction')
                                # Set dynamics
                                dynamics_shape = act.get('transition', 'step')
                                create_element(speed_act, 'SpeedActionDynamics', attrib={
                                    'dynamicsShape': dynamics_shape,
                                    'speedDynamicsType': dynamics_shape,
                                    'value': '0'  # 0s for instantaneous if step, or a time value if gradual
                                })
                                create_element(speed_act, 'SpeedActionTarget').append(
                                    ET.Element('AbsoluteTargetSpeed', {"value": str(act.get('speed', 0))})
                                )
                            elif action_type == 'LaneChangeAction':
                                # Lateral Lane Change Action
                                lat_act = create_element(actions_elem, 'PrivateAction')
                                lane_act = create_element(create_element(lat_act, 'LateralAction'), 'LaneChangeAction')
                                direction = act.get('direction', 'none')
                                # Define lane change action: 'left' or 'right' translates to lane change target
                                target_lane_offset = "-1" if direction == "left" else "1"
                                create_element(lane_act, 'LaneChangeActionDynamics', attrib={
                                    'dynamicsShape': 'linear', 'laneChangeDynamics': 'laneChange', 'value': '1'
                                })
                                create_element(lane_act, 'LaneChangeTarget').append(
                                    ET.Element('RelativeTargetLane', {"value": target_lane_offset})
                                )
                            # (Other action types can be added as needed)
            # EndTrigger for Act (if specified)
            if 'endTrigger' in act_def:
                end_trig = act_def['endTrigger']
                end_trigger_elem = create_element(act_elem, 'StopTrigger')
                cg = create_element(end_trigger_elem, 'ConditionGroup')
                cond = create_element(cg, 'Condition', attrib={'conditionEdge': 'rising'})
                end_type = end_trig.get('type')
                if end_type == 'collision':
                    coll_cond = create_element(cond, 'ByEntityCondition')
                    create_element(coll_cond, 'CollisionCondition', attrib={
                        'entityRef': end_trig.get('condition', {}).get('entity', 'EgoVehicle'),
                        'collisionType': 'any'
                    })
                elif end_type == 'duration':
                    dur = end_trig.get('condition', {}).get('seconds', 0)
                    sim_cond = create_element(cond, 'ByValueCondition')
                    create_element(sim_cond, 'SimulationTimeCondition', attrib={
                        'value': str(dur), 'rule': 'greaterThan'
                    })
                # ... more end condition types if needed ...

    # StopTrigger for entire Storyboard (global stop condition, if provided)
    if 'StopTrigger' in scenario_data['Storyboard']:
        stop = scenario_data['Storyboard']['StopTrigger']
        stop_trigger_elem = create_element(storyboard, 'StopTrigger')
        cg = create_element(stop_trigger_elem, 'ConditionGroup')
        cond = create_element(cg, 'Condition', attrib={'conditionEdge': 'rising'})
        stype = stop.get('type')
        if stype == 'collision':
            coll_cond = create_element(cond, 'ByEntityCondition')
            create_element(coll_cond, 'CollisionCondition', attrib={
                'entityRef': stop.get('condition', {}).get('entity', 'EgoVehicle'),
                'collisionType': 'any'
            })
        elif stype == 'time':
            tval = stop.get('condition', {}).get('seconds', 0)
            sim_cond = create_element(cond, 'ByValueCondition')
            create_element(sim_cond, 'SimulationTimeCondition', attrib={
                'value': str(tval), 'rule': 'greaterThan'
            })
        # ... other global stop conditions as needed ...

    # Write out the XML tree to .xosc file
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding='UTF-8', xml_declaration=True)

if __name__ == "__main__":
    json_filename = "test.json"
    with open(json_filename, 'r') as f:
        scenario_data = json.load(f)
        generate_xosc_from_json(scenario_data, "output.xosc")
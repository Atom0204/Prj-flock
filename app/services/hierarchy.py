from typing import List, Dict, Any, Optional
from app.models.schemas import HierarchyTreeNode

HIERARCHY_LEVELS = [
    "zone",
    "circle",
    "division",
    "subdivision",
    "substation",
    "feeder",
    "dt"
]

def build_hierarchy_tree(meters: List[Dict[str, Any]]) -> List[HierarchyTreeNode]:
    """
    Reconstructs the full utility distribution hierarchy from meter records.
    Levels: Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT -> Meters
    Handles missing or inconsistent levels gracefully.
    Calculates aggregated meter counts for every branch.
    """
    root_dict: Dict[str, Any] = {}

    for meter in meters:
        h = meter.get("hierarchy") or {}
        current_dict = root_dict

        for level in HIERARCHY_LEVELS:
            node_info = h.get(level)
            if not node_info or not isinstance(node_info, dict):
                # Fallback for inconsistent/incomplete data
                code = f"UNKNOWN_{level.upper()}"
                name = f"Unknown {level.title()}"
            else:
                code = node_info.get("code") or f"UNKNOWN_{level.upper()}"
                name = node_info.get("name") or code

            key = (level, code)
            if key not in current_dict:
                current_dict[key] = {
                    "id": code,
                    "name": name,
                    "level": level,
                    "meter_count": 0,
                    "children": {}
                }

            current_dict[key]["meter_count"] += 1
            current_dict = current_dict[key]["children"]

    def convert_dict_to_nodes(d: Dict[Any, Any]) -> List[HierarchyTreeNode]:
        nodes: List[HierarchyTreeNode] = []
        for key, val in d.items():
            children_nodes = convert_dict_to_nodes(val["children"])
            # Sort children by name/code for consistent deterministic presentation
            children_nodes.sort(key=lambda x: x.name)
            nodes.append(
                HierarchyTreeNode(
                    id=val["id"],
                    name=val["name"],
                    level=val["level"],
                    meter_count=val["meter_count"],
                    children=children_nodes
                )
            )
        nodes.sort(key=lambda x: x.name)
        return nodes

    return convert_dict_to_nodes(root_dict)

import pytest
from app.services.hierarchy import build_hierarchy_tree

def test_hierarchy_tree_reconstruction():
    sample_meters = [
        {
            "meterId": "M1",
            "hierarchy": {
                "zone": {"name": "Zone A", "code": "Z-A"},
                "circle": {"name": "Circle 1", "code": "C-1"},
                "division": {"name": "Div 1", "code": "D-1"},
                "subdivision": {"name": "SubDiv 1", "code": "SD-1"},
                "substation": {"name": "SubStation 1", "code": "SS-1"},
                "feeder": {"name": "Feeder 1", "code": "F-1"},
                "dt": {"name": "DT 1", "code": "DT-1"}
            }
        },
        {
            "meterId": "M2",
            "hierarchy": {
                "zone": {"name": "Zone A", "code": "Z-A"},
                "circle": {"name": "Circle 1", "code": "C-1"},
                "division": {"name": "Div 1", "code": "D-1"},
                "subdivision": {"name": "SubDiv 1", "code": "SD-1"},
                "substation": {"name": "SubStation 1", "code": "SS-1"},
                "feeder": {"name": "Feeder 1", "code": "F-1"},
                "dt": {"name": "DT 1", "code": "DT-1"}
            }
        },
        {
            "meterId": "M3",
            "hierarchy": {
                "zone": {"name": "Zone A", "code": "Z-A"},
                "circle": {"name": "Circle 1", "code": "C-1"},
                "division": {"name": "Div 1", "code": "D-1"},
                "subdivision": {"name": "SubDiv 1", "code": "SD-1"},
                "substation": {"name": "SubStation 1", "code": "SS-1"},
                "feeder": {"name": "Feeder 2", "code": "F-2"},
                "dt": {"name": "DT 2", "code": "DT-2"}
            }
        }
    ]

    tree = build_hierarchy_tree(sample_meters)
    assert len(tree) == 1
    zone_node = tree[0]
    assert zone_node.name == "Zone A"
    assert zone_node.id == "Z-A"
    assert zone_node.meter_count == 3

    # Navigate to feeders
    circle = zone_node.children[0]
    division = circle.children[0]
    subdivision = division.children[0]
    substation = subdivision.children[0]
    assert len(substation.children) == 2  # Feeder 1 and Feeder 2

    feeder1 = next(f for f in substation.children if f.id == "F-1")
    assert feeder1.meter_count == 2
    assert feeder1.children[0].meter_count == 2

def test_hierarchy_tree_handles_missing_data():
    messy_meters = [
        {
            "meterId": "M_MESSY",
            "hierarchy": {
                "zone": {"name": "Zone X", "code": "Z-X"}
                # Missing all lower tiers
            }
        }
    ]
    tree = build_hierarchy_tree(messy_meters)
    assert len(tree) == 1
    zone = tree[0]
    assert zone.id == "Z-X"
    # Fallback nodes should be generated gracefully
    assert len(zone.children) == 1
    assert "UNKNOWN" in zone.children[0].id

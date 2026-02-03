# SPACES.py
# This acts as your database for physical room dimensions.

ROOM_DB = {
    "BUNKER": {
        "dims": {'x': 0.55, 'y': 0.56, 'z': 1.60},
        "config": {
            'levels': [0.65, 1.01, 1.49],   # Height of horizontal bars
            'pillar_thickness': 0.04,
            'bar_thickness': 0.02
        }
    },
    
    "Greenhouse": {
        "dims": {'x': 2.00, 'y': 3.00, 'z': 2.50},
        "config": {
            'levels': [1.00, 2.00],         # Bars at 1m and 2m
            'pillar_thickness': 0.10,
            'bar_thickness': 0.05
        }
    },

}
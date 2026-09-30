import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
from scipy.interpolate import interp1d

class TemporalBoundaryError(Exception):
    pass

class IMDTrackHarmonizer:
    def __init__(self):
        self.track_data = []
        self.timestamps = []
        self._interpolators = {}

    def classify_intensity(self, v_max_knots: float) -> str:
        """Classifies cyclone intensity based strictly on the IMD Knots Thresholds."""
        if v_max_knots < 17.0:
            return "LPA"
        elif 17.0 <= v_max_knots <= 27.99:
            return "D"
        elif 28.0 <= v_max_knots <= 33.99:
            return "DD"
        elif 34.0 <= v_max_knots <= 47.99:
            return "CS"
        elif 48.0 <= v_max_knots <= 63.99:
            return "SCS"
        elif 64.0 <= v_max_knots <= 89.99:
            return "VSCS"
        elif 90.0 <= v_max_knots <= 119.99:
            return "ESCS"
        else:
            return "SuCS"

    def parse_track_csv(self, csv_path: Path) -> List[Dict]:
        """Parses historical IMD records capturing the RSMC New Delhi standard."""
        parsed = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                
                # Extract fields per spec
                v_max_knots = float(row['v_max_knots'])
                p_central_hpa = float(row['p_central_hpa'])
                
                parsed.append({
                    'cyclone_id': row['cyclone_id'],
                    'timestamp': ts,
                    'center_lat': float(row['center_lat']),
                    'center_lon': float(row['center_lon']),
                    'v_max_knots': v_max_knots,
                    'v_max_kmh': v_max_knots * 1.852,
                    'p_central_hpa': p_central_hpa,
                    'delta_p_hpa': float(row.get('delta_p_hpa', 1010.0 - p_central_hpa)),
                    'imd_category': row.get('imd_category', self.classify_intensity(v_max_knots))
                })
        
        # Chronological sort
        parsed.sort(key=lambda x: x['timestamp'])
        self.track_data = parsed
        self.timestamps = [p['timestamp'].timestamp() for p in parsed]
        
        if len(self.track_data) > 1:
            # Build cubic spline or linear interpolators over the timestamp series
            times = np.array(self.timestamps)
            lats = np.array([p['center_lat'] for p in parsed])
            lons = np.array([p['center_lon'] for p in parsed])
            vmaxs = np.array([p['v_max_knots'] for p in parsed])
            pressures = np.array([p['p_central_hpa'] for p in parsed])
            
            # Linear interpolation guarantees non-overshooting between 3/6-hourly intervals
            self._interpolators['lat'] = interp1d(times, lats, kind='linear')
            self._interpolators['lon'] = interp1d(times, lons, kind='linear')
            self._interpolators['v_max'] = interp1d(times, vmaxs, kind='linear')
            self._interpolators['pressure'] = interp1d(times, pressures, kind='linear')
            
        return parsed

    def interpolate_state(self, target_time: datetime) -> Optional[Dict]:
        """Interpolates track position and intensity at half-hourly satellite pass times."""
        if not self.track_data:
            return None
            
        target_ts = target_time.timestamp()
        
        # Reject queries outside the storm's lifespan
        if target_ts < self.timestamps[0] or target_ts > self.timestamps[-1]:
            raise TemporalBoundaryError(f"Target time {target_time} is outside the known track lifespan.")
            
        # Execute interpolations
        lat = float(self._interpolators['lat'](target_ts))
        lon = float(self._interpolators['lon'](target_ts))
        v_max = float(self._interpolators['v_max'](target_ts))
        pressure = float(self._interpolators['pressure'](target_ts))
        
        v_max_kmh = v_max * 1.852
        delta_p = 1010.0 - pressure
        
        return {
            'cyclone_id': self.track_data[0]['cyclone_id'],
            'timestamp': target_time,
            'center_lat': lat,
            'center_lon': lon,
            'v_max_knots': v_max,
            'v_max_kmh': v_max_kmh,
            'p_central_hpa': pressure,
            'delta_p_hpa': delta_p,
            'imd_category': self.classify_intensity(v_max)
        }

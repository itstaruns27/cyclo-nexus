import tempfile
import csv
from datetime import datetime, timezone
from pathlib import Path
import pytest

from data_pipeline.preprocessing.imd_track_harmonizer import IMDTrackHarmonizer, TemporalBoundaryError

@pytest.fixture
def mock_imd_csv():
    """Create a synthetic 6-hour track for a historical cyclone."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'cyclone_id', 'timestamp', 'center_lat', 'center_lon', 
            'v_max_knots', 'p_central_hpa', 'delta_p_hpa'
        ])
        writer.writeheader()
        
        # t0: 50 knots (SCS)
        writer.writerow({
            'cyclone_id': 'BOB01_2020',
            'timestamp': '2020-05-18T00:00:00Z',
            'center_lat': 10.0,
            'center_lon': 85.0,
            'v_max_knots': 50.0,
            'p_central_hpa': 990.0,
            'delta_p_hpa': 20.0
        })
        
        # t0 + 6h: 70 knots (VSCS)
        writer.writerow({
            'cyclone_id': 'BOB01_2020',
            'timestamp': '2020-05-18T06:00:00Z',
            'center_lat': 11.0,
            'center_lon': 85.6,
            'v_max_knots': 70.0,
            'p_central_hpa': 975.0,
            'delta_p_hpa': 35.0
        })
        
        filepath = Path(f.name)
        
    yield filepath
    filepath.unlink()

def test_classify_intensity():
    harmonizer = IMDTrackHarmonizer()
    assert harmonizer.classify_intensity(15.0) == "LPA"
    assert harmonizer.classify_intensity(20.0) == "D"
    assert harmonizer.classify_intensity(30.0) == "DD"
    assert harmonizer.classify_intensity(40.0) == "CS"
    assert harmonizer.classify_intensity(50.0) == "SCS"
    assert harmonizer.classify_intensity(70.0) == "VSCS"
    assert harmonizer.classify_intensity(100.0) == "ESCS"
    assert harmonizer.classify_intensity(130.0) == "SuCS"

def test_interpolate_exact_observations(mock_imd_csv):
    """Verify ground-truth preservation at exact observation points."""
    harmonizer = IMDTrackHarmonizer()
    harmonizer.parse_track_csv(mock_imd_csv)
    
    t0 = datetime(2020, 5, 18, 0, 0, 0, tzinfo=timezone.utc)
    state = harmonizer.interpolate_state(t0)
    
    assert state['center_lat'] == 10.0
    assert state['center_lon'] == 85.0
    assert state['v_max_knots'] == 50.0
    assert state['imd_category'] == "SCS"

def test_interpolate_half_hour(mock_imd_csv):
    """Verify smooth coordinate and intensity interpolation at t0 + 1.5h."""
    harmonizer = IMDTrackHarmonizer()
    harmonizer.parse_track_csv(mock_imd_csv)
    
    # 1.5 hours represents 25% of the 6-hour gap
    t_target = datetime(2020, 5, 18, 1, 30, 0, tzinfo=timezone.utc)
    state = harmonizer.interpolate_state(t_target)
    
    # Lat: 10.0 to 11.0 -> 10.25 (25%)
    # Lon: 85.0 to 85.6 -> 85.15 (25%)
    # V_max: 50.0 to 70.0 -> 55.0 (25%)
    
    assert pytest.approx(state['center_lat']) == 10.25
    assert pytest.approx(state['center_lon']) == 85.15
    assert pytest.approx(state['v_max_knots']) == 55.0
    # 55 knots remains within the SCS category (48-63 kts)
    assert state['imd_category'] == "SCS"

def test_category_boundary_transition(mock_imd_csv):
    """Test dynamic re-categorization when boundary thresholds are crossed during interpolation."""
    harmonizer = IMDTrackHarmonizer()
    harmonizer.parse_track_csv(mock_imd_csv)
    
    # VSCS triggers at 64 knots. 
    # Gap is 50 to 70 (20 knots). 64 is 14 knots delta -> 70% of 6h = 4h 12m.
    t_boundary = datetime(2020, 5, 18, 4, 12, 0, tzinfo=timezone.utc)
    state = harmonizer.interpolate_state(t_boundary)
    
    assert pytest.approx(state['v_max_knots']) == 64.0
    # System officially transitioned to VSCS at this half-hour timestep
    assert state['imd_category'] == "VSCS"

def test_temporal_boundary_error(mock_imd_csv):
    """Queries outside the known lifespan must raise exceptions."""
    harmonizer = IMDTrackHarmonizer()
    harmonizer.parse_track_csv(mock_imd_csv)
    
    t_out = datetime(2020, 5, 17, 23, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(TemporalBoundaryError, match="outside the known track lifespan"):
        harmonizer.interpolate_state(t_out)

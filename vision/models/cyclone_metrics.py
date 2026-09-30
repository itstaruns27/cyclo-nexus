"""
Task 9: IMD Classification & Eye Diameter Metrics Head
══════════════════════════════════════════════════════
Owner: Agent BRAVO | Skill: [SKILL:YOLO_OBB_CV]

Post-processing metrics head for YOLO-OBB cyclone detections.
Decoupled from PyTorch, operating purely on Numpy and built-ins for
efficient downstream execution.
"""

from typing import Dict, Any

from schemas.imd_scale import IMDCategory, IMD_LABELS

# Map integer YOLO class ID to IMDCategory enum
_ID_TO_CATEGORY = {
    0: IMDCategory.D,
    1: IMDCategory.DD,
    2: IMDCategory.CS,
    3: IMDCategory.SCS,
    4: IMDCategory.VSCS,
    5: IMDCategory.ESCS,
    6: IMDCategory.SuCS,
}


class IMDClassificationHead:
    """
    Translates raw YOLO class predictions into official IMD classifications.
    """
    
    @staticmethod
    def get_classification(class_id: int, confidence: float) -> Dict[str, Any]:
        """
        Maps a YOLO class ID to IMD metadata.
        
        Args:
            class_id: Integer YOLO prediction (0-6).
            confidence: Prediction confidence score.
            
        Returns:
            Dictionary containing category string and descriptive name.
            
        Raises:
            ValueError: If class_id is not in [0, 6].
        """
        if class_id not in _ID_TO_CATEGORY:
            raise ValueError(f"Invalid class ID {class_id}. Must be between 0 and 6.")
            
        category = _ID_TO_CATEGORY[class_id]
        name = IMD_LABELS[category]
        
        return {
            "category": category.value,
            "name": name,
            "confidence": float(confidence)
        }


class EyeDiameterEstimator:
    """
    Estimates the physical diameter of a cyclone's eye based on its 
    normalized CDO bounding box dimensions and intensity class.
    """
    
    # 1024x1024 grid covers 32 degrees of latitude.
    # 32 degrees * 111 km/degree = 3552 km total.
    # 3552 km / 1024 pixels = 3.46875 km/pixel.
    KM_PER_PIXEL = 3.46875
    GRID_SIZE = 1024.0
    
    @staticmethod
    def estimate_eye_diameter(width_norm: float, height_norm: float, class_id: int) -> float:
        """
        Calculates estimated eye diameter in kilometers.
        
        Args:
            width_norm: Normalized OBB width in [0.0, 1.0].
            height_norm: Normalized OBB height in [0.0, 1.0].
            class_id: Integer YOLO prediction (0-6).
            
        Returns:
            Estimated eye diameter in km (rounded to 2 decimal places).
            Returns 0.0 for low-intensity systems lacking a well-defined eye.
        """
        if class_id not in _ID_TO_CATEGORY:
            raise ValueError(f"Invalid class ID {class_id}. Must be between 0 and 6.")
            
        # Low intensity systems (D, DD, CS) don't have well-defined eyes
        if class_id < 3:
            return 0.0
            
        # CDO Size based on minor axis
        minor_axis_norm = min(width_norm, height_norm)
        cdo_size_km = minor_axis_norm * EyeDiameterEstimator.GRID_SIZE * EyeDiameterEstimator.KM_PER_PIXEL
        
        # Heuristic: Eye diameter is ~15% of CDO minor axis for intense systems
        eye_diameter_km = cdo_size_km * 0.15
        
        return round(eye_diameter_km, 2)

"""
Task 8: Physics-Aware Data Augmentation Engine
════════════════════════════════════════════════
Owner: Agent BRAVO | Skill: [SKILL:YOLO_OBB_CV]

Applies physics-aware spatial augmentations to cyclone satellite tensors
and their corresponding YOLO-OBB labels.

Enforces the Coriolis constraint: cyclones in the Northern Hemisphere
strictly rotate counter-clockwise. Therefore, horizontal and vertical
flips are physically invalid as they would reverse the fluid dynamics.
Only rotation is permitted.
"""

import math
import random
import torch
import torchvision.transforms.functional as F


class PhysicsAwareAugmenter:
    """
    Augmentation engine enforcing NIO thermodynamic constraints.
    """

    @staticmethod
    def rotate_tensor(tensor: torch.Tensor, angle_degrees: float) -> torch.Tensor:
        """
        Rotates a 4-channel tensor around its center using bilinear interpolation.
        
        Args:
            tensor: (4, H, W) satellite tensor.
            angle_degrees: Rotation angle in degrees.
            
        Returns:
            Rotated tensor, padded with 0.0 at the edges.
        """
        # F.rotate with a positive angle rotates CCW in the image plane.
        # To match our label rotation math (where a positive angle maps the right edge
        # to the bottom edge, which is CW in the image plane), we negate the angle.
        return F.rotate(
            tensor, 
            -angle_degrees, 
            interpolation=F.InterpolationMode.BILINEAR, 
            fill=0.0
        )

    @staticmethod
    def rotate_obb_label(label: tuple, angle_degrees: float) -> tuple:
        """
        Rotates a YOLO-OBB label around the normalized center (0.5, 0.5).
        
        Args:
            label: Tuple of (class_id, x_c, y_c, w, h, theta).
                   Coords are normalized [0.0, 1.0].
            angle_degrees: Rotation angle in degrees.
            
        Returns:
            New label tuple with rotated coordinates, wrapped theta, 
            and swapped w/h if necessary.
        """
        class_id, x_c, y_c, w, h, theta = label
        
        rad = math.radians(angle_degrees)
        dx = x_c - 0.5
        dy = y_c - 0.5
        
        # 2D Rotation matrix (CW in image plane, matches -angle_degrees in F.rotate)
        new_dx = dx * math.cos(rad) - dy * math.sin(rad)
        new_dy = dx * math.sin(rad) + dy * math.cos(rad)
        
        new_x_c = 0.5 + new_dx
        new_y_c = 0.5 + new_dy
        
        # Update bounding box angle
        new_theta = theta + rad
        
        # Wrap theta into YOLO-OBB bounds [-pi/2, pi/2)
        while new_theta >= math.pi / 2:
            new_theta -= math.pi / 2
            w, h = h, w
        while new_theta < -math.pi / 2:
            new_theta += math.pi / 2
            w, h = h, w
            
        return (
            class_id, 
            round(new_x_c, 6), 
            round(new_y_c, 6), 
            round(w, 6), 
            round(h, 6), 
            round(new_theta, 6)
        )

    def random_transform(self, tensor: torch.Tensor, label: tuple) -> tuple:
        """
        Applies a random rotation between [-180, 180] degrees to both tensor and label.
        """
        angle_degrees = random.uniform(-180.0, 180.0)
        new_tensor = self.rotate_tensor(tensor, angle_degrees)
        new_label = self.rotate_obb_label(label, angle_degrees)
        return new_tensor, new_label

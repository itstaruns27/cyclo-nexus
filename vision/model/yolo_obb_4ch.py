"""
Task 8: YOLO-OBB 4-Channel Adaptation
═════════════════════════════════════
Owner: Agent BRAVO | Skill: [SKILL:YOLO_OBB_CV]

Adapts Ultralytics YOLO-OBB backbone to accept 4-channel input:
- Modify first Conv2d from in_channels=3 to in_channels=4
- Copy/average weights across first 3 channels, zero-init channel 4

STUB — Agent BRAVO will implement.
"""

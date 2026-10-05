"""
Grad-CAM for the satellite intensity CNN (master plan v5, Task 3.5)
═══════════════════════════════════════════════════════════════════
heatmap_jpeg(net, crop_u8) → JPEG bytes: the infrared image (cold cloud bright) with the regions that pushed the
wind estimate up drawn in warm colours (Selvaraju et al., Grad-CAM, ICCV 2017), ≈ 6–10 kB.
"""

import io

import numpy as np
import torch
import torch.nn.functional as F


def gradcam(net, crop_u8):
    """(128, 128) map in [0, 1] for the CNN's wind output; crop_u8 (3, 128, 128) uint8."""
    net.eval()
    feats = {}
    layer = net.f[-1]                                         # last conv block (8 × 8 before pooling → 4 × 4)
    conv = layer[-2] if isinstance(layer, torch.nn.Sequential) else layer

    def fwd(_, __, out):
        feats["a"] = out
        out.register_hook(lambda g: feats.__setitem__("g", g))
    h = conv.register_forward_hook(fwd)
    try:
        x = torch.from_numpy(crop_u8[None].astype(np.float32) / 255.0)
        y = net(x)
        net.zero_grad(set_to_none=True)
        y.sum().backward()
    finally:
        h.remove()
    a, g = feats["a"][0], feats["g"][0]
    cam = F.relu((g.mean(dim=(1, 2))[:, None, None] * a).sum(0))
    cam = F.interpolate(cam[None, None], size=crop_u8.shape[1:], mode="bilinear", align_corners=False)[0, 0]
    cam = cam.detach().numpy()
    return cam / cam.max() if cam.max() > 0 else cam


def heatmap_jpeg(net, crop_u8, size=192):
    from PIL import Image
    cam = gradcam(net, crop_u8)
    ir = 255 - crop_u8[0].astype(np.float32)                 # cold (high) clouds bright, as forecasters view IR
    ir = (ir - ir.min()) / max(1.0, ir.max() - ir.min())
    base = np.stack([ir] * 3, -1)
    heat = np.stack([np.clip(cam * 2, 0, 1), np.clip(cam * 2 - 0.6, 0, 1) * 0.8, np.zeros_like(cam)], -1)
    alpha = np.clip(cam, 0, 1)[..., None] * 0.65
    img = (base * (1 - alpha) + heat * alpha) * 255
    im = Image.fromarray(img.astype(np.uint8)).resize((size, size), Image.BILINEAR)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()

# CYCLO-NEXUS Webhook API Contract

> **Version:** 1.0.0  
> **Owner:** ARCHITECT (locked)  
> **Consumers:** Agent CHARLIE (Colab dispatcher), Agent DELTA (webhook receiver)

---

## Endpoint

```
POST https://<hostinger-domain>/api/v1/webhook/inference
```

## Required Headers

| Header | Value | Description |
|--------|-------|-------------|
| `Content-Type` | `application/json` | Always JSON payload |
| `Content-Encoding` | `gzip` | Payload is gzip-compressed |
| `X-CycloNexus-Version` | `1.0.0` | Schema version for forward compat |
| `X-CycloNexus-Timestamp` | ISO-8601 UTC | Signing timestamp |
| `X-CycloNexus-Signature` | hex string | HMAC-SHA256 of `"<timestamp>." + raw body` (uncompressed) |

## Authentication Protocol (HMAC-SHA256)

### Sender (Colab Worker)

```python
import hashlib
import hmac
import gzip
import json
from datetime import datetime, timezone

def sign_and_send(payload: dict, webhook_url: str, secret: str):
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Sign "<timestamp>.<raw JSON bytes>" — binding the timestamp prevents replaying
    # a captured body with a fresh timestamp header
    signature = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("utf-8") + b"." + raw_body,
        hashlib.sha256
    ).hexdigest()
    
    # Compress payload
    compressed = gzip.compress(raw_body)
    
    headers = {
        "Content-Type": "application/json",
        "Content-Encoding": "gzip",
        "X-CycloNexus-Version": "1.0.0",
        "X-CycloNexus-Timestamp": timestamp,
        "X-CycloNexus-Signature": signature,
    }
    
    # POST via requests
    import requests
    response = requests.post(webhook_url, data=compressed, headers=headers)
    return response
```

### Receiver (Hostinger Express.js Middleware)

```javascript
const crypto = require('crypto');

function verifyWebhookSignature(req, res, next) {
    const signature = req.headers['x-cyclonexus-signature'];
    const timestamp = req.headers['x-cyclonexus-timestamp'];
    const version   = req.headers['x-cyclonexus-version'];
    
    // 1. Validate required headers
    if (!signature || !timestamp || !version) {
        return res.status(401).json({ error: 'Missing authentication headers' });
    }
    
    // 2. Reject stale timestamps (±300 seconds)
    const requestTime = new Date(timestamp).getTime();
    const serverTime  = Date.now();
    if (Math.abs(serverTime - requestTime) > 300_000) {
        return res.status(401).json({ error: 'Timestamp outside acceptable window' });
    }
    
    // 3. Recompute HMAC over "<timestamp>." + raw (decompressed) body
    const expectedSig = crypto
        .createHmac('sha256', process.env.WEBHOOK_SECRET)
        .update(`${timestamp}.`)
        .update(req.rawBody)  // Raw body preserved by middleware
        .digest('hex');
    
    // 4. Constant-time comparison
    if (!crypto.timingSafeEqual(
        Buffer.from(signature, 'hex'),
        Buffer.from(expectedSig, 'hex')
    )) {
        return res.status(401).json({ error: 'Invalid signature' });
    }
    
    next();
}
```

## Payload Schema

The request body conforms to `schemas/geojson_spec.json` — a GeoJSON `FeatureCollection` with `metadata` envelope.

## Response Codes

| Code | Meaning |
|------|---------|
| `200` | Payload accepted and stored |
| `400` | Malformed payload (validation error) |
| `401` | Authentication failure |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

## Compression & Caching

- **Request**: Gzip-compressed JSON from Colab → Hostinger.
- **Response Caching**: GET endpoints use `node-cache` with 30s TTL. Cache invalidated on new webhook POST.
- **Grad-CAM images**: Stored as WebP, served with `Cache-Control: public, max-age=3600`.

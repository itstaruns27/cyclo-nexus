/**
 * Zod Payload Validators
 * ══════════════════════
 * Owner: Agent DELTA
 *
 * Runtime validation for webhook payloads matching schemas/geojson_spec.json.
 */

const { z } = require('zod');

const featureTypeEnum = z.enum([
  'current_eye',
  'historical_track',
  'forecast_track',
  'forecast_cone',
  'obb_outline',
  'gradcam_bounds',
]);

const imdCategoryEnum = z.enum(['D', 'DD', 'CS', 'SCS', 'VSCS', 'ESCS', 'SuCS']);

const metadataSchema = z.object({
  payload_version: z.string().regex(/^\d+\.\d+\.\d+$/),
  cyclone_id: z.string().min(3),
  cyclone_name: z.string().nullable().optional(),
  basin: z.enum(['NIO', 'BOB', 'AS']),
  generated_at: z.string().datetime({ offset: true }),
  // v4: provenance of the payload and optional link to an existing (official) system
  source: z.enum(['AI_SATELLITE']).optional(),
  status: z.enum(['active', 'watch']).optional(),
  link_cyclone_id: z.string().min(3).nullable().optional(),
});

const heartbeatSchema = z.object({
  component: z.string().regex(/^[a-z_]{3,32}$/),
  status: z.enum(['ok', 'degraded', 'error']),
  message: z.string().max(1000).nullable().optional(),
  last_data_time: z.string().datetime({ offset: true }).nullable().optional(),
  details: z.record(z.any()).optional(),
});

const featureSchema = z.object({
  type: z.literal('Feature'),
  geometry: z.object({
    type: z.enum(['Point', 'LineString', 'Polygon', 'MultiPoint']),
    coordinates: z.any(),
  }),
  properties: z.object({
    feature_type: featureTypeEnum,
  }).passthrough(),
});

const webhookPayloadSchema = z.object({
  type: z.literal('FeatureCollection'),
  metadata: metadataSchema,
  features: z.array(featureSchema).min(1),
});

/**
 * Validate a webhook payload against the GeoJSON schema.
 * @param {object} body - Parsed JSON body
 * @returns {{ success: boolean, data?: object, errors?: string[] }}
 */
function validateWebhookPayload(body) {
  const result = webhookPayloadSchema.safeParse(body);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return {
    success: false,
    errors: result.error.issues.map(i => `${i.path.join('.')}: ${i.message}`),
  };
}

/** AI consensus forecast attached to an existing official system (forecaster/guidance/live.py). */
const forecastPayloadSchema = z.object({
  cyclone_id: z.string().min(3).max(64),
  source: z.enum(['AI_CONSENSUS']),
  generated_at: z.string().datetime({ offset: true }),
  init_time: z.string().datetime({ offset: true }),
  members: z.array(z.string().regex(/^[A-Z0-9-]{2,12}$/)).min(2).max(16),
  points: z.array(z.object({
    hour: z.number().int().min(6).max(168),
    lat: z.number().min(-30).max(50),
    lon: z.number().min(30).max(130),
    wind_kt: z.number().min(0).max(200).nullable(),
    cone_radius_km: z.number().min(0).max(2000).nullable(),
    verified_error_km: z.number().min(0).max(2000).nullable().optional(),
  })).min(1).max(40),
});

function validateForecastPayload(body) {
  const result = forecastPayloadSchema.safeParse(body);
  if (result.success) return { success: true, data: result.data };
  return { success: false, errors: result.error.issues.map(i => `${i.path.join('.')}: ${i.message}`) };
}

function validateHeartbeat(body) {
  const result = heartbeatSchema.safeParse(body);
  if (result.success) return { success: true, data: result.data };
  return { success: false, errors: result.error.issues.map(i => `${i.path.join('.')}: ${i.message}`) };
}

module.exports = { validateWebhookPayload, validateHeartbeat, validateForecastPayload, forecastPayloadSchema, webhookPayloadSchema, heartbeatSchema, imdCategoryEnum };

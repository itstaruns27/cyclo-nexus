/**
 * CYCLO-NEXUS Frontend Type Contracts (TypeScript Declarations)
 * ═════════════════════════════════════════════════════════════
 * Version: 1.0.0
 * Owner: ARCHITECT (locked)
 * Consumer: Agent ECHO (Read-Only)
 *
 * These types mirror schemas/telemetry_contract.py exactly.
 */

export type IMDCategory = 'D' | 'DD' | 'CS' | 'SCS' | 'VSCS' | 'ESCS' | 'SuCS';

export interface IMDWindRange {
  readonly category: IMDCategory;
  readonly minWindKmh: number;
  readonly maxWindKmh: number;
  readonly label: string;
}

export interface OrientedBoundingBox {
  x_center: number;
  y_center: number;
  width: number;
  height: number;
  theta: number;
}

export interface EyeMetrics {
  eye_diameter_km: number;
  eyewall_thickness_km?: number;
  eye_symmetry_score?: number;
}

export interface AtmosphericState {
  timestamp: string;
  latitude: number;
  longitude: number;
  sustained_wind_kmh: number;
  sustained_wind_knots: number;
  central_pressure_hpa: number;
  environmental_pressure_hpa: number;
  imd_category: IMDCategory;
}

export interface ForecastPoint {
  forecast_hour: 6 | 12 | 24 | 48 | 72;
  predicted_lat: number;
  predicted_lon: number;
  predicted_wind_kmh: number;
  predicted_pressure_hpa: number;
  predicted_imd_category: IMDCategory;
  sigma_lat: number;
  sigma_lon: number;
  confidence: number;
}

export interface GradCAMMetadata {
  heatmap_uri: string;
  target_layer: string;
  channel_index: 0 | 1 | 2 | 3;
  min_activation: number;
  max_activation: number;
  timestamp: string;
}

export interface CycloneTelemetryPayload {
  payload_version: string;
  cyclone_id: string;
  cyclone_name?: string | null;
  basin: 'NIO' | 'BOB' | 'AS';
  generated_at: string;
  current_state: AtmosphericState;
  obb: OrientedBoundingBox;
  eye_metrics?: EyeMetrics | null;
  detection_confidence: number;
  historical_track: AtmosphericState[];
  forecast_track: ForecastPoint[];
  gradcam?: GradCAMMetadata[] | null;
}

export type CycloneFeatureType =
  | 'current_eye'
  | 'historical_track'
  | 'forecast_track'
  | 'forecast_cone'
  | 'obb_outline'
  | 'gradcam_bounds';

export interface CycloneGeoJSONProperties {
  feature_type: CycloneFeatureType;
  timestamp?: string;
  forecast_hour?: 6 | 12 | 24 | 48 | 72;
  imd_category?: IMDCategory;
  sustained_wind_kmh?: number;
  sustained_wind_knots?: number;
  central_pressure_hpa?: number;
  eye_diameter_km?: number;
  detection_confidence?: number;
  obb_params?: OrientedBoundingBox;
  sigma_lat?: number;
  sigma_lon?: number;
  confidence?: number;
  gradcam_heatmap_uri?: string;
}

export interface CycloneGeoJSONMetadata {
  payload_version: string;
  cyclone_id: string;
  cyclone_name?: string | null;
  basin: 'NIO' | 'BOB' | 'AS';
  generated_at: string;
}

export interface CycloneFeatureCollection {
  type: 'FeatureCollection';
  metadata: CycloneGeoJSONMetadata;
  features: Array<{
    type: 'Feature';
    geometry: GeoJSON.Geometry;
    properties: CycloneGeoJSONProperties;
  }>;
}

export type AlertLevel = 'RED' | 'ORANGE' | 'YELLOW';

export interface GeminiAdvisoryResponse {
  alert_level: AlertLevel;
  threat_summary: string;
  estimated_landfall_window: string;
  coastal_evacuation_priority: string[];
  actionable_directives: {
    fishermen: string;
    general_public: string;
    district_administration: string;
  };
  language: string;
  generated_at: string;
}

export interface APIResponse<T> {
  success: boolean;
  data: T;
  timestamp: string;
  cached: boolean;
}

export interface CycloneListItem {
  cyclone_id: string;
  cyclone_name?: string | null;
  imd_category: IMDCategory;
  current_lat: number;
  current_lon: number;
  sustained_wind_kmh: number;
  last_updated: string;
}

export interface CreateJobRequestDto {
  topic: string;
  duration_preset?: string | null;
  duration_seconds?: number | null;
  tts_provider?: string | null;
  voice?: string | null;
  visual_mode?: string | null;
  asset_providers?: string[] | null;
}

export interface JobResponseDto {
  job_id: string;
  execution_state: string;
  pipeline_status: string | null;
  current_stage: string | null;
  last_completed_stage: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  has_video: boolean;
  warnings: string[];
  review_reasons: string[];
}

export interface JobListResponseDto {
  jobs: JobResponseDto[];
}

export interface HealthResponseDto {
  service: string;
  status: string;
}

export interface ProviderCapabilityDto {
  id: string;
  provider: string;
  media_kind: string;
  source_type: string;
  query_strategy: string;
  runtime_status: string;
  requires_api_key: boolean;
}

export interface DurationPresetDto {
  id: string;
  target_sec: number;
}

export interface DurationCapabilitiesDto {
  presets: DurationPresetDto[];
  min_sec: number;
  max_sec: number;
  default: string;
}

export interface TtsProviderCapabilityDto {
  id: string;
  default: boolean;
  available: boolean;
}

export interface VoiceCapabilitiesDto {
  note: string;
  default: string;
  elevenlabs_from_env: boolean;
}

export interface CapabilitiesDto {
  visual_modes: string[];
  media_preferences: string[];
  asset_preferences: string[];
  providers: ProviderCapabilityDto[];
  duration: DurationCapabilitiesDto;
  tts_providers: TtsProviderCapabilityDto[];
  voices: VoiceCapabilitiesDto;
}

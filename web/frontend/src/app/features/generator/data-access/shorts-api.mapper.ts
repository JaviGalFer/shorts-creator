import type { Capabilities, ProviderCapability, DurationPreset, TtsProviderCapability } from '../model/capabilities.model';
import type { GenerationCommand } from '../model/generation-command.model';
import type { ExecutionState, Job } from '../model/job.model';
import type {
  CapabilitiesDto,
  CreateJobRequestDto,
  JobResponseDto,
} from './shorts-api.dto';

export function mapJob(dto: JobResponseDto): Job {
  return {
    jobId: dto.job_id,
    executionState: dto.execution_state as ExecutionState,
    pipelineStatus: dto.pipeline_status,
    currentStage: dto.current_stage,
    lastCompletedStage: dto.last_completed_stage,
    createdAt: dto.created_at,
    startedAt: dto.started_at,
    finishedAt: dto.finished_at,
    hasVideo: dto.has_video,
    warnings: Array.isArray(dto.warnings) ? [...dto.warnings] : [],
    reviewReasons: Array.isArray(dto.review_reasons) ? [...dto.review_reasons] : [],
  };
}

export function mapProvider(p: CapabilitiesDto['providers'][number]): ProviderCapability {
  return {
    id: p.id,
    sourceType: p.source_type,
    queryStrategy: p.query_strategy,
    runtimeStatus: p.runtime_status,
    requiresApiKey: p.requires_api_key,
  };
}

export function mapDurationPreset(p: CapabilitiesDto['duration']['presets'][number]): DurationPreset {
  return {
    id: p.id,
    targetSec: p.target_sec,
  };
}

export function mapTtsProvider(p: CapabilitiesDto['tts_providers'][number]): TtsProviderCapability {
  return {
    id: p.id,
    isDefault: p.default,
    available: p.available,
  };
}

export function mapCapabilities(dto: CapabilitiesDto): Capabilities {
  return {
    visualModes: [...dto.visual_modes],
    mediaPreferences: [...dto.media_preferences],
    assetPreferences: [...dto.asset_preferences],
    providers: dto.providers.map(mapProvider),
    duration: {
      presets: dto.duration.presets.map(mapDurationPreset),
      minSec: dto.duration.min_sec,
      maxSec: dto.duration.max_sec,
      default: dto.duration.default,
    },
    ttsProviders: dto.tts_providers.map(mapTtsProvider),
    voices: {
      note: dto.voices.note,
      default: dto.voices.default,
      elevenlabsFromEnv: dto.voices.elevenlabs_from_env,
    },
  };
}

export function mapCreateCommandToRequest(command: GenerationCommand): CreateJobRequestDto {
  const request: CreateJobRequestDto = { topic: command.topic.trim() };
  if (command.durationPreset != null && command.durationPreset !== '') {
    request.duration_preset = command.durationPreset;
  }
  if (command.durationSeconds != null) {
    request.duration_seconds = command.durationSeconds;
  }
  if (command.ttsProvider != null && command.ttsProvider !== '') {
    request.tts_provider = command.ttsProvider;
  }
  if (command.voice != null && command.voice.trim() !== '') {
    request.voice = command.voice.trim();
  }
  if (command.visualMode != null && command.visualMode !== '') {
    request.visual_mode = command.visualMode;
  }
  if (command.assetProviders != null && command.assetProviders.length > 0) {
    request.asset_providers = [...command.assetProviders];
  }
  return request;
}

import { describe, expect, it } from 'vitest';

import { mapCapabilities, mapCreateCommandToRequest, mapJob } from './shorts-api.mapper';
import type { CapabilitiesDto, JobResponseDto } from './shorts-api.dto';

const jobDto: JobResponseDto = {
  job_id: '123e4567-e89b-42d3-a456-426614174000',
  execution_state: 'FINISHED',
  pipeline_status: 'REVIEW_REQUIRED',
  current_stage: 'validate',
  last_completed_stage: 'render',
  created_at: '2026-08-20T10:00:00.000Z',
  started_at: '2026-08-20T10:00:01.000Z',
  finished_at: '2026-08-20T10:00:40.000Z',
  has_video: true,
  warnings: ['MUSIC_ENABLED_NO_PATH'],
  review_reasons: ['DURATION_FITTING_EXHAUSTED'],
};

describe('shorts-api mapper', () => {
  it('maps JobResponseDto snake_case to Job camelCase', () => {
    const job = mapJob(jobDto);
    expect(job.jobId).toBe('123e4567-e89b-42d3-a456-426614174000');
    expect(job.executionState).toBe('FINISHED');
    expect(job.pipelineStatus).toBe('REVIEW_REQUIRED');
    expect(job.currentStage).toBe('validate');
    expect(job.lastCompletedStage).toBe('render');
    expect(job.createdAt).toBe('2026-08-20T10:00:00.000Z');
    expect(job.startedAt).toBe('2026-08-20T10:00:01.000Z');
    expect(job.finishedAt).toBe('2026-08-20T10:00:40.000Z');
    expect(job.hasVideo).toBe(true);
    expect(job.warnings).toEqual(['MUSIC_ENABLED_NO_PATH']);
    expect(job.reviewReasons).toEqual(['DURATION_FITTING_EXHAUSTED']);
  });

  it('maps a JobResponseDto with nulls and missing arrays safely', () => {
    const job = mapJob({
      job_id: 'job-x',
      execution_state: 'QUEUED',
      pipeline_status: null,
      current_stage: null,
      last_completed_stage: null,
      created_at: null,
      started_at: null,
      finished_at: null,
      has_video: false,
      warnings: [],
      review_reasons: [],
    });
    expect(job.executionState).toBe('QUEUED');
    expect(job.pipelineStatus).toBeNull();
    expect(job.hasVideo).toBe(false);
    expect(job.warnings).toEqual([]);
    expect(job.reviewReasons).toEqual([]);
  });

  it('maps CapabilitiesDto to Capabilities application model', () => {
    const dto: CapabilitiesDto = {
      visual_modes: ['AUTO', 'MIXED'],
      media_preferences: ['VIDEO_PREFERRED'],
      asset_preferences: ['photograph'],
      providers: [
        {
          id: 'pexels',
          source_type: 'STOCK',
          query_strategy: 'SEARCH',
          runtime_status: 'AVAILABLE',
          requires_api_key: true,
        },
      ],
      duration: {
        presets: [{ id: 'quick_30', target_sec: 30 }],
        min_sec: 20,
        max_sec: 300,
        default: 'quick_30',
      },
      tts_providers: [{ id: 'edge_tts', default: true, available: true }],
      voices: { note: 'default only', default: 'es-ES-AlvaroNeural', elevenlabs_from_env: false },
    };

    const capabilities = mapCapabilities(dto);

    expect(capabilities.visualModes).toEqual(['AUTO', 'MIXED']);
    expect(capabilities.mediaPreferences).toEqual(['VIDEO_PREFERRED']);
    expect(capabilities.assetPreferences).toEqual(['photograph']);
    expect(capabilities.providers).toEqual([
      {
        id: 'pexels',
        sourceType: 'STOCK',
        queryStrategy: 'SEARCH',
        runtimeStatus: 'AVAILABLE',
        requiresApiKey: true,
      },
    ]);
    expect(capabilities.duration).toEqual({
      presets: [{ id: 'quick_30', targetSec: 30 }],
      minSec: 20,
      maxSec: 300,
      default: 'quick_30',
    });
    expect(capabilities.ttsProviders).toEqual([{ id: 'edge_tts', isDefault: true, available: true }]);
    expect(capabilities.voices).toEqual({
      note: 'default only',
      default: 'es-ES-AlvaroNeural',
      elevenlabsFromEnv: false,
    });
  });

  it('maps a GenerationCommand to a create request, dropping empty fields', () => {
    const request = mapCreateCommandToRequest({
      topic: '  Los delfines  ',
      durationPreset: 'quick_30',
      visualMode: 'AUTO',
      assetProviders: ['pexels', 'wikimedia_commons'],
      ttsProvider: null,
      voice: '',
      durationSeconds: null,
    });

    expect(request).toEqual({
      topic: 'Los delfines',
      duration_preset: 'quick_30',
      visual_mode: 'AUTO',
      asset_providers: ['pexels', 'wikimedia_commons'],
    });
  });

  it('maps a GenerationCommand with seconds duration', () => {
    const request = mapCreateCommandToRequest({ topic: 'x', durationSeconds: 45 });
    expect(request.duration_seconds).toBe(45);
    expect(request.duration_preset).toBeUndefined();
  });

  it('omits null assetProviders and voice', () => {
    const request = mapCreateCommandToRequest({ topic: 'x', assetProviders: null, voice: null });
    expect(request.asset_providers).toBeUndefined();
    expect(request.voice).toBeUndefined();
  });
});

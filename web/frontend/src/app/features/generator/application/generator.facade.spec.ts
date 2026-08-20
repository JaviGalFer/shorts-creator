import { Injector } from '@angular/core';
import { Subject, of, throwError } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ShortsApiClient } from '../data-access/shorts-api.client';
import type { CapabilitiesDto, JobResponseDto } from '../data-access/shorts-api.dto';
import { GeneratorFacade } from './generator.facade';

function jobDto(overrides: Partial<JobResponseDto> = {}): JobResponseDto {
  return {
    job_id: 'job-1',
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
    ...overrides,
  };
}

const capabilitiesDto: CapabilitiesDto = {
  visual_modes: ['AUTO', 'MIXED'],
  media_preferences: ['VIDEO_PREFERRED'],
  asset_preferences: ['photograph'],
  providers: [],
  duration: { presets: [{ id: 'quick_30', target_sec: 30 }], min_sec: 20, max_sec: 300, default: 'quick_30' },
  tts_providers: [{ id: 'edge_tts', default: true, available: true }],
  voices: { note: '', default: 'es-ES-AlvaroNeural', elevenlabs_from_env: false },
};

function createHarness() {
  const client = {
    getCapabilities: vi.fn(),
    createJob: vi.fn(),
    getJob: vi.fn(),
    listJobs: vi.fn(),
    videoUrl: (id: string) => `/api/v1/jobs/${id}/video`,
    downloadUrl: (id: string) => `/api/v1/jobs/${id}/download`,
  };

  const injector = Injector.create({
    providers: [
      { provide: ShortsApiClient, useValue: client as unknown as ShortsApiClient },
      GeneratorFacade,
    ],
    name: 'GeneratorFacadeTest',
  });

  const facade = injector.get(GeneratorFacade);
  return { client, injector, facade };
}

describe('GeneratorFacade', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads capabilities from the API', () => {
    const { client, facade } = createHarness();
    client.getCapabilities.mockReturnValue(of(capabilitiesDto));

    facade.initialize();

    expect(client.getCapabilities).toHaveBeenCalledTimes(1);
    expect(facade.capabilities()?.visualModes).toEqual(['AUTO', 'MIXED']);
    expect(facade.capabilities()?.duration.default).toBe('quick_30');
    expect(facade.error()).toBeNull();
  });

  it('create job maps the command and transitions state', () => {
    const { client, facade } = createHarness();
    const createSubject = new Subject<JobResponseDto>();
    client.createJob.mockReturnValue(createSubject);
    client.getJob.mockReturnValue(of(jobDto({ execution_state: 'FINISHED' })));

    facade.generate({ topic: 'Delfines', durationPreset: 'quick_30' });

    expect(facade.creatingJob()).toBe(true);
    expect(facade.currentJob()).toBeNull();
    expect(client.createJob).toHaveBeenCalledWith({ topic: 'Delfines', duration_preset: 'quick_30' });

    createSubject.next(jobDto({ job_id: 'job-9' }));
    createSubject.complete();

    expect(facade.creatingJob()).toBe(false);
    expect(facade.currentJob()?.jobId).toBe('job-9');
    facade.stopPolling();
  });

  it('create job surfaces a sanitized error', () => {
    const { client, facade } = createHarness();
    client.createJob.mockReturnValue(
      throwError(() => ({ code: 'JOB_EXECUTION_BUSY', message: 'Busy.', status: 409 })),
    );

    facade.generate({ topic: 'X' });

    expect(facade.creatingJob()).toBe(false);
    expect(facade.currentJob()).toBeNull();
    expect(facade.error()).toEqual({ code: 'JOB_EXECUTION_BUSY', message: 'Busy.', status: 409 });
  });

  it('polls through QUEUED -> RUNNING -> FINISHED', async () => {
    const { client, facade } = createHarness();
    client.getJob
      .mockReturnValueOnce(of(jobDto({ execution_state: 'QUEUED' })))
      .mockReturnValueOnce(of(jobDto({ execution_state: 'RUNNING' })))
      .mockReturnValueOnce(of(jobDto({ execution_state: 'FINISHED' })));

    facade.beginPolling('job-1');
    expect(facade.polling()).toBe(true);

    await vi.advanceTimersByTimeAsync(1);
    expect(facade.currentJob()?.executionState).toBe('QUEUED');
    expect(facade.polling()).toBe(true);

    await vi.advanceTimersByTimeAsync(1000);
    expect(facade.currentJob()?.executionState).toBe('RUNNING');

    await vi.advanceTimersByTimeAsync(1000);
    expect(facade.currentJob()?.executionState).toBe('FINISHED');
    expect(facade.polling()).toBe(false);
    expect(client.getJob).toHaveBeenCalledTimes(3);
  });

  it.each(['FINISHED', 'FAILED', 'INTERRUPTED'] as const)('stops after %s', async (state) => {
    const { client, facade } = createHarness();
    client.getJob.mockReturnValue(of(jobDto({ execution_state: state })));

    facade.beginPolling('job-1');
    expect(facade.polling()).toBe(true);

    await vi.advanceTimersByTimeAsync(1);

    expect(facade.currentJob()?.executionState).toBe(state);
    expect(facade.polling()).toBe(false);
    expect(client.getJob).toHaveBeenCalledTimes(1);
  });

  it('does not overlap polling requests', async () => {
    const { client, facade } = createHarness();
    const pending = new Subject<JobResponseDto>();
    client.getJob.mockReturnValue(pending);

    facade.beginPolling('job-1');

    await vi.advanceTimersByTimeAsync(1);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(1000);

    expect(client.getJob).toHaveBeenCalledTimes(1);
    facade.stopPolling();
  });

  it('stops polling when the owning feature is destroyed', async () => {
    const { client, facade, injector } = createHarness();
    client.getJob.mockReturnValue(of(jobDto({ execution_state: 'QUEUED' })));

    facade.beginPolling('job-1');
    await vi.advanceTimersByTimeAsync(1);
    expect(client.getJob).toHaveBeenCalledTimes(1);

    injector.destroy();

    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(1000);
    expect(client.getJob).toHaveBeenCalledTimes(1);
  });

  it('exposes video and download URLs for a job with video', () => {
    const { client, facade } = createHarness();
    const createSubject = new Subject<JobResponseDto>();
    client.createJob.mockReturnValue(createSubject);
    client.getJob.mockReturnValue(of(jobDto({ execution_state: 'FINISHED' })));

    facade.generate({ topic: 'X' });
    createSubject.next(jobDto({ job_id: 'job-9', has_video: true }));
    createSubject.complete();

    expect(facade.videoUrl()).toBe('/api/v1/jobs/job-9/video');
    expect(facade.downloadUrl()).toBe('/api/v1/jobs/job-9/download');
    facade.stopPolling();
  });

  it('exposes no URLs when the job has no video', () => {
    const { client, facade } = createHarness();
    const createSubject = new Subject<JobResponseDto>();
    client.createJob.mockReturnValue(createSubject);
    client.getJob.mockReturnValue(of(jobDto({ execution_state: 'FINISHED' })));

    facade.generate({ topic: 'X' });
    createSubject.next(jobDto({ job_id: 'job-9', has_video: false }));
    createSubject.complete();

    expect(facade.videoUrl()).toBeNull();
    expect(facade.downloadUrl()).toBeNull();
    facade.stopPolling();
  });
});

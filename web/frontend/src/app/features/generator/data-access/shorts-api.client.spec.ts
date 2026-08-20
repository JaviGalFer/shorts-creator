import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ApiError } from './api-error.mapper';
import { ShortsApiClient } from './shorts-api.client';
import type { CapabilitiesDto, JobResponseDto } from './shorts-api.dto';

describe('ShortsApiClient', () => {
  let client: ShortsApiClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    client = TestBed.inject(ShortsApiClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('GET capabilities', () => {
    const dto: CapabilitiesDto = {
      visual_modes: ['AUTO'],
      media_preferences: [],
      asset_preferences: [],
      providers: [],
      duration: { presets: [], min_sec: 20, max_sec: 300, default: 'quick_30' },
      tts_providers: [],
      voices: { note: '', default: 'es-ES-AlvaroNeural', elevenlabs_from_env: false },
    };

    client.getCapabilities().subscribe((res) => expect(res).toEqual(dto));

    const req = httpMock.expectOne('/api/v1/capabilities');
    expect(req.request.method).toBe('GET');
    req.flush(dto);
  });

  it('POST create job with request body', () => {
    const request = { topic: 'Delfines', duration_preset: 'quick_30' };
    const response: JobResponseDto = {
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
    };

    client.createJob(request).subscribe((res) => expect(res.job_id).toBe('job-1'));

    const req = httpMock.expectOne('/api/v1/jobs');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(request);
    req.flush(response);
  });

  it('GET job detail by id', () => {
    const jobId = '123e4567-e89b-42d3-a456-426614174000';
    client.getJob(jobId).subscribe((res) => expect(res.execution_state).toBe('RUNNING'));

    const req = httpMock.expectOne(`/api/v1/jobs/${jobId}`);
    expect(req.request.method).toBe('GET');
    req.flush({ ...emptyJob(), execution_state: 'RUNNING' });
  });

  it('GET list jobs', () => {
    client.listJobs().subscribe((res) => expect(res.jobs).toEqual([]));
    const req = httpMock.expectOne('/api/v1/jobs');
    expect(req.request.method).toBe('GET');
    req.flush({ jobs: [] });
  });

  it('builds safe video and download URLs from job id only', () => {
    const jobId = '123e4567-e89b-42d3-a456-426614174000';
    expect(client.videoUrl(jobId)).toBe(`/api/v1/jobs/${jobId}/video`);
    expect(client.downloadUrl(jobId)).toBe(`/api/v1/jobs/${jobId}/download`);
  });

  it('converts an HTTP error response into a safe ApiError', () => {
    const onError = vi.fn();
    client.getJob('123e4567-e89b-42d3-a456-426614174000').subscribe({ error: onError });

    const req = httpMock.expectOne('/api/v1/jobs/123e4567-e89b-42d3-a456-426614174000');
    req.flush(
      { error: { code: 'JOB_NOT_FOUND', message: 'Job not found.' } },
      { status: 404, statusText: 'Not Found' },
    );

    const received = onError.mock.calls[0][0] as ApiError;
    expect(received.code).toBe('JOB_NOT_FOUND');
    expect(received.message).toBe('Job not found.');
    expect(received.status).toBe(404);
  });
});

function emptyJob(): JobResponseDto {
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
  };
}

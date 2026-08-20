import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { JobResult } from './job-result';
import type { Job } from '../model/job.model';

describe('JobResult', () => {
  let component: JobResult;
  let fixture: ComponentFixture<JobResult>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [JobResult],
    }).compileComponents();

    fixture = TestBed.createComponent(JobResult);
    component = fixture.componentInstance;
  });

  function job(overrides: Partial<Job> = {}): Job {
    return {
      jobId: 'job-1',
      executionState: 'FINISHED',
      pipelineStatus: null,
      currentStage: null,
      lastCompletedStage: null,
      createdAt: null,
      startedAt: null,
      finishedAt: null,
      hasVideo: false,
      warnings: [],
      reviewReasons: [],
      ...overrides,
    };
  }

  it('presents REVIEW_REQUIRED outcome with reasons', () => {
    component.job = job({
      pipelineStatus: 'REVIEW_REQUIRED',
      reviewReasons: ['DURATION_FITTING_EXHAUSTED'],
    });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Revisión requerida');
    expect(text).toContain('DURATION_FITTING_EXHAUSTED');
  });

  it('presents ASSETS_PARTIAL outcome with warnings', () => {
    component.job = job({
      pipelineStatus: 'ASSETS_PARTIAL',
      warnings: ['MUSIC_ENABLED_NO_PATH'],
    });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Assets parciales');
    expect(text).toContain('MUSIC_ENABLED_NO_PATH');
  });

  it('presents a failed outcome', () => {
    component.job = job({ executionState: 'FAILED' });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent as string).toContain('Generación fallida');
  });

  it('presents an interrupted outcome', () => {
    component.job = job({ executionState: 'INTERRUPTED' });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent as string).toContain('Interrumpido');
  });

  it('renders a video preview and download link from safe URLs', () => {
    component.job = job({ executionState: 'FINISHED', pipelineStatus: 'VALIDATED', hasVideo: true });
    component.videoUrl = '/api/v1/jobs/job-1/video';
    component.downloadUrl = '/api/v1/jobs/job-1/download';
    fixture.detectChanges();

    const video = fixture.nativeElement.querySelector('video') as HTMLVideoElement;
    const download = fixture.nativeElement.querySelector('a.job-result__download') as HTMLAnchorElement;

    expect(video?.getAttribute('src')).toBe('/api/v1/jobs/job-1/video');
    expect(download?.getAttribute('href')).toBe('/api/v1/jobs/job-1/download');
  });

  it('renders no media when there is no video URL', () => {
    component.job = job({ executionState: 'FINISHED', pipelineStatus: 'VALIDATED', hasVideo: false });
    component.videoUrl = null;
    component.downloadUrl = null;
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('video')).toBeNull();
    expect(fixture.nativeElement.querySelector('a.job-result__download')).toBeNull();
  });
});

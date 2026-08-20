import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { JobProgress } from './job-progress';
import type { Job } from '../model/job.model';

describe('JobProgress', () => {
  let component: JobProgress;
  let fixture: ComponentFixture<JobProgress>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [JobProgress],
    }).compileComponents();

    fixture = TestBed.createComponent(JobProgress);
    component = fixture.componentInstance;
  });

  function job(overrides: Partial<Job> = {}): Job {
    return {
      jobId: 'job-1',
      executionState: 'RUNNING',
      pipelineStatus: null,
      currentStage: 'render',
      lastCompletedStage: 'audio',
      createdAt: null,
      startedAt: null,
      finishedAt: null,
      hasVideo: false,
      warnings: [],
      reviewReasons: [],
      ...overrides,
    };
  }

  it('renders execution state and stages', () => {
    component.job = job({ executionState: 'RUNNING', currentStage: 'render', lastCompletedStage: 'audio' });
    component.polling = true;
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('RUNNING');
    expect(text).toContain('render');
    expect(text).toContain('audio');
  });

  it('renders sanitized warnings and review reasons', () => {
    component.job = job({
      warnings: ['MUSIC_ENABLED_NO_PATH'],
      reviewReasons: ['DURATION_FITTING_EXHAUSTED'],
    });
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('MUSIC_ENABLED_NO_PATH');
    expect(text).toContain('DURATION_FITTING_EXHAUSTED');
  });

  it('renders nothing when there is no job', () => {
    component.job = null;
    fixture.detectChanges();

    expect((fixture.nativeElement.textContent as string).trim()).toBe('');
  });
});

import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription, catchError, exhaustMap, map, takeWhile, throwError, timer } from 'rxjs';

import { mapHttpError, type ApiError } from '../data-access/api-error.mapper';
import { ShortsApiClient } from '../data-access/shorts-api.client';
import { mapCapabilities, mapCreateCommandToRequest, mapJob } from '../data-access/shorts-api.mapper';
import type { Capabilities } from '../model/capabilities.model';
import type { GenerationCommand } from '../model/generation-command.model';
import { isTerminalExecutionState, type Job } from '../model/job.model';

const POLL_INTERVAL_MS = 1000;

@Injectable()
export class GeneratorFacade {
  private readonly client = inject(ShortsApiClient);
  private readonly destroyRef = inject(DestroyRef);

  private readonly capabilitiesSignal = signal<Capabilities | null>(null);
  private readonly currentJobSignal = signal<Job | null>(null);
  private readonly creatingJobSignal = signal(false);
  private readonly pollingSignal = signal(false);
  private readonly errorSignal = signal<ApiError | null>(null);

  private pollingSubscription: Subscription | null = null;

  readonly capabilities = this.capabilitiesSignal.asReadonly();
  readonly currentJob = this.currentJobSignal.asReadonly();
  readonly creatingJob = this.creatingJobSignal.asReadonly();
  readonly polling = this.pollingSignal.asReadonly();
  readonly error = this.errorSignal.asReadonly();

  readonly isTerminal = computed(() => {
    const job = this.currentJobSignal();
    return job !== null && isTerminalExecutionState(job.executionState);
  });

  readonly videoUrl = computed(() => {
    const job = this.currentJobSignal();
    return job !== null && job.hasVideo ? this.client.videoUrl(job.jobId) : null;
  });

  readonly downloadUrl = computed(() => {
    const job = this.currentJobSignal();
    return job !== null && job.hasVideo ? this.client.downloadUrl(job.jobId) : null;
  });

  initialize(): void {
    this.errorSignal.set(null);
    this.client.getCapabilities().subscribe({
      next: (dto) => this.capabilitiesSignal.set(mapCapabilities(dto)),
      error: (error: unknown) => this.errorSignal.set(mapHttpError(error)),
    });
  }

  generate(command: GenerationCommand): void {
    this.stopPolling();
    this.errorSignal.set(null);
    this.currentJobSignal.set(null);
    this.creatingJobSignal.set(true);

    this.client.createJob(mapCreateCommandToRequest(command)).subscribe({
      next: (dto) => {
        const job = mapJob(dto);
        this.currentJobSignal.set(job);
        this.creatingJobSignal.set(false);
        this.beginPolling(job.jobId);
      },
      error: (error: unknown) => {
        this.creatingJobSignal.set(false);
        this.errorSignal.set(mapHttpError(error));
      },
    });
  }

  refreshJob(): void {
    const job = this.currentJobSignal();
    if (job === null) {
      return;
    }
    this.client.getJob(job.jobId).subscribe({
      next: (dto) => this.currentJobSignal.set(mapJob(dto)),
      error: (error: unknown) => this.errorSignal.set(mapHttpError(error)),
    });
  }

  beginPolling(jobId: string): void {
    this.stopPolling();
    this.pollingSignal.set(true);

    this.pollingSubscription = timer(0, POLL_INTERVAL_MS)
      .pipe(
        exhaustMap(() =>
          this.client.getJob(jobId).pipe(
            map((dto) => mapJob(dto)),
            catchError((error: unknown) => throwError(() => mapHttpError(error))),
          ),
        ),
        takeWhile((job) => !isTerminalExecutionState(job.executionState), true),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (job) => this.currentJobSignal.set(job),
        complete: () => this.pollingSignal.set(false),
        error: (error: unknown) => {
          this.pollingSignal.set(false);
          this.errorSignal.set(mapHttpError(error));
        },
      });
  }

  stopPolling(): void {
    this.pollingSubscription?.unsubscribe();
    this.pollingSubscription = null;
    this.pollingSignal.set(false);
  }
}

import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import type { Job } from '../model/job.model';

@Component({
  selector: 'app-job-result',
  templateUrl: './job-result.html',
  styleUrl: './job-result.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobResult {
  @Input() job: Job | null = null;
  @Input() videoUrl: string | null = null;
  @Input() downloadUrl: string | null = null;

  get isReviewRequired(): boolean {
    return this.job?.pipelineStatus === 'REVIEW_REQUIRED';
  }

  get isAssetsPartial(): boolean {
    return this.job?.pipelineStatus === 'ASSETS_PARTIAL';
  }

  get isFailed(): boolean {
    return this.job?.executionState === 'FAILED';
  }

  get isInterrupted(): boolean {
    return this.job?.executionState === 'INTERRUPTED';
  }
}

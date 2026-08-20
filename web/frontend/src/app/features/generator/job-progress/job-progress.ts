import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import type { Job } from '../model/job.model';

@Component({
  selector: 'app-job-progress',
  templateUrl: './job-progress.html',
  styleUrl: './job-progress.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JobProgress {
  @Input() job: Job | null = null;
  @Input() polling = false;
}

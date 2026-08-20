import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { GeneratorFacade } from '../application/generator.facade';
import { GeneratorForm } from '../generator-form/generator-form';
import { JobProgress } from '../job-progress/job-progress';
import { JobResult } from '../job-result/job-result';
import type { GenerationCommand } from '../model/generation-command.model';

@Component({
  selector: 'app-generator-page',
  imports: [GeneratorForm, JobProgress, JobResult],
  providers: [GeneratorFacade],
  templateUrl: './generator-page.html',
  styleUrl: './generator-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GeneratorPage implements OnInit {
  readonly facade = inject(GeneratorFacade);

  ngOnInit(): void {
    this.facade.initialize();
  }

  onGenerate(command: GenerationCommand): void {
    this.facade.generate(command);
  }
}

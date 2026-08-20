import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
  inject,
} from '@angular/core';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import type { Capabilities } from '../model/capabilities.model';
import type { GenerationCommand } from '../model/generation-command.model';

function durationExclusiveValidator(group: AbstractControl): ValidationErrors | null {
  const preset = group.get('durationPreset')?.value;
  const seconds = group.get('durationSeconds')?.value;
  const hasPreset = preset != null && preset !== '';
  const hasSeconds = seconds != null && seconds !== '';
  if (hasPreset && hasSeconds) {
    return { durationExclusive: true };
  }
  return null;
}

@Component({
  selector: 'app-generator-form',
  imports: [ReactiveFormsModule],
  templateUrl: './generator-form.html',
  styleUrl: './generator-form.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GeneratorForm {
  private readonly fb = inject(FormBuilder);

  @Input() capabilities: Capabilities | null = null;
  @Input() busy = false;
  @Output() generate = new EventEmitter<GenerationCommand>();

  readonly form = this.fb.group(
    {
      topic: this.fb.control<string | null>('', [Validators.required, Validators.maxLength(500)]),
      durationPreset: this.fb.control<string | null>(null),
      durationSeconds: this.fb.control<number | null>(null, [Validators.min(1)]),
      ttsProvider: this.fb.control<string | null>(null),
      voice: this.fb.control<string | null>('', [Validators.maxLength(200)]),
      visualMode: this.fb.control<string | null>(null),
      assetProviders: this.fb.control<string[]>([]),
    },
    { validators: durationExclusiveValidator },
  );

  get presets() {
    return this.capabilities?.duration.presets ?? [];
  }

  get visualModes() {
    return this.capabilities?.visualModes ?? [];
  }

  get providers() {
    return this.capabilities?.providers ?? [];
  }

  get ttsProviders() {
    return this.capabilities?.ttsProviders ?? [];
  }

  get minSec() {
    return this.capabilities?.duration.minSec ?? 1;
  }

  get maxSec() {
    return this.capabilities?.duration.maxSec ?? 300;
  }

  get hasDurationConflict() {
    return this.form.errors?.['durationExclusive'] === true;
  }

  isProviderSelected(id: string): boolean {
    return (this.form.controls.assetProviders.value ?? []).includes(id);
  }

  toggleProvider(id: string, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    const current = this.form.controls.assetProviders.value ?? [];
    const next = checked ? [...current, id] : current.filter((provider) => provider !== id);
    this.form.controls.assetProviders.setValue(next);
    this.form.controls.assetProviders.markAsTouched();
  }

  buildCommand(): GenerationCommand {
    const value = this.form.getRawValue();
    const command: GenerationCommand = { topic: (value.topic ?? '').trim() };
    if (value.durationPreset != null && value.durationPreset !== '') {
      command.durationPreset = value.durationPreset;
    }
    if (value.durationSeconds != null) {
      command.durationSeconds = value.durationSeconds;
    }
    if (value.ttsProvider != null && value.ttsProvider !== '') {
      command.ttsProvider = value.ttsProvider;
    }
    if (value.voice != null && value.voice.trim() !== '') {
      command.voice = value.voice.trim();
    }
    if (value.visualMode != null && value.visualMode !== '') {
      command.visualMode = value.visualMode;
    }
    if (value.assetProviders != null && value.assetProviders.length > 0) {
      command.assetProviders = [...value.assetProviders];
    }
    return command;
  }

  submit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      return;
    }
    this.generate.emit(this.buildCommand());
  }
}

import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
  inject,
} from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import type { Capabilities, ProviderOption } from '../model/capabilities.model';
import type { GenerationCommand } from '../model/generation-command.model';

/** Visual modes that only accept video segments — no image fallback exists. */
const VIDEO_ONLY_MODES = new Set(['VIDEOS_ONLY']);

const PROVIDER_LABELS: Record<string, string> = {
  wikimedia_commons: 'Wikimedia Commons',
  pixabay: 'Pixabay',
  pexels: 'Pexels',
  freeai: 'FreeAI',
  pollinations: 'Pollinations',
};

const MEDIA_KIND_LABELS: Record<string, string> = {
  IMAGE: 'fotos',
  VIDEO: 'vídeo',
};

const VISUAL_MODE_INFO: Record<string, { label: string; help: string }> = {
  AUTO: {
    label: 'Automático',
    help: 'La IA elige imagen o vídeo en cada escena según lo que encuentre.',
  },
  IMAGES_ONLY: {
    label: 'Solo imágenes',
    help: 'Usa únicamente fotografías o ilustraciones fijas.',
  },
  VIDEOS_ONLY: {
    label: 'Solo vídeo',
    help: 'Usa únicamente clips de vídeo. Requiere marcar un proveedor de vídeo (Pexels) más abajo.',
  },
  MIXED: {
    label: 'Mixto',
    help: 'Combina imágenes y vídeo, alternando entre escenas.',
  },
};

const TTS_PROVIDER_LABELS: Record<string, string> = {
  edge_tts: 'Edge TTS (gratis)',
  elevenlabs: 'ElevenLabs',
};

const DURATION_PRESET_LABELS: Record<string, string> = {
  quick_30: 'Rápido — unos 30s',
  standard_45: 'Estándar — unos 45s',
  deep_60: 'Detallado — unos 60s',
};

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
export class GeneratorForm implements OnChanges {
  private readonly fb = inject(FormBuilder);

  @Input() capabilities: Capabilities | null = null;
  @Input() busy = false;
  @Output() generate = new EventEmitter<GenerationCommand>();

  /**
   * Blocks submission when the chosen visual mode has no image fallback
   * (VIDEOS_ONLY) and no video-capable provider (Pexels) is selected.
   * Selecting the mode without opting in previously reached the pipeline
   * and failed every segment as UNROUTABLE — this catches it in the form.
   */
  private readonly videoProviderValidator = (group: AbstractControl): ValidationErrors | null => {
    const visualMode = group.get('visualMode')?.value;
    if (!visualMode || !VIDEO_ONLY_MODES.has(visualMode)) {
      return null;
    }
    const videoCapable = this.videoCapableProviders;
    if (videoCapable.length === 0) {
      // Capabilities not loaded yet — nothing to validate against.
      return null;
    }
    const selected: string[] = group.get('assetProviders')?.value ?? [];
    const hasVideoProvider = selected.some((p) => videoCapable.includes(p));
    return hasVideoProvider ? null : { videoProviderRequired: true };
  };

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
    { validators: [durationExclusiveValidator, this.videoProviderValidator] },
  );

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['capabilities']) {
      // Video-provider availability depends on capabilities, not on any
      // form control value, so it never triggers revalidation on its own.
      this.form.updateValueAndValidity({ onlySelf: true, emitEvent: false });
    }
  }

  get presets() {
    return this.capabilities?.duration.presets ?? [];
  }

  get visualModes() {
    return this.capabilities?.visualModes ?? [];
  }

  /** Provider capabilities grouped by plain provider name (photo + video merged). */
  get providerGroups(): ProviderOption[] {
    const list = this.capabilities?.providers ?? [];
    const byProvider = new Map<string, ProviderOption>();
    for (const cap of list) {
      const existing = byProvider.get(cap.provider);
      if (existing) {
        if (!existing.mediaKinds.includes(cap.mediaKind)) {
          existing.mediaKinds.push(cap.mediaKind);
        }
        existing.requiresApiKey = existing.requiresApiKey || cap.requiresApiKey;
        existing.available = existing.available || cap.runtimeStatus === 'AVAILABLE';
      } else {
        byProvider.set(cap.provider, {
          provider: cap.provider,
          label: PROVIDER_LABELS[cap.provider] ?? cap.provider,
          mediaKinds: [cap.mediaKind],
          requiresApiKey: cap.requiresApiKey,
          available: cap.runtimeStatus === 'AVAILABLE',
        });
      }
    }
    return Array.from(byProvider.values());
  }

  private get videoCapableProviders(): string[] {
    return Array.from(
      new Set((this.capabilities?.providers ?? []).filter((p) => p.mediaKind === 'VIDEO').map((p) => p.provider)),
    );
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

  get hasVideoProviderConflict() {
    return this.form.errors?.['videoProviderRequired'] === true;
  }

  /** Only surface the video-provider error after the person actually engaged with these fields. */
  get showVideoProviderConflict() {
    return (
      this.hasVideoProviderConflict &&
      (this.form.controls.visualMode.dirty || this.form.controls.assetProviders.touched)
    );
  }

  get visualModeHelp(): string {
    const mode = this.form.controls.visualMode.value;
    if (!mode) {
      return 'Por defecto usa imágenes de Wikimedia Commons y Pixabay.';
    }
    return VISUAL_MODE_INFO[mode]?.help ?? '';
  }

  visualModeLabel(mode: string): string {
    return VISUAL_MODE_INFO[mode]?.label ?? mode;
  }

  ttsProviderLabel(id: string): string {
    return TTS_PROVIDER_LABELS[id] ?? id;
  }

  presetLabel(preset: { id: string; targetSec: number }): string {
    const known = DURATION_PRESET_LABELS[preset.id];
    return known ? `${known} (${preset.targetSec}s)` : `${preset.id} (${preset.targetSec}s)`;
  }

  mediaKindsLabel(kinds: string[]): string {
    return kinds
      .map((k) => MEDIA_KIND_LABELS[k] ?? k.toLowerCase())
      .sort()
      .join(' y ');
  }

  isProviderSelected(provider: string): boolean {
    return (this.form.controls.assetProviders.value ?? []).includes(provider);
  }

  toggleProvider(provider: string, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    const current = this.form.controls.assetProviders.value ?? [];
    const next = checked ? [...current, provider] : current.filter((p) => p !== provider);
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

import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { GeneratorForm } from './generator-form';
import type { Capabilities } from '../model/capabilities.model';

const capabilities: Capabilities = {
  visualModes: ['AUTO', 'IMAGES_ONLY', 'VIDEOS_ONLY', 'MIXED'],
  mediaPreferences: [],
  assetPreferences: [],
  providers: [
    {
      id: 'wikimedia_commons.image.stock',
      provider: 'wikimedia_commons',
      mediaKind: 'IMAGE',
      sourceType: 'STOCK',
      queryStrategy: 'SEARCH',
      runtimeStatus: 'AVAILABLE',
      requiresApiKey: false,
    },
    {
      id: 'pexels.photos.stock',
      provider: 'pexels',
      mediaKind: 'IMAGE',
      sourceType: 'STOCK',
      queryStrategy: 'SEARCH',
      runtimeStatus: 'AVAILABLE',
      requiresApiKey: true,
    },
    {
      id: 'pexels.video.stock',
      provider: 'pexels',
      mediaKind: 'VIDEO',
      sourceType: 'STOCK',
      queryStrategy: 'SEARCH',
      runtimeStatus: 'AVAILABLE',
      requiresApiKey: true,
    },
  ],
  duration: {
    presets: [
      { id: 'quick_30', targetSec: 30 },
      { id: 'deep_60', targetSec: 60 },
    ],
    minSec: 20,
    maxSec: 300,
    default: 'quick_30',
  },
  ttsProviders: [{ id: 'edge_tts', isDefault: true, available: true }],
  voices: { note: '', default: 'es-ES-AlvaroNeural', elevenlabsFromEnv: false },
};

describe('GeneratorForm', () => {
  let component: GeneratorForm;
  let fixture: ComponentFixture<GeneratorForm>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GeneratorForm],
    }).compileComponents();

    fixture = TestBed.createComponent(GeneratorForm);
    component = fixture.componentInstance;
    component.capabilities = capabilities;
    component.ngOnChanges({ capabilities: {} as never });
    fixture.detectChanges();
  });

  it('maps the reactive form into a generation command', () => {
    component.form.patchValue({
      topic: '  Los delfines  ',
      durationPreset: 'quick_30',
      ttsProvider: 'edge_tts',
      voice: '  es-ES-AlvaroNeural  ',
      visualMode: 'AUTO',
      assetProviders: ['pexels'],
    });

    expect(component.buildCommand()).toEqual({
      topic: 'Los delfines',
      durationPreset: 'quick_30',
      ttsProvider: 'edge_tts',
      voice: 'es-ES-AlvaroNeural',
      visualMode: 'AUTO',
      assetProviders: ['pexels'],
    });
  });

  it('maps a seconds-based duration and drops empty optional fields', () => {
    component.form.patchValue({ topic: 'Delfines', durationSeconds: 45 });

    const command = component.buildCommand();

    expect(command.topic).toBe('Delfines');
    expect(command.durationSeconds).toBe(45);
    expect(command.durationPreset).toBeUndefined();
    expect(command.ttsProvider).toBeUndefined();
    expect(command.voice).toBeUndefined();
    expect(command.visualMode).toBeUndefined();
    expect(command.assetProviders).toBeUndefined();
  });

  it('rejects a form with both a preset and seconds', () => {
    component.form.patchValue({ topic: 'Delfines', durationPreset: 'quick_30', durationSeconds: 30 });

    expect(component.form.invalid).toBe(true);
    expect(component.hasDurationConflict).toBe(true);
  });

  it('requires a topic', () => {
    component.form.patchValue({ topic: '' });
    expect(component.form.invalid).toBe(true);
    expect(component.form.controls.topic.hasError('required')).toBe(true);
  });

  it('emits the command on submit when valid', () => {
    const emitted = vi.fn();
    component.generate.subscribe(emitted);

    component.form.patchValue({ topic: 'Delfines', durationPreset: 'quick_30' });
    component.submit();

    expect(emitted).toHaveBeenCalledWith({ topic: 'Delfines', durationPreset: 'quick_30' });
  });

  it('does not emit when the form is invalid', () => {
    const emitted = vi.fn();
    component.generate.subscribe(emitted);

    component.form.patchValue({ topic: '' });
    component.submit();

    expect(emitted).not.toHaveBeenCalled();
  });

  it('toggles asset providers', () => {
    component.toggleProvider('pexels', { target: { checked: true } } as unknown as Event);
    component.toggleProvider('wikimedia_commons', { target: { checked: true } } as unknown as Event);

    expect(component.form.controls.assetProviders.value).toEqual(['pexels', 'wikimedia_commons']);

    component.toggleProvider('pexels', { target: { checked: false } } as unknown as Event);
    expect(component.form.controls.assetProviders.value).toEqual(['wikimedia_commons']);
  });

  it('groups capability rows by plain provider name, merging photo + video', () => {
    const groups = component.providerGroups;

    expect(groups).toHaveLength(2);
    const pexels = groups.find((g) => g.provider === 'pexels');
    expect(pexels).toBeTruthy();
    expect(pexels?.label).toBe('Pexels');
    expect(pexels?.mediaKinds.sort()).toEqual(['IMAGE', 'VIDEO']);
    expect(pexels?.requiresApiKey).toBe(true);

    const wikimedia = groups.find((g) => g.provider === 'wikimedia_commons');
    expect(wikimedia?.label).toBe('Wikimedia Commons');
    expect(wikimedia?.mediaKinds).toEqual(['IMAGE']);
  });

  it('blocks submission for VIDEOS_ONLY without a video-capable provider selected', () => {
    component.form.patchValue({ topic: 'Delfines', visualMode: 'VIDEOS_ONLY' });

    expect(component.form.invalid).toBe(true);
    expect(component.hasVideoProviderConflict).toBe(true);

    const emitted = vi.fn();
    component.generate.subscribe(emitted);
    component.submit();
    expect(emitted).not.toHaveBeenCalled();
  });

  it('allows VIDEOS_ONLY once a video-capable provider (pexels) is selected', () => {
    component.form.patchValue({ topic: 'Delfines', visualMode: 'VIDEOS_ONLY' });
    component.toggleProvider('pexels', { target: { checked: true } } as unknown as Event);

    expect(component.hasVideoProviderConflict).toBe(false);
    expect(component.form.valid).toBe(true);

    const emitted = vi.fn();
    component.generate.subscribe(emitted);
    component.submit();
    expect(emitted).toHaveBeenCalledWith({
      topic: 'Delfines',
      visualMode: 'VIDEOS_ONLY',
      assetProviders: ['pexels'],
    });
  });

  it('does not block AUTO or IMAGES_ONLY without any asset provider selected', () => {
    component.form.patchValue({ topic: 'Delfines', visualMode: 'AUTO' });
    expect(component.hasVideoProviderConflict).toBe(false);

    component.form.patchValue({ visualMode: 'IMAGES_ONLY' });
    expect(component.hasVideoProviderConflict).toBe(false);
  });

  it('only surfaces the video-provider error once the person touched visualMode or providers', () => {
    component.form.patchValue({ topic: 'Delfines', visualMode: 'VIDEOS_ONLY' });
    // patchValue marks the control dirty, matching real select interaction.
    expect(component.showVideoProviderConflict).toBe(true);
  });
});

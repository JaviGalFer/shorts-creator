import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { GeneratorForm } from './generator-form';
import type { Capabilities } from '../model/capabilities.model';

const capabilities: Capabilities = {
  visualModes: ['AUTO', 'MIXED'],
  mediaPreferences: [],
  assetPreferences: [],
  providers: [
    { id: 'pexels', sourceType: 'STOCK', queryStrategy: 'SEARCH', runtimeStatus: 'AVAILABLE', requiresApiKey: true },
    { id: 'wikimedia_commons', sourceType: 'SEARCH', queryStrategy: 'SEARCH', runtimeStatus: 'AVAILABLE', requiresApiKey: false },
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
});

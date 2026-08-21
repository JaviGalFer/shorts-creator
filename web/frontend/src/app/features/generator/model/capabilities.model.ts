export interface ProviderCapability {
  id: string;
  provider: string;
  mediaKind: string;
  sourceType: string;
  queryStrategy: string;
  runtimeStatus: string;
  requiresApiKey: boolean;
}

/**
 * One selectable row in the "Proveedores de assets" form control.
 *
 * A provider (e.g. Pexels) may expose more than one `ProviderCapability`
 * (photo + video). The form lets the user opt in per PROVIDER, not per
 * capability, matching the backend's `request.visuals.sourceProviders`
 * contract — so capabilities are grouped by `provider` before rendering.
 */
export interface ProviderOption {
  provider: string;
  label: string;
  mediaKinds: string[];
  requiresApiKey: boolean;
  available: boolean;
}

export interface DurationPreset {
  id: string;
  targetSec: number;
}

export interface DurationCapabilities {
  presets: DurationPreset[];
  minSec: number;
  maxSec: number;
  default: string;
}

export interface TtsProviderCapability {
  id: string;
  isDefault: boolean;
  available: boolean;
}

export interface VoiceCapabilities {
  note: string;
  default: string;
  elevenlabsFromEnv: boolean;
}

export interface Capabilities {
  visualModes: string[];
  mediaPreferences: string[];
  assetPreferences: string[];
  providers: ProviderCapability[];
  duration: DurationCapabilities;
  ttsProviders: TtsProviderCapability[];
  voices: VoiceCapabilities;
}

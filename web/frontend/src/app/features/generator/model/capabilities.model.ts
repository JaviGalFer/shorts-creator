export interface ProviderCapability {
  id: string;
  sourceType: string;
  queryStrategy: string;
  runtimeStatus: string;
  requiresApiKey: boolean;
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

export interface GenerationCommand {
  topic: string;
  durationPreset?: string | null;
  durationSeconds?: number | null;
  ttsProvider?: string | null;
  voice?: string | null;
  visualMode?: string | null;
  assetProviders?: string[] | null;
}

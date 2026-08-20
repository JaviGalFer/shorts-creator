export type ExecutionState =
  | 'QUEUED'
  | 'RUNNING'
  | 'FINISHED'
  | 'FAILED'
  | 'INTERRUPTED';

export const TERMINAL_EXECUTION_STATES: readonly ExecutionState[] = [
  'FINISHED',
  'FAILED',
  'INTERRUPTED',
];

export const ACTIVE_EXECUTION_STATES: readonly ExecutionState[] = [
  'QUEUED',
  'RUNNING',
];

export function isTerminalExecutionState(state: ExecutionState): boolean {
  return TERMINAL_EXECUTION_STATES.includes(state);
}

export interface Job {
  jobId: string;
  executionState: ExecutionState;
  pipelineStatus: string | null;
  currentStage: string | null;
  lastCompletedStage: string | null;
  createdAt: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  hasVideo: boolean;
  warnings: string[];
  reviewReasons: string[];
}

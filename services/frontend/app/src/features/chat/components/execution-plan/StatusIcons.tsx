import { Check, Circle, Loader2 } from 'lucide-react';
import type { ExecutionLogEntry } from '../../hooks/useOrchestratorChat';
import type { ExecutionStep } from './types';

export function StepStatusIcon({ status }: { status: ExecutionStep['status'] }) {
  switch (status) {
    case 'completed':
      return (
        <div className="w-4 h-4 rounded-full bg-sk-accent-red flex items-center justify-center">
          <Check className="w-2.5 h-2.5 text-white" strokeWidth={3} />
        </div>
      );
    case 'running':
      return <Loader2 className="w-4 h-4 text-sk-accent-red animate-spin" />;
    case 'error':
      return <Circle className="w-4 h-4 text-red-500" />;
    default:
      return <Circle className="w-4 h-4 text-gray-400" />;
  }
}

export function ExecutionStatusIcon({ status }: { status: ExecutionLogEntry['status'] }) {
  switch (status) {
    case 'completed':
      return (
        <div className="w-4 h-4 rounded-full bg-sk-accent-red flex items-center justify-center">
          <Check className="w-2.5 h-2.5 text-white" strokeWidth={3} />
        </div>
      );
    case 'running':
      return <Loader2 className="w-4 h-4 text-sk-accent-red animate-spin" />;
    case 'error':
      return <Circle className="w-4 h-4 text-red-500" />;
    default:
      return <Circle className="w-4 h-4 text-gray-400" />;
  }
}

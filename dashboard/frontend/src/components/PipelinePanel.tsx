import type { Pipeline } from '../types'

interface Props {
  pipelines: Pipeline[]
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function statusColor(status: string): string {
  if (['pr-created', 'completed', 'pass', 'idle'].includes(status)) return 'text-emerald-400'
  if (['running', 'active'].includes(status)) return 'text-blue-400'
  if (['error', 'failed', 'quality-blocked'].includes(status)) return 'text-red-400'
  if (['no-approved-issues', 'no-issues-found'].includes(status)) return 'text-gray-500'
  return 'text-yellow-400'
}

export function PipelinePanel({ pipelines }: Props) {
  return (
    <div className="space-y-2">
      <h2 className="text-xs font-medium uppercase tracking-widest text-gray-500 mb-3">
        Pipelines
      </h2>
      <div className="grid gap-2">
        {pipelines.map(pipe => (
          <div
            key={pipe.id}
            className="px-4 py-3 rounded-lg bg-surface-raised border border-border-subtle"
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white">{pipe.name}</span>
                <span className="text-[10px] font-mono text-gray-600">{pipe.interval}</span>
              </div>
              <span className={`text-xs font-mono ${statusColor(pipe.status)}`}>
                {pipe.status}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>{pipe.lastResult || 'no data'}</span>
              <span className="font-mono">{timeAgo(pipe.lastRun)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

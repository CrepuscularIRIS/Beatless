import type { Experiment } from '../types'

interface Props {
  experiments: Experiment[]
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    running: 'bg-blue-400/10 text-blue-400',
    paused: 'bg-yellow-400/10 text-yellow-400',
    halted: 'bg-red-400/10 text-red-400',
    idle: 'bg-gray-800 text-gray-500',
  }
  return colors[status] || colors.idle
}

export function ExperimentPanel({ experiments }: Props) {
  if (experiments.length === 0) {
    return (
      <div className="space-y-2">
        <h2 className="text-xs font-medium uppercase tracking-widest text-gray-500 mb-3">
          Experiments
        </h2>
        <div className="px-4 py-6 rounded-lg bg-surface-raised border border-border-subtle text-center">
          <p className="text-sm text-gray-600">No active experiments</p>
          <p className="text-xs text-gray-700 mt-1 font-mono">~/research/</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <h2 className="text-xs font-medium uppercase tracking-widest text-gray-500 mb-3">
        Experiments
      </h2>
      {experiments.map(exp => (
        <div
          key={exp.path}
          className="px-4 py-3 rounded-lg bg-surface-raised border border-border-subtle"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-white">{exp.name}</span>
              <span className="text-[10px] font-mono text-gray-600">
                {exp.mode === 'full' ? '2×GPU' : '1×GPU'}
              </span>
            </div>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${statusBadge(exp.status)}`}>
              {exp.status}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            {exp.currentRound !== null && (
              <span className="text-gray-400">
                round <span className="text-white font-mono">{exp.currentRound}</span>/∞
              </span>
            )}
            {exp.bestMetric !== null && (
              <span className="text-gray-400">
                best: <span className="text-emerald-400 font-mono">{exp.bestMetric.toFixed(4)}</span>
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

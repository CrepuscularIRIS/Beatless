import type { SystemStats } from '../types'

interface Props {
  system: SystemStats
}

export function SystemPanel({ system }: Props) {
  const gpuPercent = system.gpu
    ? Math.round((system.gpu.memoryUsed / system.gpu.memoryTotal) * 100)
    : 0

  return (
    <div className="space-y-2">
      <h2 className="text-xs font-medium uppercase tracking-widest text-gray-500 mb-3">
        System
      </h2>
      <div className="grid grid-cols-2 gap-2">
        <div className="px-3 py-2.5 rounded-lg bg-surface-raised border border-border-subtle">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Hermes</div>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${system.hermesGateway ? 'bg-emerald-400' : 'bg-gray-600'}`} />
            <span className={`text-sm font-mono ${system.hermesGateway ? 'text-emerald-400' : 'text-gray-500'}`}>
              {system.hermesGateway ? 'running' : 'stopped'}
            </span>
          </div>
        </div>

        <div className="px-3 py-2.5 rounded-lg bg-surface-raised border border-border-subtle">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">GPU</div>
          {system.gpu ? (
            <div>
              <div className="text-sm font-mono text-white">{system.gpu.utilization}%</div>
              <div className="mt-1 h-1 rounded-full bg-gray-800 overflow-hidden">
                <div
                  className="h-full rounded-full bg-accent transition-all duration-500"
                  style={{ width: `${gpuPercent}%` }}
                />
              </div>
              <div className="text-[10px] text-gray-600 mt-0.5 font-mono">
                {system.gpu.memoryUsed}MB / {system.gpu.memoryTotal}MB
              </div>
            </div>
          ) : (
            <span className="text-sm text-gray-600">n/a</span>
          )}
        </div>
      </div>
    </div>
  )
}

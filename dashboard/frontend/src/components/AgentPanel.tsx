import type { Agent } from '../types'

interface Props {
  agents: Agent[]
}

export function AgentPanel({ agents }: Props) {
  return (
    <div className="space-y-2">
      <h2 className="text-xs font-medium uppercase tracking-widest text-gray-500 mb-3">
        Agents
      </h2>
      {agents.map(agent => (
        <div
          key={agent.id}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-surface-raised hover:bg-surface-overlay transition-colors"
        >
          <div className="relative">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: agent.color }}
            />
            {agent.status === 'active' && (
              <div
                className="absolute inset-0 w-2.5 h-2.5 rounded-full animate-ping opacity-40"
                style={{ backgroundColor: agent.color }}
              />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-white">{agent.name}</span>
              <span className="text-[10px] text-gray-600 font-mono">{agent.role}</span>
            </div>
            <div className="text-xs text-gray-500 truncate">
              {agent.status === 'active' ? (
                <span className="text-emerald-400">{agent.currentTask || 'working...'}</span>
              ) : (
                <span>{agent.model}</span>
              )}
            </div>
          </div>
          <div
            className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
              agent.status === 'active'
                ? 'bg-emerald-400/10 text-emerald-400'
                : 'bg-gray-800 text-gray-500'
            }`}
          >
            {agent.status}
          </div>
        </div>
      ))}
    </div>
  )
}

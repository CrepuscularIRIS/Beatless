export interface Agent {
  id: string
  name: string
  role: string
  model: string
  color: string
  status: 'active' | 'idle'
  currentTask: string | null
}

export interface Pipeline {
  id: string
  name: string
  interval: string
  agent: string
  status: string
  lastRun: string | null
  lastResult: string | null
}

export interface ActivityEvent {
  type: 'commit' | 'pipeline'
  timestamp: string
  message?: string
  sha?: string
  pipeline?: string
  status?: string
  detail?: string
}

export interface Experiment {
  name: string
  path: string
  mode: 'quick' | 'full'
  status: string
  currentRound: number | null
  bestMetric: number | null
}

export interface GpuInfo {
  name: string
  utilization: number
  memoryUsed: number
  memoryTotal: number
}

export interface SystemStats {
  hermesGateway: boolean
  gpu: GpuInfo | null
  timestamp: string
}

export interface DashboardData {
  agents: Agent[]
  pipelines: Pipeline[]
  activity: ActivityEvent[]
  experiments: Experiment[]
  system: SystemStats
  collectedAt: string
}

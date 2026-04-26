import { useDashboard } from './useSSE'
import { Header } from './components/Header'
import { AgentPanel } from './components/AgentPanel'
import { PipelinePanel } from './components/PipelinePanel'
import { Timeline } from './components/Timeline'
import { ExperimentPanel } from './components/ExperimentPanel'
import { SystemPanel } from './components/SystemPanel'

function App() {
  const { data, connected } = useDashboard()

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <div className="max-w-7xl mx-auto">
        <Header connected={connected} collectedAt={data.collectedAt} />

        <div className="grid grid-cols-12 gap-4 p-4">
          {/* Left sidebar — agents + system */}
          <div className="col-span-3 space-y-6">
            <AgentPanel agents={data.agents} />
            <SystemPanel system={data.system} />
          </div>

          {/* Main content — timeline */}
          <div className="col-span-5">
            <Timeline events={data.activity} />
          </div>

          {/* Right sidebar — pipelines + experiments */}
          <div className="col-span-4 space-y-6">
            <PipelinePanel pipelines={data.pipelines} />
            <ExperimentPanel experiments={data.experiments} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App

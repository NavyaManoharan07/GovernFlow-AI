import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { WorkflowProvider } from './context/WorkflowContext'
import { AgentRegistryPage } from './pages/AgentRegistryPage'
import { ApplicationsPage } from './pages/ApplicationsPage'
import { AuditPage } from './pages/AuditPage'
import { CommandCenter } from './pages/CommandCenter'
import { WorkflowGraphPage } from './pages/WorkflowGraphPage'

export default function App() {
  return (
    <WorkflowProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/graph" element={<WorkflowGraphPage />} />
          <Route path="/agents" element={<AgentRegistryPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/audit" element={<AuditPage />} />
        </Routes>
      </Layout>
    </WorkflowProvider>
  )
}

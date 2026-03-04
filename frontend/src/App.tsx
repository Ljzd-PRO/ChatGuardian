import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import RuleManagement from './pages/RuleManagement'
import TriggerStats from './pages/TriggerStats'
import MessageQueue from './pages/MessageQueue'
import SystemConfig from './pages/SystemConfig'

function App() {
  return (
    <BrowserRouter basename="/app">
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="rules" element={<RuleManagement />} />
          <Route path="stats" element={<TriggerStats />} />
          <Route path="queues" element={<MessageQueue />} />
          <Route path="config" element={<SystemConfig />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App

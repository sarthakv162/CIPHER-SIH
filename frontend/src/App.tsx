import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Artefacts } from '@/routes/Artefacts'
import { Entry } from '@/routes/Entry'
import { Parivartan } from '@/routes/Parivartan'
import { Run } from '@/routes/Run'
import { System } from '@/routes/System'
import { Workspace } from '@/routes/Workspace'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Entry />} />
      <Route element={<AppShell />}>
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/runs/:transformId" element={<Run />} />
        <Route path="/artefacts" element={<Artefacts />} />
        <Route path="/parivartan" element={<Parivartan />} />
        <Route path="/system" element={<System />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

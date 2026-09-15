import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Artefacts } from '@/routes/Artefacts'
import { Parivartan } from '@/routes/Parivartan'
import { Run } from '@/routes/Run'
import { System } from '@/routes/System'
import { Workspace } from '@/routes/Workspace'

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Workspace />} />
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/runs/:transformId" element={<Run />} />
        <Route path="/runs/:transformId/artefacts" element={<Artefacts />} />
        <Route path="/artefacts" element={<Artefacts />} />
        <Route path="/parivartan" element={<Parivartan />} />
        <Route path="/system" element={<System />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

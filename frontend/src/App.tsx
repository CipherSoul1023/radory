import { Route, Routes } from 'react-router-dom'
import { SetupPage } from './pages/SetupPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SetupPage />} />
    </Routes>
  )
}

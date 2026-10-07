import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { OptionalClerkProvider } from './components/OptionalClerkProvider'
import { configureMonitoring } from './services/monitoring'
import './index.css'

void configureMonitoring()

const queryClient = new QueryClient()
const app = (
  <BrowserRouter>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </BrowserRouter>
)
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <OptionalClerkProvider>{app}</OptionalClerkProvider>
  </StrictMode>,
)

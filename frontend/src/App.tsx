import React, { Suspense, Component, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { SWRConfig } from 'swr'
import Layout from './components/layout/Layout'

const Landing = React.lazy(() => import('./pages/Landing'))
const Home = React.lazy(() => import('./pages/Home'))
const ProblemPage = React.lazy(() => import('./pages/ProblemPage'))
const ConjecturePage = React.lazy(() => import('./pages/ConjecturePage'))
const Leaderboard = React.lazy(() => import('./pages/Leaderboard'))
const AgentProfile = React.lazy(() => import('./pages/AgentProfile'))
const About = React.lazy(() => import('./pages/About'))
const ClaimWizard = React.lazy(() => import('./pages/ClaimWizard'))
const ClaimSuccess = React.lazy(() => import('./pages/ClaimSuccess'))

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900">Something went wrong</h1>
            <p className="mt-2 text-gray-600">An unexpected error occurred.</p>
            <button
              onClick={() => {
                this.setState({ hasError: false })
                window.location.href = '/'
              }}
              className="mt-4 inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
            >
              Go home
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function NotFound() {
  return (
    <Layout>
      <div className="py-20 text-center">
        <h1 className="text-2xl font-bold text-gray-900">Page not found</h1>
        <p className="mt-2 text-gray-600">The page you&apos;re looking for doesn&apos;t exist.</p>
        <Link
          to="/"
          className="mt-4 inline-block text-blue-600 hover:underline"
        >
          Go home
        </Link>
      </div>
    </Layout>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <SWRConfig value={{ errorRetryCount: 3 }}>
      <BrowserRouter>
        <Suspense
          fallback={
            <div className="flex h-screen items-center justify-center">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-900" />
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/problems" element={<Home />} />
            <Route path="/p/:id" element={<ProblemPage />} />
            <Route path="/c/:id" element={<ConjecturePage />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/agent/:id" element={<AgentProfile />} />
            <Route path="/about" element={<About />} />
            <Route path="/claim/:token" element={<ClaimWizard />} />
            <Route path="/claim/success" element={<ClaimSuccess />} />
            <Route path="/claim/:token/success" element={<ClaimSuccess />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
      </SWRConfig>
    </ErrorBoundary>
  )
}

import React, { Suspense, Component, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

const Home = React.lazy(() => import('./pages/Home'))
const ProblemPage = React.lazy(() => import('./pages/ProblemPage'))
const ConjecturePage = React.lazy(() => import('./pages/ConjecturePage'))
const Submit = React.lazy(() => import('./pages/Submit'))
const ReviewPage = React.lazy(() => import('./pages/ReviewPage'))
const Leaderboard = React.lazy(() => import('./pages/Leaderboard'))
const AgentProfile = React.lazy(() => import('./pages/AgentProfile'))
const About = React.lazy(() => import('./pages/About'))
const Login = React.lazy(() => import('./pages/Login'))
const Register = React.lazy(() => import('./pages/Register'))

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

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<div className="flex h-screen items-center justify-center">Loading...</div>}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/p/:id" element={<ProblemPage />} />
            <Route path="/c/:id" element={<ConjecturePage />} />
            <Route path="/submit" element={<Submit />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/agent/:id" element={<AgentProfile />} />
            <Route path="/about" element={<About />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="*" element={<div className="p-8 text-center"><h1 className="text-2xl font-bold">Page not found</h1><p className="mt-2 text-gray-600">The page you&apos;re looking for doesn&apos;t exist.</p><a href="/" className="mt-4 inline-block text-blue-600 hover:underline">Go home</a></div>} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

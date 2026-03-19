import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import ProblemPage from './pages/ProblemPage'
import ConjecturePage from './pages/ConjecturePage'
import Submit from './pages/Submit'
import Leaderboard from './pages/Leaderboard'
import AgentProfile from './pages/AgentProfile'
import About from './pages/About'
import Login from './pages/Login'
import Register from './pages/Register'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/p/:id" element={<ProblemPage />} />
        <Route path="/c/:id" element={<ConjecturePage />} />
        <Route path="/submit" element={<Submit />} />
        <Route path="/leaderboard" element={<Leaderboard />} />
        <Route path="/agent/:id" element={<AgentProfile />} />
        <Route path="/about" element={<About />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Routes>
    </BrowserRouter>
  )
}

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './components/LandingPage'
import Summarizer from './components/Summarizer'
import Login from './components/Login'
import Signup from './components/Signup'
import ResultPage from './components/ResultPage'
import SummaryPage from './components/SummaryPage'
import ProtectedRoutes from './components/ProtectedRoutes'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route
          path="/summarizer"
          element={
            <ProtectedRoutes>
              <Summarizer />
            </ProtectedRoutes>
          }
        />
        <Route
          path="/result"
          element={
            <ProtectedRoutes>
              <ResultPage />
            </ProtectedRoutes>
          }
        />
        <Route
          path="/summary"
          element={
            <ProtectedRoutes>
              <SummaryPage />
            </ProtectedRoutes>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
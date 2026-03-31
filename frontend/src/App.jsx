import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Events from './pages/Events'
import EventDetail from './pages/EventDetail'
import Teams from './pages/Teams'
import TeamDetail from './pages/TeamDetail'
import Players from './pages/Players'
import PlayerDetail from './pages/PlayerDetail'
import Matches from './pages/Matches'
import MatchDetail from './pages/MatchDetail'
import { AuthProvider } from './components/cartola/AuthProvider'
import CartolaHome from './pages/cartola/CartolaHome'
import Market from './pages/cartola/Market'
import PlayerMarket from './pages/cartola/PlayerMarket'
import Portfolio from './pages/cartola/Portfolio'
import Ranking from './pages/cartola/Ranking'
import Login from './pages/cartola/Login'
import Register from './pages/cartola/Register'
import TransactionHistory from './pages/cartola/TransactionHistory'
import LinkDiscord from './pages/cartola/LinkDiscord'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter basename="/hltv">
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/events" element={<Events />} />
            <Route path="/events/:id" element={<EventDetail />} />
            <Route path="/teams" element={<Teams />} />
            <Route path="/teams/:id" element={<TeamDetail />} />
            <Route path="/players" element={<Players />} />
            <Route path="/players/:id" element={<PlayerDetail />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/matches/:id" element={<MatchDetail />} />
            <Route path="/cartola" element={<CartolaHome />} />
            <Route path="/cartola/market" element={<Market />} />
            <Route path="/cartola/market/:id" element={<PlayerMarket />} />
            <Route path="/cartola/portfolio" element={<Portfolio />} />
            <Route path="/cartola/portfolio/history" element={<TransactionHistory />} />
            <Route path="/cartola/ranking" element={<Ranking />} />
            <Route path="/cartola/login" element={<Login />} />
            <Route path="/cartola/register" element={<Register />} />
            <Route path="/cartola/link" element={<LinkDiscord />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App

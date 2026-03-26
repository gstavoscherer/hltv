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

function App() {
  return (
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
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App

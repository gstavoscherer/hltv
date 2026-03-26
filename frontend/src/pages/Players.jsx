import { useState, useEffect, useCallback } from 'react'
import { fetchApi } from '../api'
import PlayerTable from '../components/PlayerTable'

const PAGE_SIZE = 50

export default function Players() {
  const [players, setPlayers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sortBy, setSortBy] = useState('rating_2_0')
  const [order, setOrder] = useState('desc')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [total, setTotal] = useState(0)

  const loadPlayers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = `?sort_by=${sortBy}&order=${order}&limit=${PAGE_SIZE}&offset=${offset}&search=${encodeURIComponent(search)}`
      const data = await fetchApi(`/players${params}`)
      let arr
      if (Array.isArray(data)) {
        arr = data
        setTotal(data.length + offset)
        setHasMore(data.length === PAGE_SIZE)
      } else {
        arr = data.players || data.data || []
        setTotal(data.total || arr.length + offset)
        setHasMore(arr.length === PAGE_SIZE)
      }
      setPlayers(arr)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [sortBy, order, search, offset])

  useEffect(() => {
    loadPlayers()
  }, [loadPlayers])

  function handleSort(key, ord) {
    setSortBy(key)
    setOrder(ord)
    setOffset(0)
  }

  function handleSearch(e) {
    e.preventDefault()
    setSearch(searchInput)
    setOffset(0)
  }

  return (
    <div>
      <div className="page-header">
        <h1>Players</h1>
        <p>Browse and sort player career statistics</p>
      </div>

      <form onSubmit={handleSearch} className="search-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Search players by nickname..."
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
        />
        <button
          type="submit"
          style={{
            padding: '8px 20px',
            background: 'var(--accent)',
            border: 'none',
            borderRadius: 6,
            color: '#fff',
            fontWeight: 600,
            cursor: 'pointer',
            fontSize: 14,
          }}
        >
          Search
        </button>
        {search && (
          <button
            type="button"
            onClick={() => { setSearchInput(''); setSearch(''); setOffset(0) }}
            style={{
              padding: '8px 16px',
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: 14,
            }}
          >
            Clear
          </button>
        )}
      </form>

      {error && <div className="error-message">Failed to load players: {error}</div>}

      {loading ? (
        <div className="loading"><span className="loading-spinner"></span>Loading players...</div>
      ) : players.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">&#9786;</div>
          <p>{search ? `No players matching "${search}".` : 'No player data yet.'}</p>
        </div>
      ) : (
        <>
          <PlayerTable
            players={players}
            sortBy={sortBy}
            order={order}
            onSort={handleSort}
          />

          <div className="pagination">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </button>
            <span className="page-info">
              Showing {offset + 1}-{offset + players.length}
            </span>
            <button
              disabled={!hasMore}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}

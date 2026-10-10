import { ChevronDown, Search } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { getBrokerageInitials } from '../../services/dashboard'

type AppTopbarProps = {
  workspaceName: string
}

export function AppTopbar({ workspaceName }: AppTopbarProps) {
  const [searchValue, setSearchValue] = useState('')
  const [searchMessage, setSearchMessage] = useState('')
  const searchInput = useRef<HTMLInputElement>(null)
  const initials = getBrokerageInitials(workspaceName)

  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchInput.current?.focus()
      }
    }
    window.addEventListener('keydown', focusSearch)
    return () => window.removeEventListener('keydown', focusSearch)
  }, [])

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSearchMessage(
      searchValue.trim() ? 'No matching Radory intelligence yet.' : '',
    )
  }

  return (
    <header className="workspace-dashboard-topbar">
      <div className="workspace-dashboard-search-area">
        <form
          className="workspace-dashboard-search"
          role="search"
          onSubmit={submitSearch}
        >
          <Search aria-hidden="true" size={18} />
          <input
            aria-label="Search Radory"
            onChange={(event) => {
              setSearchValue(event.target.value)
              if (!event.target.value.trim()) setSearchMessage('')
            }}
            placeholder="Search companies, opportunities, signals..."
            ref={searchInput}
            type="search"
            value={searchValue}
          />
          <kbd>⌘ K</kbd>
        </form>
        {searchMessage && (
          <p className="workspace-dashboard-search-result" role="status">
            {searchMessage}
          </p>
        )}
      </div>

      <div className="workspace-dashboard-workspace-area">
        <div
          className="workspace-dashboard-workspace-chip"
          aria-label={`Active brokerage: ${workspaceName}`}
        >
          <span className="workspace-dashboard-workspace-logo">{initials}</span>
          <span className="workspace-dashboard-workspace-meta">
            <strong title={workspaceName}>{workspaceName}</strong>
            <span>Active brokerage</span>
          </span>
          <ChevronDown
            aria-hidden="true"
            className="workspace-dashboard-workspace-chevron"
            size={16}
          />
        </div>
      </div>
    </header>
  )
}

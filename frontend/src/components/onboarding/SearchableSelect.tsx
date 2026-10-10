import { ChevronDown, Search, X } from 'lucide-react'
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type RefObject,
} from 'react'
import { createPortal } from 'react-dom'

export interface SearchOption {
  id: string
  label: string
  meta?: string
  preferred?: boolean
}

interface FloatingPosition {
  left: number
  top: number
  width: number
  maxHeight: number
}

function useFloatingMenu(
  open: boolean,
  onClose: () => void,
): {
  anchorRef: RefObject<HTMLDivElement | null>
  menuRef: RefObject<HTMLUListElement | null>
  menuStyle: CSSProperties
  syncPosition: () => void
} {
  const anchorRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLUListElement>(null)
  const [position, setPosition] = useState<FloatingPosition>({
    left: 0,
    top: 0,
    width: 0,
    maxHeight: 220,
  })

  const syncPosition = useCallback(() => {
    const bounds = anchorRef.current?.getBoundingClientRect()
    if (!bounds) return
    const top = bounds.bottom + 6
    const safeBottomMargin = 20
    const availableHeight = window.innerHeight - top - safeBottomMargin
    setPosition({
      left: bounds.left,
      top,
      width: bounds.width,
      maxHeight: Math.max(0, Math.min(220, availableHeight)),
    })
  }, [])

  useEffect(() => {
    if (!open) return

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node
      if (
        !anchorRef.current?.contains(target) &&
        !menuRef.current?.contains(target)
      )
        onClose()
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    window.addEventListener('resize', syncPosition)
    window.addEventListener('scroll', syncPosition, true)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('resize', syncPosition)
      window.removeEventListener('scroll', syncPosition, true)
    }
  }, [onClose, open, syncPosition])

  return {
    anchorRef,
    menuRef,
    menuStyle: {
      left: position.left,
      top: position.top,
      width: position.width,
      maxHeight: position.maxHeight,
    },
    syncPosition,
  }
}

export function SearchableCombobox({
  id,
  options,
  value,
  placeholder,
  onSelect,
}: {
  id: string
  options: readonly SearchOption[]
  value: SearchOption | null
  placeholder: string
  onSelect: (option: SearchOption) => void
}) {
  const listId = useId()
  const [query, setQuery] = useState(value?.label ?? '')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const close = useCallback(() => {
    setOpen(false)
    setQuery(value?.label ?? '')
  }, [value?.label])
  const { anchorRef, menuRef, menuStyle, syncPosition } = useFloatingMenu(
    open,
    close,
  )
  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase('en-ZA')
    if (!term || query === value?.label) return [...options]
    return options.filter(({ label, meta }) =>
      `${label} ${meta ?? ''}`.toLocaleLowerCase('en-ZA').includes(term),
    )
  }, [options, query, value?.label])
  const visibleOptions = filtered

  const openMenu = () => {
    syncPosition()
    setOpen(true)
  }
  const choose = (option: SearchOption) => {
    onSelect(option)
    setQuery(option.label)
    setOpen(false)
    setActiveIndex(0)
  }

  return (
    <div className="setup-combobox" ref={anchorRef}>
      <div className="setup-combobox-input">
        <Search size={15} aria-hidden="true" />
        <input
          aria-activedescendant={
            open && visibleOptions[activeIndex]
              ? `${listId}-${visibleOptions[activeIndex].id}`
              : undefined
          }
          aria-autocomplete="list"
          aria-controls={listId}
          aria-expanded={open}
          autoComplete="off"
          id={id}
          onChange={(event) => {
            setQuery(event.target.value)
            setActiveIndex(0)
            openMenu()
          }}
          onClick={openMenu}
          onFocus={(event) => {
            event.currentTarget.select()
            openMenu()
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              openMenu()
              setActiveIndex((index) =>
                Math.min(index + 1, Math.max(visibleOptions.length - 1, 0)),
              )
            } else if (event.key === 'ArrowUp') {
              event.preventDefault()
              setActiveIndex((index) => Math.max(index - 1, 0))
            } else if (
              event.key === 'Enter' &&
              open &&
              visibleOptions[activeIndex]
            ) {
              event.preventDefault()
              choose(visibleOptions[activeIndex])
            } else if (event.key === 'Escape') {
              event.preventDefault()
              close()
            }
          }}
          placeholder={placeholder}
          role="combobox"
          value={query}
        />
        <ChevronDown size={16} aria-hidden="true" />
      </div>
      {open &&
        createPortal(
          <ul
            className="setup-combobox-menu"
            data-floating-overlay="true"
            id={listId}
            ref={menuRef}
            role="listbox"
            style={menuStyle}
          >
            {visibleOptions.length ? (
              visibleOptions.map((option, index) => (
                <li
                  aria-selected={option.id === value?.id}
                  className={index === activeIndex ? 'is-active' : ''}
                  id={`${listId}-${option.id}`}
                  key={option.id}
                  onMouseDown={(event) => {
                    event.preventDefault()
                    choose(option)
                  }}
                  role="option"
                >
                  <span>{option.label}</span>
                  {option.meta && <small>{option.meta}</small>}
                </li>
              ))
            ) : (
              <li
                className="setup-combobox-empty"
                role="option"
                aria-selected="false"
              >
                No matching South African city
              </li>
            )}
          </ul>,
          document.body,
        )}
    </div>
  )
}

export function SearchableMultiCombobox({
  id,
  options,
  selected,
  placeholder,
  onSelect,
  onRemove,
}: {
  id: string
  options: readonly SearchOption[]
  selected: readonly string[]
  placeholder: string
  onSelect: (value: string) => void
  onRemove: (value: string) => void
}) {
  const listId = useId()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
    setActiveIndex(0)
  }, [])
  const { anchorRef, menuRef, menuStyle, syncPosition } = useFloatingMenu(
    open,
    close,
  )
  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase('en-ZA')
    return options
      .filter(({ label }) => !selected.includes(label))
      .filter(({ label, meta, preferred }) =>
        term
          ? `${label} ${meta ?? ''}`.toLocaleLowerCase('en-ZA').includes(term)
          : preferred,
      )
      .sort(
        (left, right) =>
          Number(right.preferred ?? false) - Number(left.preferred ?? false) ||
          left.label.localeCompare(right.label, 'en-ZA'),
      )
      .slice(0, 40)
  }, [options, query, selected])

  const openMenu = () => {
    syncPosition()
    setOpen(true)
  }
  const choose = (value: string) => {
    onSelect(value)
    close()
  }

  return (
    <div>
      <div className="setup-combobox" ref={anchorRef}>
        <div className="setup-combobox-input">
          <Search size={15} aria-hidden="true" />
          <input
            aria-activedescendant={
              open && filtered[activeIndex]
                ? `${listId}-${filtered[activeIndex].id}`
                : undefined
            }
            aria-autocomplete="list"
            aria-controls={listId}
            aria-expanded={open}
            autoComplete="off"
            id={id}
            onChange={(event) => {
              setQuery(event.target.value)
              setActiveIndex(0)
              openMenu()
            }}
            onClick={openMenu}
            onFocus={openMenu}
            onKeyDown={(event) => {
              if (event.key === 'ArrowDown') {
                event.preventDefault()
                openMenu()
                setActiveIndex((index) =>
                  Math.min(index + 1, Math.max(filtered.length - 1, 0)),
                )
              } else if (event.key === 'ArrowUp') {
                event.preventDefault()
                setActiveIndex((index) => Math.max(index - 1, 0))
              } else if (
                event.key === 'Enter' &&
                open &&
                filtered[activeIndex]
              ) {
                event.preventDefault()
                choose(filtered[activeIndex].label)
              } else if (event.key === 'Escape') {
                event.preventDefault()
                close()
              }
            }}
            placeholder={placeholder}
            role="combobox"
            value={query}
          />
        </div>
        {open &&
          createPortal(
            <ul
              className="setup-combobox-menu"
              data-floating-overlay="true"
              id={listId}
              ref={menuRef}
              role="listbox"
              style={menuStyle}
            >
              {filtered.length ? (
                filtered.map((option, index) => (
                  <li
                    aria-selected="false"
                    className={index === activeIndex ? 'is-active' : ''}
                    id={`${listId}-${option.id}`}
                    key={option.id}
                    onMouseDown={(event) => {
                      event.preventDefault()
                      choose(option.label)
                    }}
                    role="option"
                  >
                    <span>{option.label}</span>
                    {option.meta && <small>{option.meta}</small>}
                  </li>
                ))
              ) : (
                <li
                  className="setup-combobox-empty"
                  role="option"
                  aria-selected="false"
                >
                  No matching submarket found
                </li>
              )}
            </ul>,
            document.body,
          )}
      </div>
      {selected.length > 0 && (
        <div className="setup-tags" aria-label="Selected submarkets">
          {selected.map((value) => (
            <button key={value} onClick={() => onRemove(value)} type="button">
              {value}
              <X size={12} aria-hidden="true" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

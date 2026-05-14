import { useState, useRef, useEffect, useId, ReactNode, KeyboardEvent } from 'react'
import { Icon } from './Icon'
import './Select.css'

export interface SelectOption {
  value: string
  label: ReactNode
  meta?: string
}

interface SelectProps {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  id?: string
  'aria-label'?: string
  onClose?: () => void
}

export const Select = ({
  value,
  onChange,
  options,
  placeholder = 'Select…',
  disabled = false,
  id,
  'aria-label': ariaLabel,
  onClose,
}: SelectProps) => {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [typeahead, setTypeahead] = useState('')
  const typeaheadTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const [popupPos, setPopupPos] = useState<{
    top: number
    left: number
    width: number
    maxHeight: number
  } | null>(null)
  const uid = useId()
  const listboxId = `${uid}-listbox`

  const selectedIndex = options.findIndex((o) => o.value === value)
  const selectedOption = options[selectedIndex]
  const displayLabel = selectedOption?.label ?? placeholder

  const openMenu = () => {
    if (disabled) return
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      const viewportH = window.innerHeight
      const gap = 4
      const margin = 8
      const maxPopupH = 320
      const spaceBelow = viewportH - rect.bottom - margin
      const spaceAbove = rect.top - margin
      // Flip upward only when there's clearly not enough room below
      // and meaningfully more room above. Otherwise prefer downward.
      const openUpward = spaceBelow < 200 && spaceAbove > spaceBelow
      const maxHeight = Math.max(
        120,
        Math.min(maxPopupH, openUpward ? spaceAbove : spaceBelow)
      )
      const top = openUpward
        ? Math.max(margin, rect.top - gap - maxHeight)
        : rect.bottom + gap
      setPopupPos({
        top,
        left: rect.left,
        width: Math.max(rect.width, 180),
        maxHeight,
      })
    }
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0)
    setOpen(true)
  }

  const closeMenu = (suppressOnClose = false) => {
    setOpen(false)
    triggerRef.current?.focus()
    if (!suppressOnClose) onClose?.()
  }

  const selectOption = (optValue: string) => {
    onChange(optValue)
    closeMenu(true)
  }

  // Focus the listbox when it opens
  useEffect(() => {
    if (open && listRef.current) {
      listRef.current.focus()
    }
  }, [open])

  // Scroll active item into view
  useEffect(() => {
    if (!open || activeIndex < 0) return
    const item = listRef.current?.children[activeIndex] as HTMLElement
    item?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex, open])

  // Click outside closes
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (
        !triggerRef.current?.contains(e.target as Node) &&
        !listRef.current?.contains(e.target as Node)
      ) {
        setOpen(false)
        onClose?.()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open, onClose])

  const handleTriggerKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      openMenu()
    }
  }

  const handleListKeyDown = (e: KeyboardEvent<HTMLUListElement>) => {
    switch (e.key) {
      case 'Escape':
        e.preventDefault()
        closeMenu()
        break
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex((i) => Math.min(i + 1, options.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex((i) => Math.max(i - 1, 0))
        break
      case 'Home':
        e.preventDefault()
        setActiveIndex(0)
        break
      case 'End':
        e.preventDefault()
        setActiveIndex(options.length - 1)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        if (activeIndex >= 0) selectOption(options[activeIndex].value)
        break
      case 'Tab':
        if (activeIndex >= 0) selectOption(options[activeIndex].value)
        else closeMenu()
        break
      default: {
        if (e.key.length === 1) {
          const char = e.key.toLowerCase()
          const next = typeahead + char
          setTypeahead(next)
          if (typeaheadTimer.current) clearTimeout(typeaheadTimer.current)
          typeaheadTimer.current = setTimeout(() => setTypeahead(''), 700)
          const idx = options.findIndex((o) =>
            String(o.label).toLowerCase().startsWith(next)
          )
          if (idx >= 0) setActiveIndex(idx)
        }
      }
    }
  }

  return (
    <div className="select-wrapper">
      <button
        ref={triggerRef}
        id={id}
        type="button"
        className={`select-trigger${open ? ' select-trigger--open' : ''}${disabled ? ' select-trigger--disabled' : ''}`}
        onClick={() => (open ? closeMenu() : openMenu())}
        onKeyDown={handleTriggerKeyDown}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-label={ariaLabel}
        disabled={disabled}
      >
        <span className="select-trigger__value">{displayLabel}</span>
        <Icon
          name="expand_more"
          size={18}
          className={`select-trigger__caret${open ? ' select-trigger__caret--open' : ''}`}
        />
      </button>

      {open && (
        <ul
          ref={listRef}
          id={listboxId}
          role="listbox"
          className="select-popup"
          style={
            popupPos
              ? {
                  position: 'fixed',
                  top: popupPos.top,
                  left: popupPos.left,
                  width: popupPos.width,
                  maxHeight: popupPos.maxHeight,
                }
              : {}
          }
          tabIndex={-1}
          onKeyDown={handleListKeyDown}
          aria-activedescendant={activeIndex >= 0 ? `${uid}-opt-${activeIndex}` : undefined}
        >
          {options.map((opt, i) => (
            <li
              key={opt.value}
              id={`${uid}-opt-${i}`}
              role="option"
              className={`select-option${i === activeIndex ? ' select-option--active' : ''}${opt.value === value ? ' select-option--selected' : ''}`}
              aria-selected={opt.value === value}
              onMouseEnter={() => setActiveIndex(i)}
              onMouseDown={(e) => {
                e.preventDefault()
                selectOption(opt.value)
              }}
            >
              <span className="select-option__label">{opt.label}</span>
              {opt.meta && <span className="select-option__meta">{opt.meta}</span>}
              {opt.value === value && (
                <Icon name="check" size={16} className="select-option__check" />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Select, SelectOption } from './Select'

// jsdom doesn't implement scrollIntoView
beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn()
})

// Two options share the 'c' prefix so multi-char typeahead can demonstrate narrowing.
const OPTIONS: SelectOption[] = [
  { value: 'apple', label: 'Apple' },
  { value: 'banana', label: 'Banana' },
  { value: 'cherry', label: 'Cherry' },
  { value: 'coconut', label: 'Coconut' },
  { value: 'date', label: 'Date' },
]

function setup(value = 'apple', onChange = vi.fn()) {
  const user = userEvent.setup()
  render(<Select value={value} onChange={onChange} options={OPTIONS} aria-label="fruit" />)
  return { user, onChange }
}

describe('Select', () => {
  it('renders the selected option label as the trigger text', () => {
    setup('banana')
    expect(screen.getByRole('button', { name: 'fruit' })).toHaveTextContent('Banana')
  })

  it('opens on click and closes on second click', async () => {
    const { user } = setup()
    const trigger = screen.getByRole('button', { name: 'fruit' })
    await user.click(trigger)
    expect(screen.getByRole('listbox')).toBeInTheDocument()
    await user.click(trigger)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('selects an option on click and calls onChange', async () => {
    const { user, onChange } = setup('apple')
    await user.click(screen.getByRole('button', { name: 'fruit' }))
    await user.click(screen.getByRole('option', { name: 'Cherry' }))
    expect(onChange).toHaveBeenCalledWith('cherry')
  })

  it('opens with Space and navigates down with ArrowDown', async () => {
    const { user, onChange } = setup('apple')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard(' ')
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    // apple(0) + 2 → cherry(2)
    expect(onChange).toHaveBeenCalledWith('cherry')
  })

  it('navigates up with ArrowUp from a non-first selection', async () => {
    // Start at cherry so ArrowUp has real work to do (would otherwise clamp at 0).
    const { user, onChange } = setup('cherry')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard('{Enter}')      // opens; activeIndex = selectedIndex = 2 (cherry)
    await user.keyboard('{ArrowUp}')    // → banana(1)
    await user.keyboard('{Enter}')
    expect(onChange).toHaveBeenCalledWith('banana')
  })

  it('jumps to last with End and to first with Home from a mid-list start', async () => {
    // Start at cherry (index 2) so both Home and End genuinely move activeIndex.
    const { user, onChange } = setup('cherry')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard('{Enter}{End}{Enter}')
    expect(onChange).toHaveBeenCalledWith('date')

    onChange.mockClear()
    trigger.focus()
    await user.keyboard('{Enter}{Home}{Enter}')
    expect(onChange).toHaveBeenCalledWith('apple')
  })

  it('Tab commits the active option', async () => {
    const { user, onChange } = setup('apple')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard('{Enter}{ArrowDown}{Tab}')
    // apple(0) → ArrowDown → banana(1), Tab commits.
    expect(onChange).toHaveBeenCalledWith('banana')
  })

  it('closes on Escape and returns focus to trigger', async () => {
    const { user } = setup()
    const trigger = screen.getByRole('button', { name: 'fruit' })
    await user.click(trigger)
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(trigger)
  })

  it('closes when clicking outside', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <div>
        <button>outside</button>
        <Select value="apple" onChange={onChange} options={OPTIONS} aria-label="fruit" />
      </div>
    )
    await user.click(screen.getByRole('button', { name: 'fruit' }))
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'outside' }))
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('single-char type-ahead jumps to the matching option', async () => {
    const { user, onChange } = setup('apple')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard('{Enter}d{Enter}')
    expect(onChange).toHaveBeenCalledWith('date')
  })

  it('multi-char type-ahead narrows past a shared prefix', async () => {
    // 'c' alone matches cherry (first c-option); 'co' must narrow to coconut.
    const { user, onChange } = setup('apple')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard('{Enter}co{Enter}')
    expect(onChange).toHaveBeenCalledWith('coconut')
  })

  it('does not open when disabled', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <Select value="apple" onChange={onChange} options={OPTIONS} disabled aria-label="fruit" />
    )
    const trigger = screen.getByRole('button', { name: 'fruit' })
    await user.click(trigger)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})

describe('Select type-ahead reset', () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
    // shouldAdvanceTime lets userEvent's internal awaits proceed in real time
    // while still letting us jump the 700ms typeahead timer with advanceTimersByTime.
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('resets after 700 ms idle so a new sequence starts fresh', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render(<Select value="apple" onChange={onChange} options={OPTIONS} aria-label="fruit" />)

    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()
    await user.keyboard('{Enter}')
    await user.keyboard('b') // typeahead = 'b' → banana

    // Flush the 700ms idle reset (act wraps the setTypeahead('') state update).
    act(() => {
      vi.advanceTimersByTime(750)
    })

    // If the reset didn't fire, typeahead would be 'bc' (no match, activeIndex stays at banana).
    // With reset, typeahead is fresh 'c' → cherry.
    await user.keyboard('c{Enter}')
    expect(onChange).toHaveBeenCalledWith('cherry')
  })
})

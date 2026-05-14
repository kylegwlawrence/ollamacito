import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Select, SelectOption } from './Select'

// jsdom doesn't implement scrollIntoView
beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn()
})

const OPTIONS: SelectOption[] = [
  { value: 'apple', label: 'Apple' },
  { value: 'banana', label: 'Banana' },
  { value: 'cherry', label: 'Cherry' },
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

  it('opens with Space and navigates with ArrowDown/ArrowUp', async () => {
    const { user, onChange } = setup('apple')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard(' ')
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    await user.keyboard('{ArrowDown}')
    await user.keyboard('{ArrowDown}')
    await user.keyboard('{Enter}')
    // Started at index 0 (apple), moved down 2 → cherry
    expect(onChange).toHaveBeenCalledWith('cherry')
  })

  it('navigates to last with End then first with Home', async () => {
    const { user, onChange } = setup('apple')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard('{Enter}')
    await user.keyboard('{End}')
    await user.keyboard('{Enter}')
    expect(onChange).toHaveBeenCalledWith('date')

    onChange.mockClear()
    trigger.focus()
    await user.keyboard('{Enter}')
    await user.keyboard('{Home}')
    await user.keyboard('{Enter}')
    expect(onChange).toHaveBeenCalledWith('apple')
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

  it('single-char type-ahead jumps to the matching option', async () => {
    const { user, onChange } = setup('apple')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard('{Enter}')
    await user.keyboard('d')
    await user.keyboard('{Enter}')
    expect(onChange).toHaveBeenCalledWith('date')
  })

  it('multi-char type-ahead narrows to a longer prefix', async () => {
    const { user, onChange } = setup('apple')
    const trigger = screen.getByRole('button', { name: 'fruit' })
    trigger.focus()

    await user.keyboard('{Enter}')
    // 'ch' prefix → Cherry (not Banana even though both start with a consonant)
    await user.keyboard('c')
    await user.keyboard('h')
    await user.keyboard('{Enter}')
    expect(onChange).toHaveBeenCalledWith('cherry')
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

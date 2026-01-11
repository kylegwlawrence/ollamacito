import { useState } from 'react'
import { Button } from '../common/Button'

/**
 * Test component for error boundaries
 * Remove this file after testing
 */
export const ErrorTest = () => {
  const [shouldThrow, setShouldThrow] = useState(false)

  if (shouldThrow) {
    throw new Error('Test error thrown intentionally! Error boundaries should catch this.')
  }

  return (
    <div style={{ padding: '2rem' }}>
      <h2>Error Boundary Test Component</h2>
      <p>Click the button below to throw an error and test the error boundary:</p>
      <Button onClick={() => setShouldThrow(true)} variant="danger">
        Throw Test Error
      </Button>
      <p style={{ marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>
        This will simulate a component crash. The error boundary should catch it and show a fallback UI.
      </p>
    </div>
  )
}

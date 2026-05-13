/**
 * Vitest setup — extends `expect` with jest-dom matchers and resets any
 * remaining DOM between tests. Loaded automatically by vitest.config.ts.
 */
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})

// Default model is loaded from backend settings
// Frontend waits for backend to load before allowing chat creation
// No hardcoded fallback - button shows "⏳ Loading..." until settings are available
export const DEFAULT_TEMPERATURE = 0.7
export const DEFAULT_MAX_TOKENS = 2048

export const TEMPERATURE_MIN = 0.0
export const TEMPERATURE_MAX = 2.0
export const TEMPERATURE_STEP = 0.1

export const MAX_TOKENS_MIN = 128
export const MAX_TOKENS_MAX = 8192
export const MAX_TOKENS_STEP = 128

export const CHAT_PAGE_SIZE = 20
export const MESSAGE_PAGE_SIZE = 50

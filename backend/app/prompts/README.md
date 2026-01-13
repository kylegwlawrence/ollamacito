# Prompts Directory

This directory contains prompt templates used by the application for various AI-powered features.

## Files

### `chat_title_generation.md`
Prompt used to automatically generate chat titles after the first assistant response.

**Configuration:** Set via `TITLE_GENERATION_PROMPT_FILE` environment variable or in `config.py`.

**Model:** Configured via `TITLE_GENERATION_MODEL` (default: SummLlama3.2:3B-Q5_K_M)

**Usage:** Automatically loaded when generating chat titles. You can modify this prompt without changing code - the system reads it dynamically at runtime.

## Adding New Prompts

To add a new prompt template:
1. Create a new `.md` file in this directory
2. Add a configuration field in `backend/app/core/config.py`
3. Load it dynamically in your service using `Path(settings.your_prompt_file).read_text()`

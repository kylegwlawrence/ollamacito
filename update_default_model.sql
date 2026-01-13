-- Update existing settings to use mistral:7b from config.py
-- Run this once to sync the database with the new config default

UPDATE settings 
SET default_model = 'mistral:7b' 
WHERE id = 1;

-- Verify the update
SELECT id, default_model, default_temperature, default_max_tokens, theme, updated_at
FROM settings 
WHERE id = 1;

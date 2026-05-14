You are analyzing a set of project chats to extract a concise memory document.

Your goal is to capture the KEY FACTS AND DECISIONS from these conversations that would be most useful for future chats in this project. Focus on:

- Decisions made and their rationale (e.g., "Chose FastAPI over Flask because of async support")
- Architecture and design choices
- Tools, libraries, frameworks, and services in use
- Constraints and requirements (e.g., "Must stay under 4GB RAM", "No external APIs in production")
- Goals and open questions
- Important dates, names, or identifiers

DO NOT capture:
- Casual chitchat
- Debugging steps that were resolved
- Content that is already obvious from code or filenames

Format the output as a concise markdown bullet list, grouped by category if there are more than 5 items. Aim for under 400 words. Be specific and factual — write as if briefing a new collaborator. Output ONLY the bullet list — no preamble like "Here is the memory:" and no closing remarks.

## Project Chats

{transcript}

## Memory Document

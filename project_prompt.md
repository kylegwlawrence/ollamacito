# Creating a new Ollama desktop app
Ollama has a MacOS desktop app. I've been using it frequently but it lacks some features. 

## Problem
Here is a description of the issues the define the problem:
- it crashes periodically
- there is no concept of:
    - a project
    - memory
    - additional context like files
    - collaboration across chats and projects
- it provides limited settings. You can control:
    - token size
    - folder where models are located

## Solution
Create a chat application that runs in Docker. It will have the following features:
    - single chats
    - projects
        - project instructions including system prompts
        - multiple chats
        - memory management
        - additional context like files
    - settings (per chat with defaults) for: 
        - token size
        - temperature
        - model selection (per chat)
    - chat history

## Requirements
1. Lightweight and Python based:
    - make the application as lightweight and simple as possible since the AI model is very resource intensive
    - write as much of the codebase in Python as you possibly can
2. Docker services:
    - use Docker compose to run all services with the exception of Ollama - that will be run locally
3. Front-end:
    - needs to be:
        - easy to navigate
        - uncluttered
        - built with components to navigate between sections in the app, such as projects, chat history, artifacts, files, memory, settings, etc
        - easy to expand with new features
    - use industry design standards
    - build in dark mode and light mode
    - you decide on the infrastructure
4. Back-end:
    - abstracted API calls that are easy to use and understand
    - simple storage solution (likely postgres)
    - robust error handling
    - backups
    - use postgres for storage and then you decide on the rest of the infrastructure
5. Infrastructure:
    - other than the suggestion to use postgres for the backend and docker compose for services, it is up to you to research and recommend the rest of the infrastructure
6. Test suite
    - create a simple test suite that covers all major features of the application
    - if we need to create more detailed tests/more coverage then we will do that later

## Instructions
- Simplicity first
- Research best practices for AI chat apps such as Claude. This will help you develop a clean app
- Produce helpful and concise but limited documentation. If we need to expand documentation we can do that later. 
- Use existing and well vetted libraries where possible to make development easier and faster
- Use DRY principles to avoid duplication of code wherever possible
- Handle errors gracefully and provide clear error messages to the user
- Write useful docstrings and code comments
- Do not use any cloud infrastucture
- store secrets in a .env file
- use a python venv called .venv

## Summary
Build a full-stack AI chat application that is more feature rich than the Ollama MacOS desktop app. The app wil use Ollama, postgres and Docker, and the rest of the infrastructure will be based on your recommendation.
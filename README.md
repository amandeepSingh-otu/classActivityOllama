# AI Dungeon (Local Ollama Edition)

A minimal text-adventure game powered by a local LLM (Ollama). Players explore, pick up items, and interact with the world using text commands.

---

## Features

- Rule-enforced gameplay with `rules.json`.
- Tracks `location`, `inventory`, `flags`, `hp`, and turns.
- Save/load game progress.
- Transcript of all actions saved in `samples/transcript.txt`.
- Supports both atomic state updates (list of strings) and dictionary-based updates.

---

## Installation

1. Clone the repository:

```bash
git clone <repo-url>
cd ai-dungeon
run the main.py

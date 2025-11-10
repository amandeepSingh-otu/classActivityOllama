
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# loqd all the files here 
BASE = Path(__file__).parent
RULES_PATH = BASE / "rules.json"
GM_PROMPT_PATH = BASE / "prompts/gm.txt"
SAVE_PATH = BASE / "save.json"
TRANSCRIPT_PATH = BASE / "samples/transcript.txt"
TRANSCRIPT_PATH.parent.mkdir(exist_ok=True)

MODEL = "llama3.1:8b"
MAX_HISTORY = 6

#load the rules over here, all json related function
def load_json(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(obj: Any, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def safe_json_extract(text: str) -> dict:
    """Extract JSON from model output even if extra text exists."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return {"narration": "Invalid GM response.", "state_change": []}

def append_transcript(entry: dict):
    with open(TRANSCRIPT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

#connect with ollama
def call_ollama(prompt: str) -> str:
    try:
        proc = subprocess.run(
            ["ollama", "run", MODEL],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=120
        )
        return proc.stdout.strip() or proc.stderr.strip()
    except Exception as e:
        sys.exit(f"[Error contacting Ollama: {e}]")

# -game logic
class GameEngine:
    def __init__(self, rules: dict):
        self.rules = rules
        self.state = dict(rules.get("START", {}))
        self.history: List[dict] = []

    def build_prompt(self, player_cmd: str) -> str:
        gm_text = GM_PROMPT_PATH.read_text(encoding="utf-8")
        return (
            f"{gm_text}\n\n"
            f"RULES_JSON:{json.dumps(self.rules,separators=(',',':'))}\n"
            f"CURRENT_STATE:{json.dumps(self.state,separators=(',',':'))}\n"
            f"RECENT_HISTORY:{json.dumps(self.history[-MAX_HISTORY:],indent=2)}\n"
            f"PLAYER_COMMAND:{player_cmd}\n\n"
            "INSTRUCTIONS: Reply strictly as JSON with keys 'narration' and 'state_change' "
        )

    def apply_state_changes(self, changes: List[str]):
        for atom in changes:
            if atom.startswith("move_to:"):
                self.state["location"] = atom.split(":",1)[1].strip()
            elif atom.startswith("add_item:"):
                item = atom.split(":",1)[1].strip()
                self.state.setdefault("inventory", [])
                if item not in self.state["inventory"]:
                    self.state["inventory"].append(item)
            elif atom.startswith("remove_item:"):
                item = atom.split(":",1)[1].strip()
                if item in self.state.get("inventory", []):
                    self.state["inventory"].remove(item)
            elif atom.startswith("set_flag:"):
                flag = atom.split(":",1)[1].strip()
                self.state.setdefault("flags", {})[flag] = True
            elif atom.startswith("hp_delta:"):
                try:
                    delta = int(atom.split(":",1)[1])
                except ValueError:
                    delta = 0
                self.state["hp"] = self.state.get("hp",0) + delta
                if self.state["hp"] <= 0:
                    self.state.setdefault("flags", {})["hp_zero"] = True
        self.state["turns"] = self.state.get("turns",0) + 1

    def check_end_conditions(self) -> Optional[str]:
        end = self.rules.get("END_CONDITIONS", {})
        flags = self.state.get("flags", {})

        if all(flags.get(f) for f in end.get("WIN_ALL_FLAGS", [])):
            return "You won!"
        if any(flags.get(f) for f in end.get("LOSE_ANY_FLAGS", [])):
            return " You lost!"
        if self.state.get("turns",0) >= end.get("MAX_TURNS", float("inf")):
            return " Max turns exceeded!"
        return None

    def handle_command(self, cmd: str):
        cmd = cmd.lower()
        if cmd == "help":
            print("Commands:", ", ".join(self.rules.get("COMMANDS", [])))
            return
        if cmd == "inventory":
            print("nventory:", ", ".join(self.state.get("inventory", [])) or "empty")
            return
        if cmd == "save":
            save_json(self.state, SAVE_PATH)
            print(f"Saved game → {SAVE_PATH}")
            return
        if cmd == "load":
            if SAVE_PATH.exists():
                self.state = load_json(SAVE_PATH)
                print("Loaded save.")
            else:
                print("No save file found.")
            return
        if cmd == "quit":
            print(" Goodbye!")
            sys.exit(0)

        # Call GM
        prompt = self.build_prompt(cmd)
        raw = call_ollama(prompt)
        parsed = safe_json_extract(raw)

        narration = parsed.get("narration","")
        state_change = parsed.get("state_change",[])
        self.apply_state_changes(state_change)

        # Show narration
        if isinstance(narration,list):
            narration_text = "\n".join(str(p).strip() for p in narration)
        else:
            narration_text = str(narration).strip()
        print("\n"+narration_text+"\n")

        # Append history & transcript
        self.history.append({"player": cmd, "gm": {"narration": narration, "state_change": state_change}})
        append_transcript({"player": cmd, "gm": {"narration": narration, "state_change": state_change}, "state": self.state})

        # Check end
        end_reason = self.check_end_conditions()
        if end_reason:
            print(end_reason)
            sys.exit(0)

def main():
    rules = load_json(RULES_PATH)
    engine = GameEngine(rules)

    print("\n"+rules.get("QUEST",{}).get("intro","Welcome to AI Dungeon!")+"\n")
    print("Type 'help' for commands. 'save', 'load', 'inventory', 'quit' available.\n")

    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            engine.handle_command(cmd)
            time.sleep(0.05)
        except KeyboardInterrupt:
            print("\n Exiting.")
            break

if __name__ == "__main__":
    main()

import json
import os
from typing import Dict, Any, Tuple, Optional

DATA_FILE = "data.json"


class GoalStorage:
    def __init__(self, filepath: str = DATA_FILE):
        self.filepath = filepath
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        default_data = {
            "title": "COMMUNITY FUNDING GOAL",
            "goal": 500.0,
            "current": 0.0,
            "currency": "$",
            "goal_reached_announced": False,
            "primary_guild_id": None,
            "primary_channel_id": None,
            "primary_message_id": None
        }
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # If migrating from old guilds format, retain target values
                    if "guilds" in loaded and loaded["guilds"]:
                        first_guild = next(iter(loaded["guilds"].values()))
                        default_data["title"] = first_guild.get("title", default_data["title"])
                        default_data["goal"] = float(first_guild.get("goal", default_data["goal"]))
                        default_data["current"] = float(first_guild.get("current", default_data["current"]))
                    default_data.update({k: v for k, v in loaded.items() if k in default_data})
                    return default_data
            except Exception as e:
                print(f"[Storage] Error loading {self.filepath}: {e}")
        return default_data

    def _save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Storage] Error saving to {self.filepath}: {e}")

    def set_primary(self, guild_id: int | str, channel_id: int | str, message_id: Optional[int | str] = None):
        self.data["primary_guild_id"] = str(guild_id)
        self.data["primary_channel_id"] = int(channel_id)
        if message_id:
            self.data["primary_message_id"] = int(message_id)
        self._save()

    def set_message_id(self, message_id: int):
        self.data["primary_message_id"] = int(message_id)
        self._save()

    def get_data(self) -> Dict[str, Any]:
        return self.data

    def set_goal(self, goal: float, title: Optional[str] = None, reset_current: bool = False) -> Dict[str, Any]:
        self.data["goal"] = float(goal)
        if title:
            self.data["title"] = title.strip()
        if reset_current:
            self.data["current"] = 0.0
            
        self.data["goal_reached_announced"] = (self.data["current"] >= self.data["goal"]) and (self.data["goal"] > 0)
        self._save()
        return self.data

    def add_money(self, amount: float) -> Tuple[Dict[str, Any], bool]:
        prev = self.data["current"]
        self.data["current"] += float(amount)
        
        was_below = prev < self.data["goal"]
        is_reached = self.data["current"] >= self.data["goal"] and self.data["goal"] > 0
        just_reached = was_below and is_reached and not self.data.get("goal_reached_announced", False)
        
        if is_reached:
            self.data["goal_reached_announced"] = True
            
        self._save()
        return self.data, just_reached

    def set_current_cash(self, amount: float) -> Tuple[Dict[str, Any], bool]:
        prev = self.data["current"]
        self.data["current"] = max(0.0, float(amount))
        
        was_below = prev < self.data["goal"]
        is_reached = self.data["current"] >= self.data["goal"] and self.data["goal"] > 0
        just_reached = was_below and is_reached and not self.data.get("goal_reached_announced", False)
        
        if is_reached:
            self.data["goal_reached_announced"] = True
        else:
            self.data["goal_reached_announced"] = False
            
        self._save()
        return self.data, just_reached


storage = GoalStorage()

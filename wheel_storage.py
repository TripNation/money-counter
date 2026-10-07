import json
import os
import threading
from typing import Any, Optional

DATA_FILE = "wheel_data.json"
_lock = threading.Lock()

def _load_raw() -> dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_raw(data: dict[str, Any]) -> None:
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    if os.path.exists(DATA_FILE):
        os.replace(temp_file, DATA_FILE)
    else:
        os.rename(temp_file, DATA_FILE)

class WheelStorage:
    @staticmethod
    def _get_guild(data: dict[str, Any], guild_id: int) -> dict[str, Any]:
        gid = str(guild_id)
        if gid not in data:
            data[gid] = {
                "entries": [],
                "active_signup": None,
                "history": []
            }
        return data[gid]

    @classmethod
    def get_entries(cls, guild_id: int) -> list[dict[str, Any]]:
        with _lock:
            data = _load_raw()
            guild = cls._get_guild(data, guild_id)
            return list(guild.get("entries", []))

    @classmethod
    def add_entry(cls, guild_id: int, user_id: int, user_name: str) -> bool:
        with _lock:
            data = _load_raw()
            guild = cls._get_guild(data, guild_id)
            entries = guild.setdefault("entries", [])
            for e in entries:
                if e.get("id") == user_id:
                    e["name"] = user_name
                    _save_raw(data)
                    return False
            entries.append({"id": user_id, "name": user_name})
            _save_raw(data)
            return True

    @classmethod
    def remove_entry(cls, guild_id: int, user_id: int) -> bool:
        with _lock:
            data = _load_raw()
            guild = cls._get_guild(data, guild_id)
            entries = guild.setdefault("entries", [])
            initial_len = len(entries)
            guild["entries"] = [e for e in entries if e.get("id") != user_id]
            if len(guild["entries"]) != initial_len:
                _save_raw(data)
                return True
            return False

    @classmethod
    def clear_entries(cls, guild_id: int) -> int:
        with _lock:
            data = _load_raw()
            guild = cls._get_guild(data, guild_id)
            count = len(guild.get("entries", []))
            guild["entries"] = []
            _save_raw(data)
            return count

    @classmethod
    def set_active_signup(cls, guild_id: int, signup_info: dict[str, Any]) -> None:
        with _lock:
            data = _load_raw()
            guild = cls._get_guild(data, guild_id)
            guild["active_signup"] = signup_info
            _save_raw(data)

    @classmethod
    def get_active_signup(cls, guild_id: int) -> Optional[dict[str, Any]]:
        with _lock:
            data = _load_raw()
            guild = cls._get_guild(data, guild_id)
            return guild.get("active_signup")

    @classmethod
    def mark_signup_closed(cls, guild_id: int) -> None:
        with _lock:
            data = _load_raw()
            guild = cls._get_guild(data, guild_id)
            if guild.get("active_signup"):
                guild["active_signup"]["closed"] = True
            _save_raw(data)

    @classmethod
    def clear_active_signup(cls, guild_id: int) -> None:
        with _lock:
            data = _load_raw()
            guild = cls._get_guild(data, guild_id)
            guild["active_signup"] = None
            _save_raw(data)

    @classmethod
    def record_winner(cls, guild_id: int, user_id: int, user_name: str) -> None:
        with _lock:
            data = _load_raw()
            guild = cls._get_guild(data, guild_id)
            history = guild.setdefault("history", [])
            import time
            history.insert(0, {
                "winner_id": user_id,
                "winner_name": user_name,
                "timestamp": int(time.time())
            })
            guild["history"] = history[:20]
            _save_raw(data)

    @classmethod
    def get_all_active_signups(cls) -> list[tuple[int, dict[str, Any]]]:
        with _lock:
            data = _load_raw()
            results = []
            for gid_str, gdata in data.items():
                signup = gdata.get("active_signup")
                if signup and not signup.get("closed", False):
                    try:
                        results.append((int(gid_str), signup))
                    except ValueError:
                        pass
            return results

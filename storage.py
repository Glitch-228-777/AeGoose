import json
import os
import threading

DATA_FILE = os.getenv("DATA_FILE", "data.json")

_DEFAULTS = {
    "appeal_counter": 0,
    "ebalooff": {},
    "warnings": {},
    "whitelist": {},
    "config": {},
}

_lock = threading.Lock()


def _read():
    if not os.path.exists(DATA_FILE):
        return dict(_DEFAULTS)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)
    for k, v in _DEFAULTS.items():
        data.setdefault(k, v if not isinstance(v, dict) else {})
    return data


def _write(data):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


_data = _read()


def save():
    with _lock:
        _write(_data)


def get(key, default=None):
    return _data.get(key, default)


def set_value(key, value):
    _data[key] = value
    save()


def next_appeal_number():
    with _lock:
        _data["appeal_counter"] = int(_data.get("appeal_counter", 0)) + 1
        _write(_data)
        return _data["appeal_counter"]


def get_ebalooff():
    return _data.setdefault("ebalooff", {})


def set_ebalooff(user_id, iso_until):
    _data.setdefault("ebalooff", {})[str(user_id)] = iso_until
    save()


def remove_ebalooff(user_id):
    existed = _data.setdefault("ebalooff", {}).pop(str(user_id), None)
    save()
    return existed is not None


def add_warning(guild_id, user_id, entry):
    g = _data.setdefault("warnings", {}).setdefault(str(guild_id), {})
    g.setdefault(str(user_id), []).append(entry)
    save()
    return len(g[str(user_id)])


def get_warnings(guild_id, user_id):
    return _data.get("warnings", {}).get(str(guild_id), {}).get(str(user_id), [])


def clear_warnings(guild_id, user_id):
    g = _data.get("warnings", {}).get(str(guild_id), {})
    count = len(g.get(str(user_id), []))
    g[str(user_id)] = []
    save()
    return count


_CONFIG_DEFAULTS = {
    "log_channel": None,
    "antispam_enabled": True,
    "message_limit": 8,
    "ping_limit": 6,
    "antispam_action": "delete",
    "antispam_timeout_minutes": 10,
}


def get_config(guild_id):
    cfg = dict(_CONFIG_DEFAULTS)
    cfg.update(_data.get("config", {}).get(str(guild_id), {}))
    return cfg


def set_config(guild_id, **kwargs):
    g = _data.setdefault("config", {}).setdefault(str(guild_id), {})
    g.update(kwargs)
    save()
    return get_config(guild_id)


def toggle_whitelist(guild_id, user_id, punishment: str):
    g = _data.setdefault("whitelist", {}).setdefault(str(guild_id), {})
    user_wl = g.setdefault(str(user_id), [])
    punishment = punishment.lower()
    if punishment in user_wl:
        user_wl.remove(punishment)
        added = False
    else:
        user_wl.append(punishment)
        added = True
    save()
    return added, user_wl


def get_whitelist(guild_id, user_id):
    return _data.get("whitelist", {}).get(str(guild_id), {}).get(str(user_id), [])


def is_whitelisted(guild_id, user_id, punishment: str) -> bool:
    user_wl = get_whitelist(guild_id, user_id)
    if not user_wl:
        return False
    punishment = punishment.lower()
    return "all" in user_wl or punishment in user_wl

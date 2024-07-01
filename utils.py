import json

def load_settings():
    settings = {}
    try:
        settings = json.load(open('Settings.json', 'r'))
    except:
        pass
    return settings

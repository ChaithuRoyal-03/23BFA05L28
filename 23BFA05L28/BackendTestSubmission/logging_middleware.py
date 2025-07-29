import requests

def log_event(stack, level, package, message):
    url = "http://127.0.0.1:5000/evaluation-service/logs"
    log_data = {
        "stack": stack,
        "level": level,
        "package": package,
        "message": message
    }
    try:
        response = requests.post(url, json=log_data)
        if response.ok:
            print("✅ Log created successfully:", response.json())
        else:
            print(f"❌ Failed to log: {response.status_code}")
    except Exception as e:
        print(f"❌ Error in logging: {e}") 
import requests, os
base = f"http://localhost:{os.getenv('PORT','8000')}"
print("Health:", requests.get(f"{base}/health").json())

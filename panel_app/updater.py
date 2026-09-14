import os
import requests
CURRENT_VERSION="1.4.0"
def check():
    url=os.environ.get("PANEL_UPDATE_MANIFEST_URL")
    if not url:return None
    response=requests.get(url,timeout=5);response.raise_for_status();data=response.json()
    return data if data.get("version") and data["version"]!=CURRENT_VERSION else None

import os,time
from .storage import APPDATA_DIR,json_load,json_save
CACHE_FILE=os.path.join(APPDATA_DIR,"community_catalog.json")
def save_catalog(items): json_save(CACHE_FILE,{"saved_at":time.time(),"items":items})
def load_catalog():
    data=json_load(CACHE_FILE,{})
    return data.get("items",[]),data.get("saved_at")

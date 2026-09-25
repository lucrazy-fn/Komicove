import os
from .storage import APPDATA_DIR,json_load,json_save
STATE_FILE=os.path.join(APPDATA_DIR,"reader_state.json")
MANUAL_PANELS_FILE=os.path.join(APPDATA_DIR,"manual_panels.json")
def load_state(content_key): return json_load(STATE_FILE,{}).get(content_key,{})
def save_state(content_key,**state):
    data=json_load(STATE_FILE,{}); current=data.get(content_key,{}); current.update(state); data[content_key]=current; json_save(STATE_FILE,data)
def load_manual_panels(content_key,page):
    return json_load(MANUAL_PANELS_FILE,{}).get(content_key,{}).get(str(page))
def save_manual_panels(content_key,page,regions):
    data=json_load(MANUAL_PANELS_FILE,{}); comic=data.setdefault(content_key,{})
    if regions is None: comic.pop(str(page),None)
    else: comic[str(page)]=[[round(float(v),6) for v in rect] for rect in regions]
    if not comic: data.pop(content_key,None)
    json_save(MANUAL_PANELS_FILE,data)

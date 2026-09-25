from pathlib import Path
def group_by_folder(paths):
    result={}
    for path in paths: result.setdefault(str(Path(path).parent),[]).append(path)
    return result

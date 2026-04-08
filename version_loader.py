# version_loader.py
from PySide6.QtCore import QObject, Signal
from minecraft_launcher_lib.utils import get_version_list

class VersionLoader(QObject):
    finished = Signal(list)
    error = Signal(str)

    def run(self):
        try:
            data = get_version_list()
            raw = data["versions"] if isinstance(data,dict) else data
            vers = []
            for v in raw:
                if isinstance(v,dict) and "id" in v: vers.append(v["id"])
                elif isinstance(v,str): vers.append(v)
            filt = []
            for v in vers:
                if v.count('.')<1: continue
                try:
                    parts = v.split('.'); major,minor,patch = int(parts[0]),int(parts[1]),int(parts[2]) if len(parts)>2 else 0
                    if major==1 and 12<=minor<=21 and not (minor==12 and patch<2) and not (minor==21 and patch>8):
                        filt.append(v)
                except: pass
            filt.sort(key=lambda s:[int(x) for x in s.split('.')], reverse=True)
            self.finished.emit(filt)
        except Exception as e:
            self.error.emit(str(e))

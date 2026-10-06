"""Bounded conservative detection. Automatic results never replace manual panels."""
from collections import OrderedDict, deque
from dataclasses import dataclass
import math
from threading import RLock
from concurrent.futures import CancelledError
from PIL import Image

DETECTOR_VERSION = 3
MAX_PANELS = 64


@dataclass(frozen=True)
class DetectionResult:
    regions: tuple
    fallback: bool
    confidence: float
    method: str


class DetectionCache:
    """Session-only metadata; never retains images."""
    def __init__(self, capacity=128, ai=None):
        self.capacity = max(1, capacity)
        self._items = OrderedDict()
        self._lock = RLock()
        self._ai = ai

    def detect(self, key, image, manga=False, force=False, cancel=None):
        key = (DETECTOR_VERSION, key, bool(manga))
        with self._lock:
            if not force and key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
        result = detect_result(image, manga, cancel=cancel)
        if self._ai is not None:
            result = self._ai.detect(image, result, manga=manga, cancel=cancel)
        _check(cancel)
        with self._lock:
            self._items[key] = result
            self._items.move_to_end(key)
            while len(self._items) > self.capacity:
                self._items.popitem(last=False)
        return result

    def clear(self):
        with self._lock:
            self._items.clear()

    def close(self):
        self.clear()
        if self._ai is not None:
            self._ai.close()


def reading_regions(width, height, manga=False):
    columns = 4 if width > height else 2
    halves = range(columns // 2)
    if manga:
        halves = reversed(list(halves))
    return [(max(0, x / columns - .06), max(0, y / 3 - .06),
             min(1, (x + 1) / columns + .06), min(1, (y + 1) / 3 + .06))
            for half in halves for y in range(3)
            for x in ([half * 2 + 1, half * 2] if manga else [half * 2, half * 2 + 1])]


def clean_regions(regions):
    """Filter automatic geometry only; manual order/storage are left untouched."""
    result = []
    for rect in regions:
        if len(rect) != 4 or not all(math.isfinite(v) for v in rect):
            continue
        l,t,r,b = (max(0.,min(1.,v)) for v in rect)
        area=(r-l)*(b-t)
        if r-l < .06 or b-t < .045 or area < .012:
            continue
        duplicate=False
        for a,c,d,e in result:
            intersection=max(0,min(r,d)-max(l,a))*max(0,min(b,e)-max(t,c))
            union=area+(d-a)*(e-c)-intersection
            if intersection/max(union,1e-9)>=.88 or max(abs(l-a),abs(t-c),abs(r-d),abs(b-e))<=.015:
                duplicate=True
                break
        if not duplicate:
            result.append((l,t,r,b))
        if len(result)>=MAX_PANELS:
            break
    return result


def order_regions(regions,manga=False,spread=False):
    """Anchor rows prevent tall panels from merging unrelated rows."""
    pending=sorted(regions,key=lambda r:(r[1],r[0]))
    if spread:
        left=[r for r in pending if (r[0]+r[2])/2<.5]
        right=[r for r in pending if (r[0]+r[2])/2>=.5]
        if left and right and all(r[2]<=.54 for r in left) and all(r[0]>=.46 for r in right):
            halves=(right,left) if manga else (left,right)
            return [r for half in halves for r in order_regions(half,manga)]
    ordered=[]
    while pending:
        anchor=pending[0]
        tolerance=min(.08,(anchor[3]-anchor[1])*.25)
        row=[r for r in pending if r[1]-anchor[1]<=tolerance]
        ordered.extend(sorted(row,key=lambda r:(r[0]+r[2])/2,reverse=manga))
        pending=[r for r in pending if r not in row]
    return ordered


def _check(cancel):
    if cancel is not None and cancel.is_set():
        raise CancelledError()


def _split(mask,width,height,cancel=None,threshold=.98,minimum_run=3):
    regions=[]
    def visit(l,t,r,b,depth=0):
        _check(cancel)
        if depth<5:
            for axis in (0,1):
                start,end=(t,b) if axis==0 else (l,r)
                span=end-start
                low,high=(l,r) if axis==0 else (t,b)
                run=best=cut=0
                for p in range(start+span//6,end-span//6):
                    _check(cancel)
                    count=(sum(mask[p*width+q] for q in range(low,high)) if axis==0
                           else sum(mask[q*width+p] for q in range(low,high)))
                    run=run+1 if count>=(high-low)*threshold else 0
                    if run>best:
                        best,cut=run,p-run//2
                if max(minimum_run,span//300 if minimum_run==1 else span//100)<=best<span/4:
                    boxes=((l,t,r,cut),(l,cut,r,b)) if axis==0 else ((l,t,cut,b),(cut,t,r,b))
                    for box in boxes:
                        visit(*box,depth+1)
                    return
        regions.append((l/width,t/height,r/width,b/height))
    visit(0,0,width,height)
    return clean_regions(regions)


def _components(mask,width,height,cancel=None):
    seen=bytearray(width*height)
    regions=[];foreground=len(mask)-sum(mask);kept=0
    for start in range(len(mask)):
        if start%1024==0:
            _check(cancel)
        if mask[start] or seen[start]:
            continue
        queue=deque([start]);seen[start]=1
        l=r=start%width;t=b=start//width;count=0
        while queue:
            if count%1024==0:
                _check(cancel)
            point=queue.popleft();x=point%width;y=point//width;count+=1
            l=min(l,x);r=max(r,x);t=min(t,y);b=max(b,y)
            for neighbor in (point-1 if x else -1,point+1 if x+1<width else -1,
                             point-width if y else -1,point+width if y+1<height else -1):
                if neighbor>=0 and not mask[neighbor] and not seen[neighbor]:
                    seen[neighbor]=1;queue.append(neighbor)
        area=(r-l+1)*(b-t+1)
        if count>=width*height*.012 and area>=width*height*.02 and count/area>=.18:
            rect=(l/width,t/height,(r+1)/width,(b+1)/height)
            if clean_regions([rect]):
                regions.append(rect);kept+=count
    if len(regions)>MAX_PANELS or kept<foreground*.65:
        return []
    return clean_regions(regions)


def detect_result(image,manga=False,cancel=None):
    _check(cancel)
    scale=min(1.,320/image.width,480/image.height)
    small=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))),Image.Resampling.NEAREST)
    try:
        rgb=small.convert('RGB')
        try:
            pixels=list(rgb.get_flattened_data() if hasattr(rgb,'get_flattened_data') else rgb.getdata())
        finally:
            rgb.close()
        width,height=small.size
    finally:
        small.close()
    white=bytearray(min(p)>235 for p in pixels)
    black=bytearray(max(p)<20 for p in pixels)
    masks=[white]
    edge=[y*width+x for y in range(height) for x in range(width)
          if x==0 or y==0 or x==width-1 or y==height-1]
    if sum(black[i] for i in edge)>=len(edge)*.6:
        masks.append(black)
    best=[];method='gutters';confidence=0.
    white_components=None
    for index,mask in enumerate(masks):
        split=[]
        for rect in _split(mask,width,height,cancel):
            l,t,r,b=rect
            x0,y0,x1,y1=round(l*width),round(t*height),round(r*width),round(b*height)
            area=(x1-x0)*(y1-y0)
            ink=sum(not mask[y*width+x] for y in range(y0,y1) for x in range(x0,x1))
            if ink>=width*height*.004 and ink>=area*.06:
                split.append(rect)
        components=_components(mask,width,height,cancel)
        if index==0:
            white_components=components
        candidates=components if len(components)>len(split) else split
        candidate_method='components' if candidates is components else 'gutters'
        score=(.78 if candidate_method=='components' else .94)-index*.10
        if len(candidates)>1 and (not best or score>confidence or len(candidates)>len(best) and score>=confidence-.08):
            best=candidates;method=candidate_method;confidence=score
    # Scanned paper and hairline black borders are not necessarily white gutters.
    neutral=bytearray(min(p)>185 and max(p)-min(p)<30 for p in pixels)
    for mask,threshold,score in ((neutral,.80,.66),(black,.90,.72)) if confidence<.84 else ():
        candidates=[]
        for rect in _split(mask,width,height,cancel,threshold=threshold,minimum_run=1):
            l,t,r,b=rect
            x0,y0,x1,y1=round(l*width),round(t*height),round(r*width),round(b*height)
            ink=sum(not mask[y*width+x] for y in range(y0,y1) for x in range(x0,x1))
            if ink>=width*height*.004 and ink>=(x1-x0)*(y1-y0)*.06:
                candidates.append(rect)
        if len(candidates)>1 and (not best or len(candidates)>len(best) and score>=confidence-.08):
            best=candidates;method='thin_borders';confidence=score
    if best:
        if any(min(a[2],b[2])>max(a[0],b[0]) and min(a[3],b[3])>max(a[1],b[1])
               for i,a in enumerate(best) for b in best[i+1:]):
            confidence=min(confidence,.68)
        return DetectionResult(tuple(order_regions(best,manga,width>height)),False,confidence,method)
    varied=max(max(p) for p in pixels)-min(min(p) for p in pixels)>40
    whole=varied and sum(white)<len(white)*.25 and len(white_components)==1
    regions=[(0.,0.,1.,1.)] if whole else reading_regions(*image.size,manga)
    return DetectionResult(tuple(regions),True,.30 if whole else .15,'whole_page' if whole else 'approximate')


def detect_regions(image,manga=False):
    """Compatible legacy API."""
    result=detect_result(image,manga)
    return list(result.regions),result.fallback

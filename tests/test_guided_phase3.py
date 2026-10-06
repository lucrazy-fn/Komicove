import math
import time
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw
from komicove_app.guided import DetectionCache, clean_regions, detect_result, order_regions


def layout(kind, size=(300, 400)):
    image=Image.new('RGB',(300,400),'black' if kind=='black_gutters' else 'white')
    d=ImageDraw.Draw(image)
    if kind in ('grid','black_gutters'):
        for y in (10,210):
            for x in (10,160):
                d.rectangle((x,y,x+130,y+180),fill='#345678')
    elif kind=='borderless':
        d.rectangle((10,10,120,140),fill='#8a314d')
        d.rectangle((175,25,290,155),fill='#235488')
        d.rectangle((15,230,285,390),fill='#3a6544')
    elif kind=='tilted':
        d.polygon([(10,10),(280,10),(10,360)],fill='#8a314d')
        d.polygon([(290,40),(290,390),(25,390)],fill='#235488')
    elif kind=='overlap':
        d.rectangle((0,0,240,270),fill='#235488')
        d.rectangle((80,150,299,399),fill='#8a314d')
    elif kind=='splash':
        d.rectangle((0,0,299,399),fill='#235488')
        d.ellipse((70,70,250,310),fill='#8a314d')
    elif kind=='noise':
        d.rectangle((10,10,290,160),fill='#345678')
        d.rectangle((10,230,290,390),fill='#345678')
        for x in range(20,290,30):
            d.rectangle((x,188,x+2,190),fill='black')
    elif kind in ('thin_gray','thin_black'):
        d.rectangle((0,0,299,399),fill='#345678')
        color='#cdcdcd' if kind=='thin_gray' else 'black'
        d.line((150,0,150,399),fill=color,width=1)
        d.line((0,200,299,200),fill=color,width=1)
    return image.resize(size,Image.Resampling.NEAREST)


@pytest.mark.parametrize('kind,count,fallback',[
    ('grid',4,False),('black_gutters',4,False),('borderless',3,False),
    ('tilted',2,False),('overlap',1,True),('splash',1,True),('noise',2,False),
    ('thin_gray',4,False),('thin_black',4,False),
])
def test_representative_layouts(kind,count,fallback):
    result=detect_result(layout(kind))
    assert len(result.regions)==count
    assert result.fallback==fallback
    assert 0<=result.confidence<=1
    assert (result.confidence<.5)==fallback
    assert clean_regions(result.regions)==list(result.regions)
    assert all(0<=l<r<=1 and 0<=t<b<=1 for l,t,r,b in result.regions)


def test_dedup_invalid_and_legitimate_overlap():
    rects=[(0,0,.5,.5),(.005,.003,.502,.499),(.3,.3,.8,.8),
           (0,0,.001,.2),(.5,.5,.4,.6),(math.nan,0,1,1)]
    assert clean_regions(rects)==[rects[0],rects[2]]


def test_order_western_manga_and_staggered_rows():
    western=order_regions([(0,.55,.45,1),(.55,.01,1,.45),(0,0,.45,.45),(.55,.56,1,1)])
    assert western==[(0,0,.45,.45),(.55,.01,1,.45),(0,.55,.45,1),(.55,.56,1,1)]
    assert order_regions(western,True)==[western[1],western[0],western[3],western[2]]
    spread=order_regions(western,False,True)
    assert spread==[western[0],western[2],western[1],western[3]]
    assert order_regions(western,True,True)==[western[1],western[3],western[0],western[2]]


def test_cache_reuse_force_eviction_and_no_images():
    cache=DetectionCache(2);image=layout('grid')
    with patch('komicove_app.guided.detect_result',wraps=detect_result) as detect:
        first=cache.detect(('comic-a',0),image)
        assert cache.detect(('comic-a',0),image) is first
        assert detect.call_count==1
        cache.detect(('comic-a',0),image,force=True)
        assert detect.call_count==2
        cache.detect(('comic-a',0),image,manga=True)
        cache.detect(('comic-b',0),image)
        assert len(cache._items)==2
        assert all(not hasattr(r,'image') for r in cache._items.values())
        cache.clear();assert not cache._items


def test_cancelled_detection_does_not_enter_cache():
    from threading import Event
    from concurrent.futures import CancelledError
    cancel=Event();cancel.set();cache=DetectionCache()
    with pytest.raises(CancelledError):
        cache.detect('obsolete',layout('grid'),cancel=cancel)
    assert not cache._items


def test_large_page_is_bounded_and_source_intact():
    image=layout('tilted',(3000,4000));before=image.getpixel((0,0))
    started=time.perf_counter();result=detect_result(image)
    assert len(result.regions)==2
    assert image.size==(3000,4000) and image.getpixel((0,0))==before
    assert time.perf_counter()-started<5


def test_legacy_manual_panels_round_trip_without_reordering(tmp_path,monkeypatch):
    from komicove_app import reader
    monkeypatch.setattr(reader,'MANUAL_PANELS_FILE',str(tmp_path/'panels.json'))
    original=[[.5,0,1,.5],[0,0,.5,.5]]
    reader.save_manual_panels('original-comic',2,original)
    assert reader.load_manual_panels('original-comic',2)==original
    detect_result(layout('grid'),True)
    assert reader.load_manual_panels('original-comic',2)==original

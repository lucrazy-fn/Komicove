import io
import json
import os
from pathlib import Path
import time
import tkinter as tk
import zipfile
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import CancelledError
from threading import Event

import pytest
from PIL import Image

from komicove_app.archive import SmartPageLoader


@pytest.fixture(scope='module')
def gui():
    root=tk.Tk();root.withdraw()
    yield root
    root.destroy()


def comic(path, count=1000):
    pages=[]
    for size in [(2400,3600),(3000,1600),(1200,6000)]:
        with Image.new('RGB',size,'white') as image:
            data=io.BytesIO(); image.save(data,'JPEG'); pages.append(data.getvalue())
    with zipfile.ZipFile(path,'w') as archive:
        for index in range(count):
            archive.writestr(f'{index:04}.jpg',pages[index%3])
    return path


def pump(root, condition, timeout=10):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        root.update()
        if condition():
            root.update_idletasks()
            return
        time.sleep(.005)
    assert condition()


def test_scaled_decode_does_not_populate_full_resolution_cache(tmp_path):
    loader=SmartPageLoader(comic(tmp_path/'large.cbz',3))
    try:
        for page in range(3):
            image,ratio=loader.get_scaled(page,600,Event())
            assert image.width<=600 and image.width*image.height<=8_000_000
            assert abs(image.height/image.width-ratio)<.01
            image.close()
        assert not loader._cache
        cancel=Event(); cancel.set()
        with pytest.raises(CancelledError):loader.get_scaled(0,600,cancel)
        # Other modes keep the existing original-image contract.
        assert loader.get_pil(0).size==(2400,3600)
    finally:loader.close()


def test_vertical_large_comic_virtualization_resume_and_cancellation(tmp_path,monkeypatch,gui):
    from komicove_app.reader_views import WebtoonViewer
    loader=SmartPageLoader(comic(tmp_path/'large.cbz'))
    root=gui
    errors=[]; root.report_callback_exception=lambda *args:errors.append(args)
    positions=[]; delays=[]; scheduled=[time.monotonic()]; running=[True]; peak_pages=0; peak_pixels=0
    def beat():
        now=time.monotonic(); delays.append(max(0,now-scheduled[0]-.016)); scheduled[0]=now
        if running[0]:root.after(16,beat)
    root.after(16,beat)
    viewer=None
    try:
        viewer=WebtoonViewer(root,loader,width=640,height=700,on_position=lambda *p:positions.append(p))
        pump(root,lambda:0 in viewer._loaded)
        for page in [10,300,600,20,990,200,500]:
            viewer._reflow((page,.35))
            pump(root,lambda p=page:p in viewer._loaded)
            first=viewer._position()[0]
            last=next((i for i in range(first,loader.count) if viewer._tops[i]>viewer.canvas.canvasy(viewer.canvas.winfo_height())),loader.count-1)
            assert all(first-1<=i<=last+1 for i in viewer._loaded)
            assert len(viewer._labels)<=last-first+4
            assert all(photo.width()<=viewer._tw for photo in viewer._photos.values())
            assert not loader._cache
            peak_pages=max(peak_pages,len(viewer._loaded))
            peak_pixels=max(peak_pixels,sum(image.width*image.height for image in viewer._images.values()))
        for _ in range(120):
            viewer._scroll(3);root.update();time.sleep(.008)
            peak_pages=max(peak_pages,len(viewer._loaded))
            peak_pixels=max(peak_pixels,sum(image.width*image.height for image in viewer._images.values()))
        viewer._reflow((500,.35)); pump(root,lambda:500 in viewer._loaded)
        # Stale native work must not reach Tk or persist its old page.
        entered,release=Event(),Event(); original=loader.get_scaled
        def delayed(page,width,cancel):
            if page==750:
                entered.set();release.wait(5)
            return original(page,width,cancel)
        monkeypatch.setattr(loader,'get_scaled',delayed)
        viewer._reflow((750,.1)); pump(root,entered.is_set)
        viewer._reflow((500,.35)); root.update(); viewer._check_visible()
        assert viewer._cancel.is_set()
        release.set(); pump(root,lambda:viewer._request is None or viewer._request[0]!=750)
        pump(root,lambda:500 in viewer._loaded)
        anchor=viewer._position(); ratio=viewer._ratios[anchor[0]]
        viewer.destroy(); viewer=None
        assert positions[-1][0]==anchor[0]
        assert abs(positions[-1][1]-anchor[1])<.01
        viewer=WebtoonViewer(root,loader,width=900,height=700,page=anchor[0],offset=anchor[1],ratio=ratio)
        pump(root,lambda:anchor[0] in viewer._loaded)
        assert viewer._position()[0]==anchor[0]
        assert abs(viewer._position()[1]-anchor[1])<.035
        assert max(delays)<1.0, f'UI stalled {max(delays):.3f}s'
        assert not errors
        if os.environ.get('KOMICOVE_PHASE7_REPORT'):
            samples=sorted(delays)
            Path(os.environ['KOMICOVE_PHASE7_REPORT']).write_text(json.dumps(dict(
                pages=1000,source_dimensions=['2400x3600','3000x1600','1200x6000'],
                peak_loaded_pages=peak_pages,peak_decoded_rgb_bytes=peak_pixels*3,
                heartbeat_p95_ms=samples[int(len(samples)*.95)]*1000,
                heartbeat_max_ms=max(samples)*1000,
                checks='viewport, bounded prefetch, screen resolution, cancellation, continuous scroll, resume'),indent=2)+'\n',encoding='utf-8')
    finally:
        running[0]=False
        if viewer:viewer.destroy()
        loader.close()


def test_pdf_vertical_renders_at_viewport_resolution(tmp_path):
    import pymupdf
    path=tmp_path/'comic.pdf'
    doc=pymupdf.open(); doc.new_page(width=1200,height=1800); doc.save(path); doc.close()
    loader=SmartPageLoader(path)
    try:
        image,ratio=loader.get_scaled(0,600,Event())
        assert image.size==(600,900) and ratio==1.5
        assert not loader._cache
        image.close()
    finally:loader.close()


def test_external_extraction_can_be_cancelled():
    from komicove_app.archive import run_7zip
    cancel=Event()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future=executor.submit(run_7zip,sys.executable,['-c','import time; time.sleep(10)'],cancel)
        time.sleep(.15); start=time.monotonic(); cancel.set()
        with pytest.raises(CancelledError):future.result(timeout=2)
        assert time.monotonic()-start<1


def test_reader_exit_reopens_vertical_mode_and_exact_position(tmp_path,gui):
    from komicove_app.reader_views import EmbeddedReader
    from komicove_app.reader import load_state
    from komicove_app.storage import save_prefs, get_progress_page
    from komicove_app.design.icons import clear_icon_cache
    path=comic(tmp_path/'resume.cbz',30)
    root=gui;root.deiconify(); root.geometry('1000x800'); clear_icon_cache()
    errors=[]; root.report_callback_exception=lambda *args:errors.append(args)
    save_prefs(reader_guided=False)
    reader=None
    try:
        reader=EmbeddedReader(root,str(path),SmartPageLoader(path)); reader.pack(fill='both',expand=True)
        pump(root,lambda:reader._cv.winfo_width()>100)
        reader._open_webtoon(); viewer=reader._webtoon
        pump(root,lambda:0 in viewer._loaded)
        viewer._reflow((12,.4)); pump(root,lambda:12 in viewer._loaded)
        anchor=viewer._position(); reader._close()
        assert get_progress_page(str(path))==12
        assert load_state(reader._content_key)['vertical_active']
        reader=EmbeddedReader(root,str(path),SmartPageLoader(path)); reader.pack(fill='both',expand=True)
        pump(root,lambda:getattr(reader,'_webtoon',None) is not None and 12 in reader._webtoon._loaded)
        assert reader._webtoon._position()[0]==anchor[0]
        assert abs(reader._webtoon._position()[1]-anchor[1])<.03
        reader._webtoon.destroy()
        assert not load_state(reader._content_key)['vertical_active']
        assert reader._idx==12
        reader._close(); reader=None
        assert not errors
    finally:
        if reader and not reader._destroyed:reader._close()
        clear_icon_cache(); root.withdraw()

"""Optional offline provider. External model weights have their own license.

No network, automatic downloads, manual-panel writes, or arbitrary model loading.
Only the reviewed, SHA256-pinned Inkwell model is accepted.
"""
from concurrent.futures import CancelledError
import hashlib
import logging
import math
import os
from pathlib import Path
import sys
from threading import Event, Lock, Thread

from PIL import Image
from .guided import DetectionResult, clean_regions, order_regions, _check

MODEL_SHA256 = 'f240e1296efd048126b26ea4ffeddc97d7c3aa667a37e3127c2afc6d5e9b9578'
MODEL_BYTES = 12256396
MODEL_SIZE = 640
log = logging.getLogger('komicove.guided_ai')


def _runtime_defaults():
    # Preprocessing is elementwise, not BLAS. Avoid unused native thread stacks
    # before the first NumPy/ORT import, without overriding user configuration.
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')


def overlap(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0]))*max(0, min(a[3], b[3])-max(a[1], b[1]))
    return intersection/max(1e-9, (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)


def decode_rows(rows, transform):
    if len(rows) != 5 or not 0 < len(rows[0]) <= 10000 or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError('Unsupported detector output')
    left, top, width, height = transform
    candidates = []
    for index, score in enumerate(rows[4]):
        if not math.isfinite(score) or not .25 <= score <= 1:
            continue
        cx, cy, w, h = (float(rows[channel][index]) for channel in range(4))
        if not all(math.isfinite(value) for value in (cx,cy,w,h)) or w <= 0 or h <= 0:
            continue
        rect = ((cx-w/2-left)/width,(cy-h/2-top)/height,(cx+w/2-left)/width,(cy+h/2-top)/height)
        valid = clean_regions([rect])
        if valid:
            candidates.append((float(score),valid[0]))
    kept = []
    for score, rect in sorted(candidates, reverse=True)[:300]:
        if not any(overlap(rect, prior) > .5 for _,prior in kept):
            kept.append((score,rect))
            if len(kept) == 64:
                break
    return kept


def combine(kept, baseline, manga=False, spread=False):
    """Never claim a small isolated detection covers an entire page."""
    if not kept:
        if not baseline.fallback and baseline.confidence >= .84:
            return baseline
        return DetectionResult(((0.,0.,1.,1.),),True,.30,'ai_whole_page')
    regions = [rect for _,rect in kept]
    if not baseline.fallback and baseline.confidence >= .84 and len(baseline.regions) > len(regions):
        return baseline
    if len(regions) == 1:
        l,t,r,b = regions[0]
        if (r-l)*(b-t) < .5:
            # A full-width header panel can coexist with a large splash below.
            # The completion is explicitly approximate, not a second AI detection.
            if r-l >= .75 and t <= .06 and .08 <= b <= .45:
                regions.append((0.,min(1.,b+.005),1.,1.))
                return DetectionResult(tuple(order_regions(regions,manga,spread)),True,.40,'ai_partial')
            return DetectionResult(((0.,0.,1.,1.),),True,.30,'ai_partial')
    score = sum(score for score,_ in kept)/len(kept)
    return DetectionResult(tuple(order_regions(regions,manga,spread)),False,score,'ai_local')


class LocalPanelAI:
    def __init__(self, path):
        self.path = Path(path)
        self._session = None
        self._input = None
        self._disabled = False
        self._closed = False
        self._lock = Lock()
        self._active = None

    @classmethod
    def available(cls):
        if os.environ.get('KOMICOVE_GUIDED_AI','1') == '0':
            return None
        root = Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
        path = root/'local_models'/'inkwell.onnx'
        if 'KOMICOVE_PANEL_MODEL' in os.environ:
            path = Path(os.environ['KOMICOVE_PANEL_MODEL'])
        elif not path.is_file() and getattr(sys,'frozen',False):
            path = Path(getattr(sys,'_MEIPASS',root))/'local_models'/'inkwell.onnx'
        return cls(path) if path.is_file() else None

    def _open(self, cancel):
        import onnxruntime as ort
        if self.path.stat().st_size != MODEL_BYTES:
            raise ValueError('Model size mismatch')
        digest = hashlib.sha256()
        with self.path.open('rb') as source:
            while chunk := source.read(1024*1024):
                _check(cancel)
                digest.update(chunk)
        if digest.hexdigest() != MODEL_SHA256:
            raise ValueError('Model checksum mismatch')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.log_severity_level = 3
        session = ort.InferenceSession(str(self.path),sess_options=options,providers=['CPUExecutionProvider'])
        inputs = session.get_inputs()
        expected = [1,3,640,640]
        if len(inputs)!=1 or len(inputs[0].shape)!=4 or any(isinstance(v,int) and v!=expected[i] for i,v in enumerate(inputs[0].shape)):
            raise ValueError('Model input mismatch')
        _check(cancel)
        return session

    def detect(self, image, baseline, manga=False, cancel=None):
        _check(cancel)
        while not self._lock.acquire(timeout=.02):
            _check(cancel)
            if self._closed:
                return baseline
        try:
            if self._closed or self._disabled:
                return baseline
            _runtime_defaults()
            import numpy as np
            import onnxruntime as ort
            if self._session is None:
                self._session = self._open(cancel)
            if self._input is None:
                self._input = np.empty((1,3,MODEL_SIZE,MODEL_SIZE),dtype=np.float32)
            tensor = self._input
            _check(cancel)
            scale = min(MODEL_SIZE/image.width,MODEL_SIZE/image.height)
            width,height = max(1,round(image.width*scale)),max(1,round(image.height*scale))
            left,top = (MODEL_SIZE-width)//2,(MODEL_SIZE-height)//2
            with image.resize((width,height),Image.Resampling.BILINEAR) as small, small.convert('RGB') as resized:
                with Image.new('RGB',(MODEL_SIZE,MODEL_SIZE),(114,114,114)) as canvas:
                    canvas.paste(resized,(left,top))
                    # Reuse the contiguous NCHW input; avoid three float copies.
                    np.copyto(tensor[0],np.asarray(canvas).transpose(2,0,1),casting='unsafe')
                    np.divide(tensor,np.float32(255.),out=tensor)
            _check(cancel)
            options = ort.RunOptions()
            self._active = options
            finished = Event()
            def cancel_run():
                while not finished.wait(.02):
                    if self._closed or cancel is not None and cancel.is_set():
                        options.terminate = True
                        return
            monitor = Thread(target=cancel_run,name='guided-ai-cancel',daemon=True)
            monitor.start()
            try:
                output = self._session.run(None,{self._session.get_inputs()[0].name:tensor},options)[0]
            finally:
                finished.set()
                monitor.join()
                self._active = None
            _check(cancel)
            if self._closed:
                raise CancelledError()
            if output.ndim != 3 or output.shape[0]!=1:
                raise ValueError('Model output mismatch')
            kept = decode_rows(output[0],(left,top,width,height))
            return combine(kept,baseline,manga,image.width>image.height)
        except CancelledError:
            raise
        except Exception as exc:
            _check(cancel)
            if self._closed:
                raise CancelledError() from None
            self._disabled = True
            self._session = None
            self._input = None
            # Do not expose archive/model paths or native exception contents.
            log.warning('Local panel AI unavailable (%s); using existing detector',type(exc).__name__)
            return baseline
        finally:
            if self._closed:
                self._session = None
                self._input = None
            self._lock.release()

    def close(self):
        self._closed = True
        active = self._active
        if active is not None:
            try:
                active.terminate = True
            except RuntimeError:
                pass  # The completed native run may already be releasing its options.
        if self._lock.acquire(blocking=False):
            try:
                self._session = None
                self._input = None
            finally:
                self._lock.release()

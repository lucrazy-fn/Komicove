from concurrent.futures import CancelledError
from threading import Event
from unittest.mock import patch
import math

from PIL import Image
import pytest

from komicove_app.guided import DetectionCache, DetectionResult
from komicove_app.guided_ai import LocalPanelAI, combine, decode_rows, _runtime_defaults


def baseline(fallback=True):
    return DetectionResult(((0.,0.,1.,1.),),fallback,.3 if fallback else .94,'whole_page')


def test_neural_decode_nms_and_invalid_rows():
    rows=[[160,160,float('nan')],[160,160,160],[300,300,50],[300,300,50],[.9,.8,.95]]
    kept=decode_rows(rows,(0,0,640,640))
    assert len(kept)==1 and kept[0][0]==.9
    with pytest.raises(ValueError):decode_rows([[1]],(0,0,640,640))
    with pytest.raises(ValueError):decode_rows([[1],[1],[1],[1],[]],(0,0,640,640))


def test_letterbox_geometry_and_tiny_noise():
    kept=decode_rows([[320,320],[320,320],[200,1],[200,1],[.8,.8]],(160,0,320,640))
    assert len(kept)==1
    assert kept[0][1]==(.1875,.34375,.8125,.65625)


def test_partial_header_completes_only_as_indicated_fallback():
    result=combine([(.9,(.02,.0,.98,.16))],baseline())
    assert result.fallback and result.method=='ai_partial'
    assert len(result.regions)==2 and result.regions[1][1]>.16
    assert result.confidence<.5


def test_empty_splash_and_small_isolated_region():
    assert combine([],baseline()).regions==((0.,0.,1.,1.),)
    assert combine([(.9,(.1,.2,.4,.5))],baseline()).fallback
    assert combine([(.9,(0.,0.,1.,1.))],baseline()).method=='ai_local'


def test_confident_heuristic_and_order_are_preserved():
    good=DetectionResult(((0.,0.,.5,.5),(.5,0.,1.,.5)),False,.94,'gutters')
    assert combine([],good) is good
    assert combine([(.8,(0.,0.,1.,1.))],good) is good
    boxes=[(.8,good.regions[0]),(.9,good.regions[1])]
    assert combine(boxes,baseline(),True).regions==tuple(reversed(good.regions))
    assert combine(boxes,baseline(),False).regions==good.regions


def test_checksum_failure_and_missing_runtime_are_safe(tmp_path):
    model=tmp_path/'invalid.onnx';model.write_bytes(b'invalid')
    ai=LocalPanelAI(model)
    with Image.new('RGB',(200,300)) as image:
        with patch.object(ai,'_open',side_effect=ValueError('bad checksum')):
            assert ai.detect(image,baseline()).fallback
            assert ai._disabled
    ai.close();assert ai._session is None


def test_cancelled_provider_never_populates_cache():
    class CancelledProvider:
        def detect(self,*args,**kwargs):raise CancelledError()
        def close(self):pass
    cache=DetectionCache(ai=CancelledProvider())
    with Image.new('RGB',(200,300)) as image:
        with pytest.raises(CancelledError):cache.detect('obsolete',image)
    assert not cache._items


def test_provider_cache_force_and_close():
    class Provider:
        calls=0;closed=False
        def detect(self,*args,**kwargs):self.calls+=1;return baseline()
        def close(self):self.closed=True
    provider=Provider();cache=DetectionCache(ai=provider)
    with Image.new('RGB',(200,300)) as image:
        first=cache.detect('page',image)
        assert cache.detect('page',image) is first and provider.calls==1
        cache.detect('page',image,force=True);assert provider.calls==2
    cache.close();assert provider.closed and not cache._items


def test_opt_out_does_not_load_a_model(monkeypatch):
    monkeypatch.setenv('KOMICOVE_GUIDED_AI','0')
    assert LocalPanelAI.available() is None


def test_frozen_provider_finds_bundled_model_and_preserves_adjacent_override(tmp_path, monkeypatch):
    import sys
    monkeypatch.setenv('KOMICOVE_GUIDED_AI', '1')
    monkeypatch.delenv('KOMICOVE_PANEL_MODEL', raising=False)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path/'Komicove.exe'))
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path/'_internal'), raising=False)
    bundled = tmp_path/'_internal'/'local_models'/'inkwell.onnx'
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b'fixture')
    assert LocalPanelAI.available().path == bundled
    adjacent = tmp_path/'local_models'/'inkwell.onnx'
    adjacent.parent.mkdir()
    adjacent.write_bytes(b'override fixture')
    assert LocalPanelAI.available().path == adjacent
    monkeypatch.setenv('KOMICOVE_PANEL_MODEL', str(tmp_path/'missing.onnx'))
    assert LocalPanelAI.available() is None
    monkeypatch.setenv('KOMICOVE_PANEL_MODEL', str(bundled))
    assert LocalPanelAI.available().path == bundled


def test_cancel_before_loading_keeps_source_intact():
    ai=LocalPanelAI('not-used.onnx');cancel=Event();cancel.set()
    with Image.new('RGB',(200,300)) as image:
        with pytest.raises(CancelledError):ai.detect(image,baseline(),cancel=cancel)
        assert image.size==(200,300) and ai._session is None


def test_preprocessing_thread_default_preserves_explicit_configuration(monkeypatch):
    monkeypatch.delenv('OPENBLAS_NUM_THREADS',raising=False)
    _runtime_defaults()
    assert __import__('os').environ['OPENBLAS_NUM_THREADS']=='1'
    monkeypatch.setenv('OPENBLAS_NUM_THREADS','4')
    _runtime_defaults()
    assert __import__('os').environ['OPENBLAS_NUM_THREADS']=='4'


def test_input_buffer_is_identical_reused_and_released():
    np=pytest.importorskip('numpy')
    pytest.importorskip('onnxruntime')
    class Input:
        name='images'
    class Session:
        def get_inputs(self):return [Input()]
        def run(self,outputs,feeds,options):
            self.tensor=feeds['images']
            return [np.zeros((1,5,1),dtype=np.float32)]
    ai=LocalPanelAI('not-loaded.onnx');ai._session=Session()
    with Image.new('RGB',(200,300),(17,129,253)) as image:
        ai.detect(image,baseline())
        first=ai._input
        width,height=427,640
        with image.resize((width,height),Image.Resampling.BILINEAR) as resized:
            with Image.new('RGB',(640,640),(114,114,114)) as canvas:
                canvas.paste(resized,((640-width)//2,0))
                expected=np.asarray(canvas,dtype=np.float32).transpose(2,0,1)[None].copy()/255.
        np.testing.assert_array_equal(first,expected)
        assert first.flags.c_contiguous
        ai.detect(image,baseline())
        assert ai._input is first
    ai.close()
    assert ai._input is None and ai._session is None

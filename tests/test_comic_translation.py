import json
import sys
import zipfile
from io import BytesIO
from threading import Event
from concurrent.futures import CancelledError
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from komicove_app import comic_translation as comic
from komicove_app.translation_views import draw_translation_overlay, _source_font_size, _styled_layout, _comic_font
from komicove_app.archive import ArchiveBackend
from tools.translation_fixture import page as authorial_page


def test_ocr_lines_and_cancel(monkeypatch):
    tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
           "5\t1\t1\t1\t1\t1\t10\t20\t20\t10\t82\tOlá\n"
           "5\t1\t1\t1\t1\t2\t32\t20\t25\t10\t78\tmundo\n").encode()
    class Process:
        returncode = 0
        def communicate(self, input=None, timeout=None):
            assert input.startswith(b"\x89PNG")
            assert timeout == .1
            return tsv, b""
    monkeypatch.setattr(comic.shutil, "which", lambda _: "tesseract")
    def launch(*args, **kwargs):
        assert args[0][1:3] == ["stdin", "stdout"]
        assert kwargs["stdin"] is comic.subprocess.PIPE
        assert kwargs["stdout"] is comic.subprocess.PIPE
        assert kwargs["stderr"] is comic.subprocess.PIPE
        return Process()
    monkeypatch.setattr(comic.subprocess, "Popen", launch)
    rows = comic.recognize(Image.new("RGB", (100, 100), "white"), "por")
    horizontal = next(row for row in rows if row.box[0] == pytest.approx(.1))
    assert horizontal.original == "Olá mundo"
    assert horizontal.confidence == pytest.approx(.8)
    assert horizontal.box == pytest.approx((.1, .2, .57, .3))
    stopped = Event(); stopped.set()
    with pytest.raises(CancelledError):
        comic.recognize(Image.new("RGB", (100, 100)), cancel=stopped)


def test_ocr_timeout_stops_child(monkeypatch):
    class Process:
        returncode = None
        stopped = False
        def communicate(self, input=None, timeout=None):
            if self.stopped:
                return b"", b""
            raise comic.subprocess.TimeoutExpired("tesseract", timeout)
        def kill(self): self.stopped = True
    process = Process()
    ticks = iter((0, 0, 61))
    monkeypatch.setattr(comic.shutil, "which", lambda _: "tesseract")
    monkeypatch.setattr(comic.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(comic, "time", SimpleNamespace(monotonic=lambda: next(ticks), sleep=lambda _: None))
    with pytest.raises(comic.TranslationError, match="ocr_timeout"):
        comic._ocr_once(Image.new("RGB", (10, 10)), "eng", 11)
    assert process.stopped


def test_ocr_does_not_require_a_writable_temporary_directory(monkeypatch):
    tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
           "5\t1\t1\t1\t1\t1\t1\t1\t8\t8\t90\tHi\n").encode()
    class Process:
        returncode = 0
        def communicate(self, input=None, timeout=None):
            return tsv, b""
    monkeypatch.setattr(comic.shutil, "which", lambda _: "tesseract")
    monkeypatch.setattr(comic.subprocess, "Popen", lambda *a, **k: Process())
    monkeypatch.setattr(comic.tempfile, "TemporaryDirectory",
                        lambda *a, **k: pytest.fail("OCR wrote a temporary file"))
    rows = comic._ocr_once(Image.new("RGB", (10, 10), "white"), "eng", 11)
    assert rows[0].original == "Hi"


def test_ocr_tsv_treats_quotes_as_text_instead_of_joining_rows(monkeypatch):
    tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
           "5\t1\t1\t1\t1\t1\t1\t1\t20\t8\t91\tSAY\"\n"
           "5\t1\t1\t1\t2\t1\t1\t12\t24\t8\t92\tHELLO\n").encode()

    class Process:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            return tsv, b""

    monkeypatch.setattr(comic.shutil, "which", lambda _: "tesseract")
    monkeypatch.setattr(comic.subprocess, "Popen", lambda *args, **kwargs: Process())

    rows = comic._ocr_once(Image.new("RGB", (100, 100), "white"), "eng", 11)

    assert [row.original for row in rows] == ['SAY"', "HELLO"]


def test_translation_candidate_accepts_readable_dialogue_and_rejects_short_noise():
    dialogue = comic.TextRegion((.1, .1, .4, .2), "RUN! THIS WAY!", .72)
    sound_effect = comic.TextRegion((.1, .2, .4, .3), "KRAKOOM", .80)
    noise = comic.TextRegion((.1, .3, .2, .4), "AX", .89)
    uncertain = comic.TextRegion((.1, .4, .4, .5), "I THINK WE SHOULD GO", .64)

    assert comic.auto_translation_candidate(dialogue)
    assert comic.auto_translation_candidate(sound_effect)
    assert not comic.auto_translation_candidate(noise)
    assert not comic.auto_translation_candidate(uncertain)


@pytest.mark.skipif(not comic.tesseract_available(), reason="Tesseract is not installed")
def test_uncertain_balloon_gets_high_resolution_ocr_retry():
    source = authorial_page("HELLO, HERO!")
    found = comic.recognize(source, "eng")
    greeting = next(row for row in found if "HELLO" in row.original)
    assert "HERO" in greeting.original
    assert greeting.confidence >= .7
    tilted = next(row for row in found if "RUN!" in row.original)
    assert -18 <= tilted.angle <= -6
    assert not comic.auto_translation_candidate(tilted)
    greeting.translated = "Olá, herói!"
    result = draw_translation_overlay(source, [greeting], (0, 0, source.width, source.height))
    assert result.crop((135, 100, 195, 340)).tobytes() == source.crop((135, 100, 195, 340)).tobytes()


@pytest.mark.parametrize("provider", ["openai", "anthropic", "xai", "groq", "openrouter", "gemini"])
def test_provider_text_only_payload_and_errors(monkeypatch, provider):
    calls = []
    class Response:
        status_code = 200
        ok = True
        def json(self):
            if provider == "anthropic":
                return {"content": [{"type": "text", "text": '{"0":"Hello"}'}]}
            if provider == "gemini":
                return {"candidates": [{"content": {"parts": [{"text": '{"0":"Hello"}'}]}}]}
            return {"choices": [{"message": {"content": '{"0":"Hello"}'}}]}
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr(comic.requests, "post", post)
    rows = [comic.TextRegion((.1, .1, .4, .2), "Olá", .9)]
    comic.translate_remote(rows, "pt", "en", provider=provider, model="user-selected", key="private")
    assert rows[0].translated == "Hello"
    url, request = calls[0]
    assert url.startswith("https://")
    assert "Olá" in json.dumps(request["json"], ensure_ascii=False)
    assert "base64" not in json.dumps(request["json"])
    assert "inline_data" not in json.dumps(request["json"])
    assert "image_url" not in json.dumps(request["json"])
    assert "private" not in json.dumps(request["json"])
    if provider == "gemini":
        assert url.endswith("/models/user-selected:generateContent")
        assert request["headers"]["x-goog-api-key"] == "private"
        assert "Authorization" not in request["headers"]
    class Rejected:
        status_code = 429
        ok = False
    monkeypatch.setattr(comic.requests, "post", lambda *a, **k: Rejected())
    with pytest.raises(comic.TranslationError, match="quota_or_rate_limit"):
        comic.test_connection(provider, "user-selected", "private")


def test_compatible_provider_requires_explicit_https_endpoint(monkeypatch):
    with pytest.raises(comic.TranslationError, match="invalid_endpoint"):
        comic.endpoint("compatible")
    assert comic.endpoint("compatible", "https://example.test/v1") == "https://example.test/v1"
    with pytest.raises(comic.TranslationError, match="invalid_endpoint"):
        comic.endpoint("compatible", "http://example.test/v1")


@pytest.mark.parametrize("provider,model", [
    ("openai", "gpt-5.4-mini"), ("anthropic", "claude-sonnet-5-5"),
    ("xai", "grok-4.7"), ("gemini", "gemini-3.8-flash"),
])
def test_image_is_sent_only_with_explicit_input_and_supported_model(monkeypatch, provider, model):
    sent = []
    def request(*args, **kwargs):
        sent.append(args[4])
        return '{"0":"Hello"}'
    monkeypatch.setattr(comic, "_request", request)
    page = Image.new("RGB", (80, 80), "white")
    rows = [comic.TextRegion((.1, .1, .4, .2), "Olá", .9)]
    comic.translate_remote(rows, "pt", "en", provider=provider, model=model, key="dummy")
    assert "base64" not in json.dumps(sent[-1])
    rows[0].translation_attempted = False
    comic.translate_remote(rows, "pt", "en", provider=provider, model=model, key="dummy", image=page)
    assert "base64" in json.dumps(sent[-1]) or "inline_data" in json.dumps(sent[-1])


def test_empty_translation_is_not_billed_twice(monkeypatch):
    calls = []
    class Response:
        ok = True
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": '{"0":""}'}}]}
    monkeypatch.setattr(comic.requests, "post", lambda *args, **kwargs: (calls.append(1), Response())[1])
    rows = [comic.TextRegion((.1, .1, .4, .2), "[illegible]", .9)]
    comic.translate_remote(rows, "auto", "pt", provider="openai", model="chosen", key="private")
    comic.translate_remote(rows, "auto", "pt", provider="openai", model="chosen", key="private")
    assert rows[0].translation_attempted and rows[0].translated == ""
    assert len(calls) == 1


def test_uncertain_ocr_waits_for_manual_correction_before_remote_charge(monkeypatch):
    calls = []
    monkeypatch.setattr(comic, "_request", lambda *args, **kwargs: (calls.append(1), '{"0":"Pare!"}')[1])
    row = comic.TextRegion((.1, .1, .4, .2), "P@R?", .3)
    comic.translate_remote([row], "en", "pt", provider="openai", model="chosen", key="private")
    assert calls == [] and not row.translation_attempted
    row.original = "STOP!"
    row.manual_original = True
    comic.translate_remote([row], "en", "pt", provider="openai", model="chosen", key="private")
    assert calls == [1] and row.translated == "Pare!"


def test_remote_response_must_match_all_regions_before_any_change(monkeypatch):
    rows = [comic.TextRegion((.1, .1, .3, .2), "First", .9),
            comic.TextRegion((.6, .1, .8, .2), "Second", .9)]
    monkeypatch.setattr(comic, "_request", lambda *args, **kwargs: '{"0":"Primeiro"}')
    with pytest.raises(comic.TranslationError, match="invalid_provider_response"):
        comic.translate_remote(rows, "en", "pt", provider="openai", model="chosen", key="dummy")
    assert all(not row.translation_attempted and not row.translated for row in rows)


def test_previous_page_context_and_remote_cache_revision(monkeypatch, tmp_path):
    monkeypatch.setattr(comic, "_CACHE", tmp_path / "cache")
    monkeypatch.setattr(comic, "_CORRECTIONS", tmp_path / "corrections")
    image = Image.new("RGB", (40, 40), "white")
    current = [comic.TextRegion((.1, .1, .5, .2), "He returned", .9, "Ele voltou")]
    args = ("book", 1, image, "en", "pt", "openai", "chosen")
    comic.write_cache(*args, current)
    assert comic.read_cache(*args) is not None
    comic.write_ocr_cache("book", 0, image, "eng", False,
                          [comic.TextRegion((.1, .1, .4, .2), "The captain left", .9)])
    assert comic.previous_page_context("book", 1) == ["The captain left"]
    assert comic.read_cache(*args) is None
    comic.write_cache(*args, current)
    prior = comic.TextRegion((.1, .1, .4, .2), "The captain returned", .9)
    prior.manual_original = True
    comic.save_correction("book", 0, prior)
    assert comic.previous_page_context("book", 1) == ["The captain returned"]
    assert comic.read_cache(*args) is None
    local = ("book", 1, image, "en", "pt", "local", "")
    comic.write_cache(*local, current)
    assert comic.read_cache(*local) is not None


def test_local_glossary_matches_whole_expression_only():
    words = {"Captain Nova": "Capitã Nova"}
    assert comic.glossary_exact_match("  captain   NOVA  ", words) == "Capitã Nova"
    assert comic.glossary_exact_match("Captain Nova returned", words) is None


def test_brazilian_portuguese_is_distinct_from_european_portuguese():
    european = ("Isto está a mudar. Se precisares, podes falar com a tua equipa "
                "e ver o ficheiro no ecrã.")
    assert comic.brazilian_portuguese(european) == (
        "Isso está mudando. Se precisar, pode falar com a sua equipe e ver o arquivo na tela.")
    assert comic.brazilian_portuguese("Agradeço por não falares. Podes olhar-te ao espelho.") == (
        "Agradeço por não falar. Pode se olhar no espelho.")
    assert comic.brazilian_portuguese("Chegou a isto, meu. O meu carro ficou.") == (
        "Chegou a isso, cara. O meu carro ficou.")
    assert comic.translation_language_name("pt-BR") == "Brazilian Portuguese (pt-BR)"
    assert comic.translation_language_name("pt-PT") == "European Portuguese (pt-PT)"
    assert comic._model_language("pt-BR") == comic._model_language("pt-PT") == "pt"


def test_export_cbz_preserves_original_order_and_metadata(tmp_path):
    original = tmp_path / "autoral.cbz"
    destination = tmp_path / "autoral-traduzido.cbz"
    page = Image.new("RGB", (80, 60), "white")
    stream = BytesIO(); page.save(stream, format="PNG")
    with zipfile.ZipFile(original, "w") as archive:
        archive.writestr("art/", b"")
        archive.writestr("ComicInfo.xml", "<ComicInfo><Title>Autoral</Title></ComicInfo>")
        archive.writestr("art/001.png", stream.getvalue())
        archive.writestr("art/002.png", stream.getvalue())
    original_bytes = original.read_bytes()
    backend = ArchiveBackend(original)
    try:
        def render(index, data):
            if index:
                return None
            translated = Image.open(BytesIO(data)).convert("RGB")
            ImageDraw.Draw(translated).text((10, 10), "OLA", fill="black")
            result = BytesIO(); translated.save(result, format="PNG")
            return result.getvalue()
        assert comic.export_cbz_copy(backend, destination, render) == 1
    finally:
        backend.close()
    assert original.read_bytes() == original_bytes
    with zipfile.ZipFile(destination) as archive:
        assert archive.namelist() == ["art/", "ComicInfo.xml", "art/001.png", "art/002.png"]
        assert archive.read("ComicInfo.xml") == b"<ComicInfo><Title>Autoral</Title></ComicInfo>"
        assert archive.read("art/001.png") != stream.getvalue()
        assert archive.read("art/002.png") == stream.getvalue()
    invalid = ArchiveBackend(original)
    try:
        with pytest.raises(comic.TranslationError, match="invalid_export_path"):
            comic.export_cbz_copy(invalid, original, lambda *_: None)
    finally:
        invalid.close()


def test_export_pdf_pages_have_reopenable_image_names(tmp_path):
    from types import SimpleNamespace

    source = tmp_path / "autoral.pdf"
    source.write_bytes(b"source remains unchanged")
    image = BytesIO()
    Image.new("RGB", (60, 40), "white").save(image, format="PNG")
    archive = SimpleNamespace(path=source, kind="pdf", names=["page_0"], count=1,
                              read_page=lambda index: image.getvalue())
    destination = tmp_path / "translated.cbz"
    assert comic.export_cbz_copy(archive, destination, lambda *_: None) == 0
    reopened = ArchiveBackend(destination)
    try:
        assert reopened.count == 1
        assert reopened.names == ["page_0.png"]
    finally:
        reopened.close()
    assert source.read_bytes() == b"source remains unchanged"


def test_connection_requires_provider_content(monkeypatch):
    monkeypatch.setattr(comic, "_request", lambda *args, **kwargs: "  ")
    with pytest.raises(comic.TranslationError, match="invalid_provider_response"):
        comic.test_connection("openai", "chosen", "private")


def test_cache_and_manual_correction_survive_provider_change(monkeypatch, tmp_path):
    monkeypatch.setattr(comic, "_CACHE", tmp_path / "cache")
    monkeypatch.setattr(comic, "_CORRECTIONS", tmp_path / "corrections")
    image = Image.new("RGB", (40, 40), "white")
    region = comic.TextRegion((.1, .1, .4, .2), "unclear", .3, "wrong")
    comic.write_ocr_cache("book", 2, image, "eng", False, [region])
    assert comic.read_ocr_cache("book", 2, image, "eng", False)[0].original == "unclear"
    assert comic.read_ocr_cache("book", 2, image, "por", False) is None
    assert comic.read_ocr_cache("book", 2, image, "eng", True) is None
    comic.write_cache("book", 2, image, "auto", "pt", "openai", "one", [region])
    cached = comic.read_cache("book", 2, image, "auto", "pt", "openai", "one")
    assert cached[0].translated == "wrong"
    region.original = "clear"; region.manual_original = True
    region.translated = "certo"; region.manual_translation = True
    comic.save_correction("book", 2, region)
    corrected = comic.read_cache("book", 2, image, "auto", "pt", "openai", "one")[0]
    assert (corrected.original, corrected.translated) == ("clear", "certo")
    other = [comic.TextRegion((.1, .1, .4, .2), "unclear", .3)]
    comic.apply_corrections("book", 2, other)
    assert (other[0].original, other[0].translated) == ("clear", "certo")
    comic.clear_cache()
    assert comic.read_cache("book", 2, image, "auto", "pt", "openai", "one") is None
    assert comic._correction_file("book", 2).is_file()


def test_empty_and_repeated_corrections_keep_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(comic, "_CACHE", tmp_path / "cache")
    monkeypatch.setattr(comic, "_CORRECTIONS", tmp_path / "corrections")
    image = Image.new("RGB", (40, 40), "white")
    region = comic.TextRegion((.1, .1, .4, .2), "STOP!", .9, "Parar!")
    comic.write_cache("book", 0, image, "en", "pt", "openai", "chosen", [region])
    comic.save_correction("book", 0, region)
    assert not comic._correction_file("book", 0).is_file()
    path = comic._correction_file("book", 0)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({region.identity: {}}), encoding="utf-8")
    assert comic.read_cache("book", 0, image, "en", "pt", "openai", "chosen") is not None
    region.translated = "Pare!"; region.manual_translation = True
    comic.save_correction("book", 0, region)
    content = path.read_bytes()
    comic.save_correction("book", 0, region)
    assert path.read_bytes() == content
    assert comic.read_cache("book", 0, image, "en", "pt", "openai", "chosen")[0].translated == "Pare!"


def test_original_correction_invalidates_only_stale_translation(monkeypatch, tmp_path):
    monkeypatch.setattr(comic, "_CORRECTIONS", tmp_path / "corrections")
    corrected = comic.TextRegion((.1, .1, .4, .2), "clear", .3)
    corrected.manual_original = True
    comic.save_correction("book", 3, corrected)
    stale = comic.TextRegion((.1, .1, .4, .2), "unclear", .3, "wrong")
    stale.translation_attempted = True
    comic.apply_corrections("book", 3, [stale])
    assert stale.original == "clear"
    assert stale.translated == ""
    assert not stale.translation_attempted


def test_overlay_keeps_original_frame_and_guided_panel():
    frame = Image.new("RGB", (300, 200), "white")
    drawing = ImageDraw.Draw(frame)
    drawing.text((40, 32), "A", fill="black")
    drawing.text((215, 32), "B", fill="black")
    rows = [comic.TextRegion((.1, .1, .4, .35), "A", .9, "Translated"),
            comic.TextRegion((.6, .1, .9, .35), "B", .9, "Other")]
    result = draw_translation_overlay(frame, rows, (0, 0, 300, 200), (.0, .0, .5, .5))
    assert result.crop((30, 20, 120, 70)).tobytes() != frame.crop((30, 20, 120, 70)).tobytes()
    assert result.crop((180, 20, 270, 70)).tobytes() == frame.crop((180, 20, 270, 70)).tobytes()


def test_complex_background_keeps_art_and_shows_translation_label():
    frame = Image.new("RGB", (300, 200))
    drawing = ImageDraw.Draw(frame)
    for y in range(200):
        drawing.line((0, y, 299, y), fill=(y, 40, 200-y))
    drawing.line((30, 20, 120, 70), fill="black", width=3)
    row = comic.TextRegion((.1, .1, .4, .35), "Hello", .8, "Olá")
    result = draw_translation_overlay(frame, [row], (0, 0, 300, 200))
    assert result.crop((30, 20, 120, 70)).tobytes() == frame.crop((30, 20, 120, 70)).tobytes()
    assert result.crop((30, 72, 180, 98)).tobytes() != frame.crop((30, 72, 180, 98)).tobytes()


def test_rotation_keeps_text_and_translated_position():
    source = comic.TextRegion((.1, .2, .3, .4), "Hello", .9, "Olá", True, True,
                              word_scales=(.7, 1.4))
    turned = comic.rotate_regions([source], 1)[0]
    assert turned.box == pytest.approx((.6, .1, .8, .3))
    assert turned.angle == 90
    assert (turned.original, turned.translated, turned.manual_translation) == ("Hello", "Olá", True)
    assert turned.word_scales == (.7, 1.4)
    restored = comic.rotate_regions([turned], 3)[0]
    assert restored.box == pytest.approx(source.box)
    assert restored.angle == 0


def test_original_letter_sizes_drive_translation_layout():
    image = Image.new("RGB", (900, 320), "white")
    draw = ImageDraw.Draw(image)
    sizes = []
    for y, size in ((20, 18), (100, 38), (190, 75)):
        font = _comic_font("STOP!", size)
        draw.text((30, y), "STOP!", fill="black", font=font)
        sizes.append(_source_font_size(image, (25, y, 370, y+size+10), "STOP!"))
    assert sizes[0] < sizes[1] < sizes[2]
    lines, _ = _styled_layout(draw, "vá AGORA!", 45, (.6, 1.6), 450, 120)
    fonts = [font.size for line, _ in lines for _, font, _, _ in line]
    assert fonts[1] > fonts[0] * 1.5


def test_rendered_translation_keeps_each_original_letter_scale():
    image = Image.new("RGB", (720, 440), "white")
    draw = ImageDraw.Draw(image)
    entries = ((30, 22, "psst", "psiu"),
               (145, 46, "HELLO", "OLÁ"),
               (280, 82, "STOP!", "PARE!"))
    rows = []
    for top, size, source, translated in entries:
        draw.text((65, top), source, font=_comic_font(source, size), fill="black")
        rows.append(comic.TextRegion((55/720, (top-8)/440, 450/720,
                                      (top+size+12)/440), source, 1, translated))
    output = draw_translation_overlay(image, rows, (0, 0, 720, 440))

    def ink_height(page, start, end):
        ys = [y for y in range(start, end) for x in range(50, 455)
              if max(page.getpixel((x, y))[:3]) < 110]
        return max(ys)-min(ys)+1

    for top, size, _, _ in entries:
        original = ink_height(image, top-8, top+size+12)
        translated = ink_height(output, top-8, top+size+12)
        assert .75 <= translated/original <= 1.25


def test_manual_correction_survives_rotation(monkeypatch, tmp_path):
    monkeypatch.setattr(comic, "_CORRECTIONS", tmp_path / "corrections")
    original = comic.TextRegion((.1, .2, .3, .4), "Hello", .9)
    turned = comic.rotate_regions([original], 1)[0]
    turned.original = "Hello!"
    turned.translated = "Olá!"
    turned.manual_original = turned.manual_translation = True
    comic.save_correction("book", 1, turned, turns=1)
    upright = comic.apply_corrections("book", 1, [original])[0]
    assert (upright.original, upright.translated) == ("Hello!", "Olá!")
    rotated_again = comic.rotate_regions([comic.TextRegion((.1, .2, .3, .4), "Hello", .9)], 1)
    comic.apply_corrections("book", 1, rotated_again, turns=1)
    assert rotated_again[0].translated == "Olá!"


def test_local_component_download_reports_progress_and_can_cancel(monkeypatch, tmp_path):
    from concurrent.futures import CancelledError
    from threading import Event
    from types import SimpleNamespace

    monkeypatch.setattr(comic.tempfile, "tempdir", str(tmp_path))
    class Response:
        headers = {"Content-Length": "8"}
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def raise_for_status(self): pass
        def iter_content(self, _): yield b"abcd"; yield b"efgh"
    monkeypatch.setattr(comic.requests, "get", lambda *a, **k: Response())
    installed = []
    monkeypatch.setattr(comic, "install_local_model", lambda path: installed.append(path))
    offer = (SimpleNamespace(links=["https://example.test/model.argosmodel"]), None)
    cancel = Event()
    with pytest.raises(CancelledError):
        comic.install_local_offer(offer, cancel,
                                  lambda *_: cancel.set())
    assert not installed
    assert not list(tmp_path.glob("komicove-model-*"))
    cancel.clear()
    progress = []
    comic.install_local_offer(offer, cancel, lambda *item: progress.append(item))
    assert progress[-1] == (1, 1, 8, 8)
    assert len(installed) == 1
    assert not list(tmp_path.glob("komicove-model-*"))
    sentence_path = tmp_path / "models" / "en.onnx"
    comic.install_local_offer((None, ("en", "https://example.test/en.onnx", sentence_path)))
    assert sentence_path.read_bytes() == b"abcdefgh"
    assert not list(sentence_path.parent.glob("tmp*.onnx"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Credential Manager only")
def test_windows_key_is_outside_preferences(monkeypatch, tmp_path):
    monkeypatch.setattr(comic, "_CACHE", tmp_path / "cache")
    monkeypatch.setattr(comic, "_CREDENTIAL_PREFIX", "Komicove:test-translation:")
    try:
        comic.save_key("openai", "fixture-private-key")
        assert comic.load_key("openai") == "fixture-private-key"
        assert not (tmp_path / "cache" / "keys.dpapi").exists()
    finally:
        comic.save_key("openai", "")

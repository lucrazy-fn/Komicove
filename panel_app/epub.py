import posixpath
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

MAX_XML = 2 * 1024 * 1024


def resolve(base, href):
    uri = urlsplit(href)
    if uri.scheme or uri.netloc:
        raise ValueError('EPUB com recurso externo não suportado.')
    path = posixpath.normpath(posixpath.join(posixpath.dirname(base), unquote(uri.path)))
    if path.startswith(('/', '../')) or path == '..' or '\\' in path:
        raise ValueError('Caminho inválido no EPUB.')
    return path


def xml(archive, name):
    if archive.getinfo(name).file_size > MAX_XML:
        raise ValueError('Documento EPUB grande demais.')
    raw = archive.read(name)
    if b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Declarações externas não são permitidas no EPUB.')
    return ET.fromstring(raw)


def local(tag):
    return tag.rsplit('}', 1)[-1]


def image_pages(archive):
    if 'META-INF/encryption.xml' in archive.namelist():
        raise ValueError('EPUB com DRM ou recursos criptografados não é suportado.')
    container = xml(archive, 'META-INF/container.xml')
    package = next((e.attrib.get('full-path') for e in container.iter() if local(e.tag) == 'rootfile'), None)
    if not package:
        raise ValueError('EPUB sem documento principal.')
    package = resolve('', package)
    root = xml(archive, package)
    manifest = {e.attrib['id']: e.attrib for e in root.iter() if local(e.tag) == 'item' and 'id' in e.attrib}
    pages = []
    for ref in root.iter():
        if local(ref.tag) != 'itemref' or ref.get('linear') == 'no':
            continue
        item = manifest.get(ref.get('idref'))
        if not item:
            raise ValueError('Ordem de páginas inválida no EPUB.')
        name = resolve(package, item['href'])
        if item.get('media-type', '').startswith('image/') and not name.lower().endswith('.svg'):
            pages.append(name)
            continue
        document = xml(archive, name)
        bodies = [e for e in document.iter() if local(e.tag) == 'body']
        body = bodies[0] if bodies else document
        images = []
        for node in body.iter():
            tag = local(node.tag)
            if tag in {'script', 'iframe', 'object', 'canvas', 'path', 'rect', 'text', 'foreignObject'}:
                raise ValueError('Este EPUB usa conteúdo complexo. O suporte atual é para HQs com uma imagem por página.')
            if tag not in {'style', 'title', 'desc'} and ((node.text or '').strip() or (node.tail or '').strip()):
                raise ValueError('EPUB de texto ainda não é suportado; use uma HQ com páginas em imagem.')
            if tag in {'img', 'image'}:
                href = node.get('src') or node.get('href') or node.get('{http://www.w3.org/1999/xlink}href')
                if href:
                    images.append(resolve(name, href))
        if len(images) != 1:
            raise ValueError('Este EPUB precisa ter uma imagem por página, na ordem de leitura.')
        pages.extend(images)
    if not pages or len(pages) > 10000:
        raise ValueError('Quantidade de páginas inválida no EPUB.')
    total = 0
    for name in pages:
        if archive.getinfo(name).file_size > 48 * 1024 * 1024:
            raise ValueError('Página EPUB grande demais.')
        total += archive.getinfo(name).file_size
    if total > 1536 * 1024 * 1024:
        raise ValueError('Conteúdo EPUB grande demais.')
    return pages

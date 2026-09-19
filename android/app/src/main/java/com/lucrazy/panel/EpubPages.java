package com.lucrazy.panel;

import java.io.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.*;

final class EpubPages {
    static String resolve(String base,String href)throws Exception{
        URI input=new URI(href);
        if(input.isAbsolute()||input.getAuthority()!=null)throw new IOException("EPUB com recurso externo não suportado.");
        String decoded=input.getPath();
        if(decoded==null||decoded.startsWith("/")||decoded.contains("\\"))throw new IOException("Caminho EPUB inválido.");
        String parent=base.contains("/")?base.substring(0,base.lastIndexOf('/')+1):"";
        Deque<String> parts=new ArrayDeque<>();
        for(String part:(parent+decoded).split("/")){if(part.isEmpty()||part.equals("."))continue;if(part.equals("..")){if(parts.isEmpty())throw new IOException("Caminho EPUB inválido.");parts.removeLast();}else parts.addLast(part);}
        return String.join("/",parts);
    }
    static Document xml(ZipFile zip,String name)throws Exception{
        ZipEntry entry=zip.getEntry(name);if(entry==null)throw new IOException("Recurso ausente no EPUB.");
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        try(InputStream in=zip.getInputStream(entry)){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(out.size()+n>2*1024*1024)throw new IOException("Documento EPUB grande demais.");out.write(b,0,n);}}
        byte[] bytes=out.toByteArray();String raw=new String(bytes,StandardCharsets.UTF_8).toUpperCase(Locale.ROOT);
        if(raw.indexOf(0)>=0||raw.contains("<!DOCTYPE")||raw.contains("<!ENTITY"))throw new IOException("EPUB: XML UTF-8 sem declarações externas é necessário.");
        DocumentBuilderFactory factory=DocumentBuilderFactory.newInstance();factory.setNamespaceAware(true);factory.setExpandEntityReferences(false);
        javax.xml.parsers.DocumentBuilder builder=factory.newDocumentBuilder();builder.setEntityResolver((a,b)->{throw new org.xml.sax.SAXException("Recurso externo bloqueado");});
        return builder.parse(new ByteArrayInputStream(bytes));
    }
    static List<String> read(ZipFile zip)throws Exception{
        if(zip.getEntry("META-INF/encryption.xml")!=null)throw new IOException("EPUB com DRM não é suportado.");
        NodeList roots=xml(zip,"META-INF/container.xml").getElementsByTagNameNS("*","rootfile");
        if(roots.getLength()==0)throw new IOException("EPUB sem documento principal.");
        String packagePath=resolve("",((Element)roots.item(0)).getAttribute("full-path"));
        Document document=xml(zip,packagePath);Map<String,Element> items=new HashMap<>();
        NodeList manifest=document.getElementsByTagNameNS("*","item");
        for(int i=0;i<manifest.getLength();i++){Element e=(Element)manifest.item(i);items.put(e.getAttribute("id"),e);}
        List<String> pages=new ArrayList<>();NodeList spine=document.getElementsByTagNameNS("*","itemref");
        for(int i=0;i<spine.getLength();i++){
            Element ref=(Element)spine.item(i);if(ref.getAttribute("linear").equals("no"))continue;
            Element item=items.get(ref.getAttribute("idref"));if(item==null)throw new IOException("Ordem de leitura inválida.");
            String path=resolve(packagePath,item.getAttribute("href"));
            if(item.getAttribute("media-type").startsWith("image/")&&!path.endsWith(".svg"))pages.add(path);
            else {
                Document page=xml(zip,path);NodeList bodies=page.getElementsByTagNameNS("*","body");
                Node body=bodies.getLength()>0?bodies.item(0):page.getDocumentElement();
                List<String> images=new ArrayList<>();scan(body,path,images);
                if(images.size()!=1)throw new IOException("Suporte EPUB atual: HQs com uma imagem por página.");
                pages.addAll(images);
            }
        }
        if(pages.isEmpty()||pages.size()>BookSource.MAX_PAGES)throw new IOException("Quantidade de páginas inválida.");
        long total=0;
        for(String path:pages){ZipEntry entry=zip.getEntry(path);if(entry==null||!BookSource.image(path))throw new IOException("Imagem EPUB ausente ou incompatível.");if(entry.getSize()>BookSource.MAX_PAGE)throw new IOException("Página grande demais.");total+=Math.max(0,entry.getSize());}
        if(total>BookSource.MAX_TOTAL)throw new IOException("EPUB grande demais.");
        return pages;
    }
    static void scan(Node node,String path,List<String> images)throws Exception{
        if(node.getNodeType()==Node.TEXT_NODE||node.getNodeType()==Node.CDATA_SECTION_NODE){if(!node.getTextContent().trim().isEmpty())throw new IOException("EPUB de texto ainda não é suportado.");return;}
        if(node instanceof Element){Element e=(Element)node;String tag=e.getLocalName();if(tag==null)tag=e.getTagName();
            if(Arrays.asList("script","iframe","object","canvas","path","rect","text","foreignObject").contains(tag))throw new IOException("EPUB com página complexa ainda não é suportado.");
            if(Arrays.asList("style","title","desc").contains(tag))return;
            if(tag.equals("img")||tag.equals("image")){String href=e.getAttribute("src");if(href.isEmpty())href=e.getAttribute("href");if(href.isEmpty())href=e.getAttributeNS("http://www.w3.org/1999/xlink","href");images.add(resolve(path,href));}
        }
        NodeList children=node.getChildNodes();for(int i=0;i<children.getLength();i++)scan(children.item(i),path,images);
    }
}

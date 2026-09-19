package com.lucrazy.panel;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=28)
public class EpubPagesTest {
    private void putImage(ZipOutputStream out,String name)throws Exception{
        out.putNextEntry(new ZipEntry(name));android.graphics.Bitmap image=android.graphics.Bitmap.createBitmap(20,30,android.graphics.Bitmap.Config.ARGB_8888);
        image.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out);image.recycle();out.closeEntry();
    }
    private void put(ZipOutputStream out,String name,String body)throws Exception{out.putNextEntry(new ZipEntry(name));out.write(body.getBytes(StandardCharsets.UTF_8));out.closeEntry();}
    @Test public void spineOrderAndImageWrappers()throws Exception{
        File file=File.createTempFile("epub-test-",".epub");
        try {
            try(ZipOutputStream out=new ZipOutputStream(new FileOutputStream(file))){
                put(out,"META-INF/container.xml","<container><rootfiles><rootfile full-path='OEBPS/book.opf'/></rootfiles></container>");
                put(out,"OEBPS/book.opf","<package><manifest><item id='a' href='a.xhtml' media-type='application/xhtml+xml'/><item id='b' href='1.png' media-type='image/png'/></manifest><spine><itemref idref='a'/><itemref idref='b'/></spine></package>");
                put(out,"OEBPS/a.xhtml","<html><body><img src='2.png'/></body></html>");putImage(out,"OEBPS/1.png");putImage(out,"OEBPS/2.png");
            }
            try(ZipFile zip=new ZipFile(file)){assertEquals(Arrays.asList("OEBPS/2.png","OEBPS/1.png"),EpubPages.read(zip));}
            try(BookSource source=new BookSource(file,file.getParentFile())){android.graphics.Bitmap image=source.page(0,320);assertEquals(20,image.getWidth());assertEquals(30,image.getHeight());image.recycle();}
        }finally{file.delete();}
    }
    @Test public void blocksExternalAndTraversal()throws Exception{
        for(String path:new String[]{"https://example.com/x.png","../../x.png","%2e%2e/%2e%2e/x.png"}){
            try{EpubPages.resolve("OEBPS/a.xhtml",path);fail("Caminho aceito: "+path);}catch(IOException expected){}
        }
    }
}

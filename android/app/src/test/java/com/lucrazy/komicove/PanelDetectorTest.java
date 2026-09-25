package com.lucrazy.komicove;
import android.graphics.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import static org.junit.Assert.*;
@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.GraphicsMode(org.robolectric.annotation.GraphicsMode.Mode.NATIVE)
public class PanelDetectorTest {
    @Test public void fallbackCoversPageAndOrdersSpread(){
        java.util.List<RectF> regions=PanelDetector.readingRegions(2500,1900,false);
        assertEquals(12,regions.size());assertTrue(regions.get(0).centerX()<regions.get(6).centerX());
        for(int y=0;y<=100;y++)for(int x=0;x<=100;x++){
            boolean covered=false;
            for(RectF r:regions)if(x/100f>=r.left&&x/100f<=r.right&&y/100f>=r.top&&y/100f<=r.bottom)covered=true;
            assertTrue(covered);
        }
        assertTrue(PanelDetector.readingRegions(2500,1900,true).get(0).centerX()>.5f);
    }
    @Test public void suppliedArchivePagesCanBeNavigated()throws Exception {
        String path=System.getenv("PANEL_TEST_CBZ");org.junit.Assume.assumeNotNull(path);
        java.io.File cache=org.robolectric.RuntimeEnvironment.getApplication().getCacheDir();
        try(BookSource source=new BookSource(new java.io.File(path),cache)){
            int pages=0,fallbacks=0;
            for(int page=0;page<source.pages.size();page++){
                Bitmap image=source.page(page,1600);assertNotNull(image);java.util.List<RectF> result=PanelDetector.detect(image,false);
                if(result.size()==1){fallbacks++;result=PanelDetector.readingRegions(image.getWidth(),image.getHeight(),false);}
                assertTrue(result.size()>1);image.recycle();pages++;
            }
            assertTrue(pages>0);System.out.println("Archive pages: "+pages+"; approximate navigation: "+fallbacks);
        }
    }
    @Test public void separatesColumnsAndReversesManga(){
        Bitmap b=Bitmap.createBitmap(300,300,Bitmap.Config.ARGB_8888);
        b.eraseColor(Color.BLACK);
        for(int y=0;y<300;y++)for(int x=145;x<155;x++)b.setPixel(x,y,Color.WHITE);
        java.util.List<RectF> normal=PanelDetector.detect(b,false),manga=PanelDetector.detect(b,true);
        assertEquals(2,normal.size());assertEquals(2,manga.size());
        assertTrue(normal.get(0).centerX()<normal.get(1).centerX());assertTrue(manga.get(0).centerX()>manga.get(1).centerX());
    }
    @Test public void undividedPageRemainsWhole(){
        Bitmap b=Bitmap.createBitmap(300,300,Bitmap.Config.ARGB_8888);b.eraseColor(Color.BLACK);
        assertEquals(1,PanelDetector.detect(b,false).size());
    }
}

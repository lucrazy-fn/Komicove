package com.lucrazy.komicove;

import android.graphics.*;
import java.util.*;
import java.util.concurrent.CancellationException;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35)
@org.robolectric.annotation.GraphicsMode(org.robolectric.annotation.GraphicsMode.Mode.NATIVE)
public class GuidedPhase3Test {
    static Bitmap layout(String kind){
        Bitmap b=Bitmap.createBitmap(300,400,Bitmap.Config.ARGB_8888);b.eraseColor(kind.equals("black_gutters")?Color.BLACK:Color.WHITE);
        Canvas c=new Canvas(b);Paint p=new Paint();p.setColor(Color.rgb(52,86,120));
        if(kind.equals("grid")||kind.equals("black_gutters"))for(int y:new int[]{10,210})for(int x:new int[]{10,160})c.drawRect(x,y,x+131,y+181,p);
        else if(kind.equals("borderless")){c.drawRect(10,10,121,141,p);c.drawRect(175,25,291,156,p);c.drawRect(15,230,286,391,p);}
        else if(kind.equals("tilted")){polygon(c,p,10,10,280,10,10,360);polygon(c,p,290,40,290,390,25,390);}
        else if(kind.equals("overlap")){c.drawRect(0,0,241,271,p);p.setColor(Color.rgb(138,49,77));c.drawRect(80,150,300,400,p);}
        else if(kind.equals("splash")){c.drawRect(0,0,300,400,p);p.setColor(Color.rgb(138,49,77));c.drawOval(70,70,250,310,p);}
        else if(kind.equals("noise")){c.drawRect(10,10,291,161,p);c.drawRect(10,230,291,391,p);p.setColor(Color.BLACK);for(int x=20;x<290;x+=30)c.drawRect(x,188,x+3,191,p);}
        else if(kind.equals("thin_gray")||kind.equals("thin_black")){c.drawRect(0,0,300,400,p);p.setColor(kind.equals("thin_gray")?Color.rgb(205,205,205):Color.BLACK);c.drawRect(150,0,151,400,p);c.drawRect(0,200,300,201,p);}
        return b;
    }
    private static void polygon(Canvas c,Paint p,float... points){Path path=new Path();path.moveTo(points[0],points[1]);for(int i=2;i<points.length;i+=2)path.lineTo(points[i],points[i+1]);path.close();c.drawPath(path,p);}
    @Test public void representativeLayouts(){
        String[] kinds={"grid","black_gutters","borderless","tilted","overlap","splash","noise","thin_gray","thin_black"};int[] counts={4,4,3,2,1,1,2,4,4};
        for(int i=0;i<kinds.length;i++){Bitmap b=layout(kinds[i]);try{PanelDetector.Result r=PanelDetector.analyze(b,false);
            assertEquals(kinds[i],counts[i],r.regions().size());assertEquals(kinds[i],i==4||i==5,r.fallback);
            assertEquals(r.fallback,r.confidence<.5f);assertEquals(r.regions(),PanelDetector.clean(r.regions()));
            for(RectF rect:r.regions())assertTrue(rect.left>=0&&rect.top>=0&&rect.right<=1&&rect.bottom<=1&&rect.width()>0&&rect.height()>0);
        }finally{b.recycle();}}
    }
    @Test public void dedupTinyInvalidAndOverlap(){
        List<RectF> input=Arrays.asList(new RectF(0,0,.5f,.5f),new RectF(.005f,.003f,.502f,.499f),new RectF(.3f,.3f,.8f,.8f),new RectF(0,0,.001f,.2f),new RectF(.5f,.5f,.4f,.6f),new RectF(Float.NaN,0,1,1));
        assertEquals(Arrays.asList(input.get(0),input.get(2)),PanelDetector.clean(input));
    }
    @Test public void westernMangaStaggeredAndSpreadOrder(){
        List<RectF> western=Arrays.asList(new RectF(0,0,.45f,.45f),new RectF(.55f,.01f,1,.45f),new RectF(0,.55f,.45f,1),new RectF(.55f,.56f,1,1));
        List<RectF> input=new ArrayList<>(western);Collections.reverse(input);
        assertEquals(western,PanelDetector.order(input,false,false));
        assertEquals(Arrays.asList(western.get(1),western.get(0),western.get(3),western.get(2)),PanelDetector.order(input,true,false));
        assertEquals(Arrays.asList(western.get(0),western.get(2),western.get(1),western.get(3)),PanelDetector.order(input,false,true));
        assertEquals(Arrays.asList(western.get(1),western.get(3),western.get(0),western.get(2)),PanelDetector.order(input,true,true));
    }
    @Test public void cacheForceEvictionAndNoMutableResults(){
        PanelDetector.Cache cache=new PanelDetector.Cache(2);Bitmap b=layout("grid");
        try{PanelDetector.Result first=cache.detect("a:0",b,false,false);assertSame(first,cache.detect("a:0",b,false,false));
            first.regions().get(0).set(0,0,0,0);assertTrue(first.regions().get(0).width()>0);
            b.eraseColor(Color.BLACK);PanelDetector.Result forced=cache.detect("a:0",b,false,true);assertNotSame(first,forced);assertTrue(forced.fallback);
            cache.detect("a:0",b,true,false);cache.detect("b:0",b,false,false);assertEquals(2,cache.size());cache.clear();assertEquals(0,cache.size());
        }finally{b.recycle();}
    }
    @Test public void largePageBoundedSourcePreserved(){Bitmap small=layout("tilted"),large=Bitmap.createScaledBitmap(small,3000,4000,false);
        try{assertEquals(2,PanelDetector.analyze(large,false).regions().size());assertFalse(large.isRecycled());assertEquals(4000,large.getHeight());}finally{small.recycle();large.recycle();}}
    @Test public void obsoleteDetectionIsCancelled(){Bitmap b=layout("grid");try{Thread.currentThread().interrupt();PanelDetector.analyze(b,false);fail("Expected cancellation");}catch(CancellationException expected){}finally{Thread.interrupted();b.recycle();}}
}

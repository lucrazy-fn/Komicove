package com.lucrazy.komicove;

import android.graphics.*;
import android.view.View;
import java.util.concurrent.TimeUnit;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35)
@org.robolectric.annotation.GraphicsMode(org.robolectric.annotation.GraphicsMode.Mode.NATIVE)
public class GuidedPanelFocusTest {
    private ZoomPage view(int width,int height){
        ZoomPage view=new ZoomPage(RuntimeEnvironment.getApplication(),new ZoomPage.Actions(){public void next(){}public void previous(){}public void toggle(){}});
        view.measure(View.MeasureSpec.makeMeasureSpec(width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(height,View.MeasureSpec.EXACTLY));
        view.layout(0,0,width,height);return view;
    }
    private Bitmap page(){
        Bitmap image=Bitmap.createBitmap(1200,1800,Bitmap.Config.ARGB_8888);Canvas c=new Canvas(image);Paint p=new Paint();
        p.setColor(Color.RED);c.drawRect(0,0,1200,600,p);p.setColor(Color.GREEN);c.drawRect(0,600,1200,1200,p);p.setColor(Color.BLUE);c.drawRect(0,1200,1200,1800,p);
        return image;
    }
    private Bitmap render(ZoomPage view){Bitmap b=Bitmap.createBitmap(view.getWidth(),view.getHeight(),Bitmap.Config.ARGB_8888);b.eraseColor(Color.BLACK);view.draw(new Canvas(b));return b;}
    private void centered(ZoomPage view,RectF region){
        assertEquals(view.getWidth()/2f,view.getWidth()/2f+view.panX+(region.centerX()-.5f)*view.image.getWidth()*view.renderScale(),.1f);
        assertEquals(view.getHeight()/2f,view.getHeight()/2f+view.panY+(region.centerY()-.5f)*view.image.getHeight()*view.renderScale(),.1f);
    }
    @Test public void wideTopPanelIsCenteredWithoutOtherPanels(){
        ZoomPage view=view(360,700);Bitmap page=page();view.setImage(page);RectF region=new RectF(0,.08f,1,.22f);
        try{
            view.focus(region);centered(view,region);assertTrue(view.panY>0);assertTrue(view.zoom<1);
            assertTrue(region.width()*page.getWidth()*view.renderScale()<=view.getWidth());
            Bitmap b=render(view);try{assertEquals(Color.RED,b.getPixel(180,350));assertEquals(Color.BLACK,b.getPixel(180,250));assertEquals(Color.BLACK,b.getPixel(180,450));}finally{b.recycle();}
        }finally{page.recycle();}
    }
    @Test public void wideBottomPanelRemainsCenteredAfterResizeAndZoom(){
        ZoomPage view=view(360,700);Bitmap page=page();view.setImage(page);RectF region=new RectF(0,.72f,1,.95f);
        try{view.focus(region);assertTrue(view.panY<0);centered(view,region);view.zoomBy(1.25f);centered(view,region);
            view.layout(0,0,700,360);view.focus(region);centered(view,region);
            Bitmap b=render(view);try{assertEquals(Color.BLUE,b.getPixel(350,180));assertEquals(Color.BLACK,b.getPixel(350,10));}finally{b.recycle();}
        }finally{page.recycle();}
    }
    @Test public void overviewAndNormalFitStillShowWholePage(){
        ZoomPage view=view(360,700);Bitmap page=page();view.setImage(page);RectF region=new RectF(0,.08f,1,.22f);
        try{view.focus(region);view.overview(region);assertEquals(1,view.zoom,0);assertEquals(0,view.panY,0);
            Bitmap b=render(view);try{assertEquals(Color.RED,b.getPixel(180,100));assertEquals(Color.GREEN,b.getPixel(180,350));assertEquals(Color.BLUE,b.getPixel(180,600));}finally{b.recycle();}
            view.clearOverview();view.focus(region);centered(view,region);view.fitToScreen();view.zoomBy(.5f);assertEquals(1,view.zoom,0);
        }finally{page.recycle();}
    }
    @Test public void hiddenControlsDoNotApplyWholePageOffsetToFocusedPanel(){
        ZoomPage view=view(360,700);Bitmap page=page();view.setImage(page);RectF region=new RectF(0,.08f,1,.22f);
        try{view.focus(region);view.setControlsPresentation(1,160);Bitmap b=render(view);
            try{assertEquals(Color.RED,b.getPixel(180,350));assertEquals(Color.BLACK,b.getPixel(180,270));}finally{b.recycle();}
        }finally{page.recycle();}
    }
    @Test public void animatedTransitionFinishesOnWidePanelAndInvalidRegionIsIgnored(){
        ZoomPage view=view(360,700);Bitmap page=page();view.setImage(page);RectF region=new RectF(0,.72f,1,.95f);
        try{view.focus(new RectF(.1f,.1f,.4f,.3f));view.focus(region,true);
            Shadows.shadowOf(android.os.Looper.getMainLooper()).idleFor(500,TimeUnit.MILLISECONDS);centered(view,region);
            float zoom=view.zoom,y=view.panY;view.focus(new RectF(Float.NaN,0,1,1));assertEquals(zoom,view.zoom,0);assertEquals(y,view.panY,0);
            Bitmap b=render(view);try{assertEquals(Color.BLUE,b.getPixel(180,350));}finally{b.recycle();}
        }finally{page.recycle();}
    }
}

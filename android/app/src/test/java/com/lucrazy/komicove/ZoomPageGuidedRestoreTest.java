package com.lucrazy.komicove;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.RectF;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import java.util.Collections;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class ZoomPageGuidedRestoreTest {
    private ZoomPage page(Context context,Bitmap image,int width,int height,RectF panel){
        ZoomPage view=new ZoomPage(context,new ZoomPage.Actions(){public void next(){}public void previous(){}public void toggle(){}});
        view.measure(android.view.View.MeasureSpec.makeMeasureSpec(width,android.view.View.MeasureSpec.EXACTLY),android.view.View.MeasureSpec.makeMeasureSpec(height,android.view.View.MeasureSpec.EXACTLY));
        view.layout(0,0,width,height);view.setImage(image);view.focus(panel);return view;
    }

    @Test public void rotationKeepsGuidedZoomAndCenter() {
        Context context=RuntimeEnvironment.getApplication();
        Bitmap image=Bitmap.createBitmap(1200,1600,Bitmap.Config.ARGB_8888);
        RectF panel=new RectF(.05f,.5f,.95f,.98f);
        ZoomPage portrait=page(context,image,1080,1500,panel);
        portrait.zoomBy(1.25f);
        float ratio=portrait.zoom/portrait.guidedFitZoom(panel);
        float centerX=portrait.centerPageX(),centerY=portrait.centerPageY();
        ZoomPage landscape=page(context,image,2100,650,panel);
        landscape.restoreGuidedView(ratio,centerX,centerY);
        assertEquals(ratio,landscape.zoom/landscape.guidedFitZoom(panel),.01f);
        assertEquals(centerX,landscape.centerPageX(),.01f);
        assertEquals(centerY,landscape.centerPageY(),.01f);
        image.recycle();
    }

    @Test public void compareModeActivatesDisplayWithoutMutatingSource() throws Exception {
        Context context=RuntimeEnvironment.getApplication();
        Bitmap image=Bitmap.createBitmap(1200,1600,Bitmap.Config.ARGB_8888);image.eraseColor(Color.WHITE);
        ZoomPage view=page(context,image,1080,1600,new RectF(0,0,1,1));
        ComicTranslation.Region region=new ComicTranslation.Region(new RectF(.3f,.3f,.7f,.4f),"HELLO",.9f);
        region.translated="OLÁ";
        java.lang.reflect.Field overlay=ZoomPage.class.getDeclaredField("translationOverlay");overlay.setAccessible(true);
        java.lang.reflect.Field compare=ZoomPage.class.getDeclaredField("translationCompare");compare.setAccessible(true);
        try{
            context.getSharedPreferences("comic_translation_prefs",0).edit().putInt("view",0).commit();
            view.setTranslations(Collections.singletonList(region),false);
            assertFalse(overlay.getBoolean(view));
            context.getSharedPreferences("comic_translation_prefs",0).edit().putInt("view",2).commit();
            view.setTranslations(Collections.singletonList(region),false);
            assertTrue(overlay.getBoolean(view));assertTrue(compare.getBoolean(view));
            Bitmap compared=Bitmap.createBitmap(1080,1600,Bitmap.Config.ARGB_8888);
            view.draw(new Canvas(compared));
            assertEquals(Color.WHITE,image.getPixel(600,560));
            compared.recycle();
        }finally{context.getSharedPreferences("comic_translation_prefs",0).edit().putInt("view",0).commit();image.recycle();}
    }

    @Test public void translatedViewNeverDrawsFallbackLabelsOverUnreconstructedArt() {
        assertFalse(ZoomPage.shouldDrawTranslation(false,false));
        assertTrue(ZoomPage.shouldDrawTranslation(false,true));
        assertTrue(ZoomPage.shouldDrawTranslation(true,false));
    }
}

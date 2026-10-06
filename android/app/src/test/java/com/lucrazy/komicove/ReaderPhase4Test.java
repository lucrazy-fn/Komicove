package com.lucrazy.komicove;

import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.view.View;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35)
public class ReaderPhase4Test {
    private ZoomPage view(){
        ZoomPage v=new ZoomPage(RuntimeEnvironment.getApplication(),new ZoomPage.Actions(){public void next(){}public void previous(){}public void toggle(){}});
        v.measure(View.MeasureSpec.makeMeasureSpec(320,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(480,View.MeasureSpec.EXACTLY));
        v.layout(0,0,320,480);v.setImage(Bitmap.createBitmap(1000,1600,Bitmap.Config.ARGB_8888));return v;
    }
    @Test public void allFourCombinationsAndReadingDirections(){
        for(boolean keepZoom:new boolean[]{false,true})for(boolean keepPosition:new boolean[]{false,true})for(String mode:new String[]{"single","dupla","manga"})for(boolean autoFit:new boolean[]{false,true}){
            ZoomPage v=view();
            v.changePage(3,-.2f,-.3f,keepZoom,keepPosition,autoFit,mode);
            float z=keepZoom?3:(autoFit?1:1/.3f);
            assertEquals(z,v.zoom,.001f);
            float mx=Math.max(0,(1000*v.renderScale()-320)/2),my=Math.max(0,(1600*v.renderScale()-480)/2);
            if(keepPosition){assertEquals(Math.max(-mx,-64*z/3),v.panX,.001f);assertEquals(Math.max(-my,-144*z/3),v.panY,.001f);}
            else {assertEquals((mode.equals("manga")?-1:1)*mx,v.panX,.001f);assertEquals(my,v.panY,.001f);}
            v.image.recycle();
        }
    }
    @Test public void migrationPersistsAndNeverOverwritesIndependentChoice(){
        SharedPreferences p=RuntimeEnvironment.getApplication().getSharedPreferences("phase4",0);
        for(boolean old:new boolean[]{false,true}){
            p.edit().clear().putBoolean("persist_zoom",old).putString("theme","sepia").commit();
            ReaderPreferences.migrate(p);
            assertEquals(old,p.getBoolean("persist_position",!old));assertEquals(old,p.getBoolean("persist_zoom",!old));
            assertEquals("sepia",p.getString("theme",""));
            p.edit().putBoolean("persist_position",!old).commit();ReaderPreferences.migrate(p);
            SharedPreferences reopened=RuntimeEnvironment.getApplication().getSharedPreferences("phase4",0);
            assertEquals(!old,reopened.getBoolean("persist_position",old));
        }
    }
    @Test public void dimensionsClampPositionAndFitKeepsWholePage(){
        ZoomPage v=view();v.changePage(3,-10,-10,true,true,true,"single");
        assertEquals(-290,v.panX,.01f);assertEquals(-480,v.panY,.01f);
        v.changePage(3,-.2f,-.3f,false,true,true,"manga");assertEquals(1,v.zoom,0);assertEquals(0,v.panX,.001f);assertEquals(0,v.panY,.001f);
        v.image.recycle();
    }
}

package com.lucrazy.komicove;

import android.content.Intent;
import android.graphics.Bitmap;
import android.os.*;
import android.view.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import java.io.*;
import java.lang.reflect.*;
import java.util.zip.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk={28,35},qualifiers="w360dp-h800dp-xhdpi")
public class ReaderFullscreenTest {
    private LibraryStore store;private LibraryStore.Book book;
    @Before public void setup()throws Exception{
        store=new LibraryStore(RuntimeEnvironment.getApplication());store.context.getSharedPreferences("reader",0).edit().clear().commit();
        Bitmap image=Bitmap.createBitmap(120,180,Bitmap.Config.ARGB_8888);image.eraseColor(android.graphics.Color.WHITE);ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        try(ZipOutputStream zip=new ZipOutputStream(bytes)){for(int i=0;i<3;i++){zip.putNextEntry(new ZipEntry(i+".png"));image.compress(Bitmap.CompressFormat.PNG,100,zip);zip.closeEntry();}}image.recycle();
        book=store.importStream(new ByteArrayInputStream(bytes.toByteArray()),"Fullscreen.cbz");
    }
    @After public void cleanup(){store.remove(book);}
    private Object field(ReaderActivity a,String name)throws Exception{Field f=ReaderActivity.class.getDeclaredField(name);f.setAccessible(true);return f.get(a);}
    private void call(ReaderActivity a,String name)throws Exception{Method m=ReaderActivity.class.getDeclaredMethod(name);m.setAccessible(true);m.invoke(a);}
    private View fullscreenButton(View view,String label){
        if(label.contentEquals(view.getContentDescription()==null?"":view.getContentDescription()))return view;
        if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){View found=fullscreenButton(((ViewGroup)view).getChildAt(i),label);if(found!=null)return found;}
        return null;
    }
    private void ready(ReaderActivity a)throws Exception{long deadline=System.currentTimeMillis()+15000;do{Shadows.shadowOf(Looper.getMainLooper()).idle();if(field(a,"source")!=null&&!(boolean)field(a,"loading"))return;Thread.sleep(10);}while(System.currentTimeMillis()<deadline);fail("Reader not ready");}
    private void layout(ReaderActivity a)throws Exception{View v=(View)field(a,"root");v.measure(View.MeasureSpec.makeMeasureSpec(720,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(1600,View.MeasureSpec.EXACTLY));v.layout(0,0,720,1600);}
    private void fullscreen(ReaderActivity a)throws Exception{
        layout(a);assertTrue((boolean)field(a,"immersiveControls"));View root=(View)field(a,"root"),canvas=(View)field(a,"canvas");
        for(String name:new String[]{"top","guidedHeader","bottomShell"})assertEquals(name,View.GONE,((View)field(a,name)).getVisibility());
        assertEquals(0,root.getPaddingTop());assertEquals(0,root.getPaddingBottom());assertEquals(root.getHeight(),canvas.getHeight());assertEquals(root.getWidth(),canvas.getWidth());
        if(Build.VERSION.SDK_INT<30){int flags=a.getWindow().getDecorView().getSystemUiVisibility();assertTrue((flags&View.SYSTEM_UI_FLAG_FULLSCREEN)!=0);assertTrue((flags&View.SYSTEM_UI_FLAG_HIDE_NAVIGATION)!=0);}
    }
    @Test public void fullscreenIsDifferentFromMinimizingAndBackRestoresAllModes()throws Exception{
        for(String mode:new String[]{"normal","manga","dupla","vertical","webtoon"}){
            book.mode=mode;store.save(book);
            try(ActivityController<ReaderActivity> c=Robolectric.buildActivity(ReaderActivity.class,new Intent(store.context,ReaderActivity.class).putExtra("book",book.id)).setup().visible()){
                ReaderActivity a=c.get();ready(a);layout(a);int page=(int)field(a,"index");
                call(a,"toggleControls");Shadows.shadowOf(Looper.getMainLooper()).idle();assertFalse((boolean)field(a,"immersiveControls"));assertEquals(View.VISIBLE,((View)field(a,"top")).getVisibility());
                call(a,"toggleControls");Shadows.shadowOf(Looper.getMainLooper()).idle();call(a,"toggleFullscreen");fullscreen(a);
                assertEquals(page,field(a,"index"));a.onBackPressed();layout(a);assertFalse(a.isFinishing());assertFalse((boolean)field(a,"immersiveControls"));assertEquals(View.VISIBLE,((View)field(a,"top")).getVisibility());assertEquals(View.VISIBLE,((View)field(a,"bottomShell")).getVisibility());
                call(a,"toggleFullscreen");fullscreen(a);call(a,"toggleControls");assertFalse((boolean)field(a,"immersiveControls"));assertEquals(page,field(a,"index"));
            }
        }
    }
    @Test public void fullscreenSurvivesGuidedUpdatesAndActivityRecreation()throws Exception{
        store.context.getSharedPreferences("reader",0).edit().putBoolean("guided",true).commit();
        for(String lang:new String[]{"pt","en"})try(ActivityController<ReaderActivity> c=Robolectric.buildActivity(ReaderActivity.class,new Intent(store.context,ReaderActivity.class).putExtra("book",book.id)).setup().visible()){
            I18n.language(store.context,lang);c.recreate();ReaderActivity a=c.get();ready(a);layout(a);
            View button=fullscreenButton((View)field(a,"guidedZoom"),lang.equals("pt")?"Tela cheia":"Full screen");assertNotNull(button);assertTrue(button.isShown());assertTrue(button.getWidth()>0);assertTrue(button.performClick());call(a,"updateCounter");fullscreen(a);
            c.recreate();a=c.get();ready(a);fullscreen(a);assertTrue((boolean)field(a,"guided"));
            call(a,"toggleControls");layout(a);assertEquals(View.VISIBLE,((View)field(a,"guidedHeader")).getVisibility());assertEquals(View.GONE,((View)field(a,"top")).getVisibility());
        }
    }
}

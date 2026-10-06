package com.lucrazy.komicove;

import android.content.*;
import android.graphics.*;
import android.os.Looper;
import android.view.*;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.zip.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35,qualifiers="w360dp-h800dp-xhdpi")
@org.robolectric.annotation.GraphicsMode(org.robolectric.annotation.GraphicsMode.Mode.NATIVE)
public class GuidedReaderUiTest {
    private LibraryStore store;private LibraryStore.Book book;
    @Before public void setup()throws Exception{
        Context context=RuntimeEnvironment.getApplication();store=new LibraryStore(context);
        context.getSharedPreferences("reader",0).edit().clear().putBoolean("guided",true).putBoolean("animate_guided",false).commit();
        context.getSharedPreferences("komicove_ui",0).edit().putString("language","pt").commit();
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        try(ZipOutputStream out=new ZipOutputStream(bytes)){int n=0;for(String kind:new String[]{"grid","tilted","splash"}){
            Bitmap image=GuidedPhase3Test.layout(kind);ByteArrayOutputStream png=new ByteArrayOutputStream();image.compress(Bitmap.CompressFormat.PNG,100,png);image.recycle();
            out.putNextEntry(new ZipEntry("00"+(++n)+".png"));out.write(png.toByteArray());out.closeEntry();
        }}
        book=store.importStream(new ByteArrayInputStream(bytes.toByteArray()),"GuidedPhase3.cbz");book.page=0;book.mode="normal";book.customPanels=new org.json.JSONObject();store.save(book);
    }
    @After public void cleanup(){if(book!=null)store.remove(book);}
    private Object field(ReaderActivity a,String name)throws Exception{Field f=ReaderActivity.class.getDeclaredField(name);f.setAccessible(true);return f.get(a);}
    private void call(ReaderActivity a,String name)throws Exception{Method m=ReaderActivity.class.getDeclaredMethod(name);m.setAccessible(true);m.invoke(a);}
    private void call(ReaderActivity a,String name,int value)throws Exception{Method m=ReaderActivity.class.getDeclaredMethod(name,int.class);m.setAccessible(true);m.invoke(a,value);}
    private <T extends View> T find(View root,Class<T> type){
        if(type.isInstance(root))return type.cast(root);
        if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++){T found=find(((ViewGroup)root).getChildAt(i),type);if(found!=null)return found;}
        return null;
    }
    private android.widget.Button redetect(View root){
        if(root instanceof android.widget.Button&&((android.widget.Button)root).getText().toString().equals("Redetectar"))return (android.widget.Button)root;
        if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++){android.widget.Button found=redetect(((ViewGroup)root).getChildAt(i));if(found!=null)return found;}
        return null;
    }
    private ActivityController<ReaderActivity> open(){return Robolectric.buildActivity(ReaderActivity.class,new Intent(store.context,ReaderActivity.class).putExtra("book",book.id)).setup().visible();}
    private void ready(ReaderActivity a)throws Exception{
        long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(15);
        do{Shadows.shadowOf(Looper.getMainLooper()).idle();if(field(a,"source")!=null&&!(boolean)field(a,"loading"))return;Thread.sleep(10);}while(System.nanoTime()<deadline);
        fail("Reader did not finish loading");
    }
    private void screenshot(ReaderActivity a,String name,int w,int h)throws Exception{
        String path=System.getenv("KOMICOVE_PHASE3_QA");View root=a.getWindow().getDecorView();root.measure(View.MeasureSpec.makeMeasureSpec(w,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(h,View.MeasureSpec.EXACTLY));root.layout(0,0,w,h);
        Shadows.shadowOf(Looper.getMainLooper()).idle();if(path==null)return;
        Bitmap image=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);root.draw(new Canvas(image));File file=new File(path,name+".png");file.getParentFile().mkdirs();try(FileOutputStream out=new FileOutputStream(file)){image.compress(Bitmap.CompressFormat.PNG,100,out);}finally{image.recycle();}
    }
    @SuppressWarnings("unchecked")
    @Test public void redetectNavigateFallbackAndNormalLayout()throws Exception{
        try(ActivityController<ReaderActivity> controller=open()){
            ReaderActivity a=controller.get();ready(a);assertTrue((boolean)field(a,"guided"));assertEquals(4,((List<RectF>)field(a,"panels")).size());
            screenshot(a,"android-guided-small",720,1600);assertEquals(View.VISIBLE,((View)field(a,"guidedHeader")).getVisibility());assertEquals(View.GONE,((View)field(a,"readerQuick")).getVisibility());
            screenshot(a,"android-guided-large",1080,1920);
            PanelDetector.Result first=(PanelDetector.Result)field(a,"guidedResult");call(a,"redetectPanels");ready(a);assertNotSame(first,field(a,"guidedResult"));
            call(a,"move",1);assertEquals(1,field(a,"panelIndex"));call(a,"jump",2);ready(a);assertTrue((boolean)field(a,"guidedFallback"));assertEquals(1,((List<RectF>)field(a,"panels")).size());
            screenshot(a,"android-guided-fallback",720,1600);
            call(a,"toggleGuided");ready(a);assertEquals(View.GONE,((View)field(a,"guidedHeader")).getVisibility());assertEquals(View.VISIBLE,((View)field(a,"readerQuick")).getVisibility());
        }
    }
    @Test public void configurationRecreationReusesDetectionAndPosition()throws Exception{
        try(ActivityController<ReaderActivity> controller=open()){
            ReaderActivity first=controller.get();ready(first);call(first,"move",1);Object session=field(first,"session"),result=field(first,"guidedResult");
            controller.recreate();ReaderActivity restored=controller.get();ready(restored);
            assertSame(session,field(restored,"session"));assertSame(result,field(restored,"guidedResult"));assertEquals(1,field(restored,"panelIndex"));
        }
    }
    @Test public void startsFocusedAndLocateReturnsToTheSamePanelInBothLanguages()throws Exception{
        for(String lang:new String[]{"pt","en"}){
            I18n.language(store.context,lang);book.page=0;book.guidedPage=0;book.guidedPanel=0;store.save(book);
            try(ActivityController<ReaderActivity> controller=open()){
                ReaderActivity a=controller.get();ready(a);screenshot(a,"android-guided-focused-"+lang,720,1600);
                ZoomPage page=(ZoomPage)field(a,"pageView");assertFalse((boolean)field(a,"overview"));assertTrue(page.zoom>1);
                android.widget.Button locate=(android.widget.Button)field(a,"guidedOverviewButton");assertTrue(locate.isShown());assertEquals(lang.equals("pt")?"Se localizar":"Find your place",locate.getText().toString());
                call(a,"move",1);Shadows.shadowOf(Looper.getMainLooper()).idle();int selected=(int)field(a,"panelIndex");
                locate.performClick();assertTrue((boolean)field(a,"overview"));assertEquals(1,page.zoom,0);assertEquals(selected,field(a,"panelIndex"));assertEquals(lang.equals("pt")?"Voltar ao quadro":"Return to panel",locate.getText().toString());
                screenshot(a,"android-guided-locate-"+lang,720,1600);locate.performClick();assertFalse((boolean)field(a,"overview"));assertTrue(page.zoom>1);assertEquals(selected,field(a,"panelIndex"));
                controller.recreate();a=controller.get();ready(a);assertFalse((boolean)field(a,"overview"));assertEquals(selected,field(a,"panelIndex"));assertTrue(((ZoomPage)field(a,"pageView")).zoom>1);
            }
        }
    }
    @SuppressWarnings("unchecked")
    @Test public void legacyManualOrderSurvivesRedetectAndEditor()throws Exception{
        String manual="[[0.5,0,1,0.5],[0,0,0.5,0.5]]";book.customPanels.put("0",new org.json.JSONArray(manual));book.mode="manga";store.save(book);
        try(ActivityController<ReaderActivity> controller=open()){
            ReaderActivity a=controller.get();ready(a);assertTrue((boolean)field(a,"guidedManual"));List<RectF> initial=new ArrayList<>((List<RectF>)field(a,"panels"));
            assertEquals(.5f,initial.get(0).left,0);call(a,"redetectPanels");ready(a);assertEquals(initial,field(a,"panels"));
            assertEquals(manual,store.get(book.id).customPanels.getJSONArray("0").toString());
            call(a,"editPanels");
            // Editor preparation uses the same worker and must not mutate saved panels.
            java.util.concurrent.Future<?> task=(java.util.concurrent.Future<?>)field(a,"editorTask");task.get(10,java.util.concurrent.TimeUnit.SECONDS);Shadows.shadowOf(Looper.getMainLooper()).idle();
            android.app.Dialog dialog=org.robolectric.shadows.ShadowDialog.getLatestDialog();assertTrue(dialog.isShowing());
            PanelEditorView editor=find(dialog.getWindow().getDecorView(),PanelEditorView.class);assertNotNull(editor);assertEquals(2,editor.panels.size());
            android.widget.Button redetect=redetect(dialog.getWindow().getDecorView());assertNotNull(redetect);redetect.performClick();
            task=(java.util.concurrent.Future<?>)field(a,"editorTask");task.get(10,java.util.concurrent.TimeUnit.SECONDS);Shadows.shadowOf(Looper.getMainLooper()).idle();
            assertEquals(4,editor.panels.size());assertTrue(redetect.isEnabled());
            assertEquals(manual,store.get(book.id).customPanels.getJSONArray("0").toString());dialog.dismiss();
            assertEquals(manual,store.get(book.id).customPanels.getJSONArray("0").toString());
        }
    }
}

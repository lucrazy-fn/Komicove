package com.lucrazy.komicove;

import android.app.*;
import android.content.*;
import android.graphics.*;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.zip.*;

/** Runs only in the isolated .phase4test application. */
public final class ReaderPhase4Instrumentation extends Instrumentation {
    private ReaderActivity active;
    private LibraryStore store;
    private LibraryStore.Book book;
    private final StringBuilder log=new StringBuilder();
    @Override public void onCreate(Bundle args){super.onCreate(args);start();}
    @Override public void onStart(){Bundle result=new Bundle();int code=Activity.RESULT_OK;
        try{
            require(getTargetContext().getPackageName().endsWith(".phase4test"),"Use -Pphase4Test=true");
            store=new LibraryStore(getTargetContext());
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(ZipOutputStream zip=new ZipOutputStream(bytes)){
                Bitmap image=Bitmap.createBitmap(1600,2400,Bitmap.Config.ARGB_8888);image.eraseColor(Color.LTGRAY);
                for(int i=0;i<3;i++){zip.putNextEntry(new ZipEntry(i+".png"));image.compress(Bitmap.CompressFormat.PNG,100,zip);zip.closeEntry();}image.recycle();
            }
            book=store.importStream(new ByteArrayInputStream(bytes.toByteArray()),"Phase4.cbz");
            SharedPreferences prefs=getTargetContext().getSharedPreferences("reader",0);
            for(boolean z:new boolean[]{false,true})for(boolean p:new boolean[]{false,true})for(String mode:new String[]{"normal","manga","dupla"}){
                prefs.edit().clear().putBoolean("guided",false).putBoolean("auto_fit",false).putBoolean("persist_zoom",z).putBoolean("persist_position",p).commit();
                book=store.get(book.id);book.page=0;book.mode=mode;book.zoom=1;book.offsetX=book.offsetY=0;store.save(book);
                open();ready(0);
                runOnMainSync(()->{try{((ZoomPage)field("pageView")).restore(3,-.12f,-.14f);invoke("jump",1);}catch(Exception e){throw new RuntimeException(e);}});ready(1);
                validate(z,p,mode);close();open();ready(1);validate(z,p,mode);close();
                log.append("PASS zoom=").append(z).append(" position=").append(p).append(" mode=").append(mode).append(" navigation/reopen\n");
            }
            for(String mode:new String[]{"vertical","webtoon"}){
                book=store.get(book.id);book.mode=mode;book.page=0;store.save(book);open();waitForIdleSync();
                runOnMainSync(()->invoke("jump",1));waitForIdleSync();Thread.sleep(300);
                require(field("vertical") instanceof ListView,"Vertical list absent");close();
                log.append("PASS ").append(mode).append(" navigation\n");
            }
            book=store.get(book.id);book.mode="normal";store.save(book);
            for(String lang:new String[]{"pt","en"}){
                getTargetContext().getSharedPreferences("komicove_ui",0).edit().putString("language",lang).commit();
                open();ready(book.page);
                final Dialog[] dialog={null};
                runOnMainSync(()->{dialog[0]=ReaderPreferences.show(active,null);});waitForIdleSync();
                View root=dialog[0].getWindow().getDecorView();List<Switch> switches=new ArrayList<>();collect(root,switches);
                require(switches.size()==5,"Expected two retention switches plus original controls");
                require(hasText(root,lang.equals("pt")?"Manter nível de zoom":"Keep zoom level"),"Zoom translation missing");
                require(hasText(root,lang.equals("pt")?"Manter posição":"Keep position"),"Position translation missing");
                runOnMainSync(()->{switches.get(0).setChecked(false);switches.get(1).setChecked(true);});waitForIdleSync();
                Thread.sleep(300);final Bitmap[] rendered={null};
                runOnMainSync(()->{int w=root.getWidth(),h=root.getHeight();require(w>0&&h>0,"Preferences layout missing");rendered[0]=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);root.draw(new Canvas(rendered[0]));});Bitmap shot=rendered[0];
                if(shot!=null){try(FileOutputStream out=new FileOutputStream(new File(getTargetContext().getCacheDir(),"phase4-"+lang+".png"))){shot.compress(Bitmap.CompressFormat.PNG,100,out);}shot.recycle();}
                runOnMainSync(()->clickText(root,lang.equals("pt")?"Salvar preferências":"Save preferences"));waitForIdleSync();
                require(!prefs.getBoolean("persist_zoom",true)&&prefs.getBoolean("persist_position",false),"Independent UI save failed");close();
                log.append("PASS preferences ").append(lang).append(" labels, switches and save\n");
            }
            result.putString("stream",log.toString());
        }catch(Throwable e){StringWriter trace=new StringWriter();e.printStackTrace(new PrintWriter(trace));code=Activity.RESULT_CANCELED;result.putString("stream",log+"FAIL "+trace);}
        finally{if(active!=null)close();if(book!=null)store.remove(book);}
        finish(code,result);
    }
    private void validate(boolean z,boolean p,String mode)throws Exception{
        ZoomPage v=(ZoomPage)field("pageView");float fit=Math.min((float)v.getWidth()/v.image.getWidth(),(float)v.getHeight()/v.image.getHeight());
        float zoom=z?3:Math.max(1,Math.min(6,1/fit));require(Math.abs(v.zoom-zoom)<.01,"Wrong zoom");
        if(p)require(v.panX<=0&&v.panY<=0,"Position reset despite ON");
        else {require(v.panY>=0,"Page must start at top");require(mode.equals("manga")?v.panX<=0:v.panX>=0,"Wrong reading edge");}
    }
    private void open(){active=(ReaderActivity)startActivitySync(new Intent(getTargetContext(),ReaderActivity.class).putExtra("book",book.id).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}
    private void close(){if(active==null)return;ReaderActivity a=active;runOnMainSync(a::finish);waitForIdleSync();active=null;}
    private void ready(int page)throws Exception{long end=System.currentTimeMillis()+20000;do{waitForIdleSync();if((int)field("displayedPage")==page&&!(boolean)field("loading"))return;Thread.sleep(20);}while(System.currentTimeMillis()<end);throw new AssertionError("Page load timed out");}
    private Object field(String name)throws Exception{Field f=ReaderActivity.class.getDeclaredField(name);f.setAccessible(true);return f.get(active);}
    private void invoke(String name,int n){try{Method m=ReaderActivity.class.getDeclaredMethod(name,int.class);m.setAccessible(true);m.invoke(active,n);}catch(Exception e){throw new RuntimeException(e);}}
    private void collect(View view,List<Switch> out){if(view instanceof Switch)out.add((Switch)view);if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++)collect(((ViewGroup)view).getChildAt(i),out);}
    private boolean hasText(View v,String text){if(v instanceof TextView&&text.equals(((TextView)v).getText().toString()))return true;if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++)if(hasText(((ViewGroup)v).getChildAt(i),text))return true;return false;}
    private void clickText(View v,String text){if(v instanceof Button&&text.equals(((Button)v).getText().toString())){v.performClick();return;}if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++)clickText(((ViewGroup)v).getChildAt(i),text);}
    private static void require(boolean ok,String message){if(!ok)throw new AssertionError(message);}
}

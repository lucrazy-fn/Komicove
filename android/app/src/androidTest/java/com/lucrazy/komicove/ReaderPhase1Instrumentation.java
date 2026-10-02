package com.lucrazy.komicove;

import android.app.*;
import android.content.*;
import android.content.pm.ActivityInfo;
import android.graphics.Bitmap;
import android.os.*;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;

/** Opt-in USB acceptance test. Creates/removes only its own library entry. */
public final class ReaderPhase1Instrumentation extends Instrumentation {
    private Bundle arguments;private final StringBuilder log=new StringBuilder();private final java.util.concurrent.atomic.AtomicLong peak=new java.util.concurrent.atomic.AtomicLong(),nativePeak=new java.util.concurrent.atomic.AtomicLong();
    @Override public void onCreate(Bundle arguments){super.onCreate(arguments);this.arguments=arguments;start();}
    @Override public void onStart(){Bundle result=new Bundle();int resultCode=Activity.RESULT_OK;LibraryStore store=new LibraryStore(getTargetContext());LibraryStore.Book fixture=null;ReaderActivity activity=null;
        try {
            String directory=arguments.getString("fixtures");if(directory==null)throw new IllegalArgumentException("Pass fixtures directory");
            for(String name:new String[]{"large.cbt","large.cb7","large-rar4.cbr","large-rar5.rar","solid.7z","solid-rar5.rar","large.cbz"}){
                File archive=File.createTempFile("phase1-benchmark-","-"+name,getTargetContext().getCacheDir());
                try{try(InputStream in=new FileInputStream(new File(directory,name));OutputStream out=new FileOutputStream(archive)){BookSource.copy(in,out);}if(Boolean.parseBoolean(arguments.getString("baseline","false")))baseline(archive,name);benchmark(archive,name);}finally{archive.delete();}
            }
            String rar4Solid=arguments.getString("rar4Solid");if(rar4Solid!=null){try(BookSource source=new BookSource(new File(rar4Solid),getTargetContext().getCacheDir())){require(source.pages.size()>1,"Solid RAR4 fixture has no pages");for(int page:new int[]{0,source.pages.size()-1,source.pages.size()/2,0})source.page(page,600).recycle();log.append("PASS compressed solid RAR4(first/last/backward/revisit)\n");}}
            File original=new File(directory,"large.cbt"),copy=new File(store.books,"phase1-usb-test.cbt");
            if(copy.exists()||store.get("phase1-usb-test")!=null)throw new IOException("Test fixture already exists; refusing overwrite");
            try(InputStream in=new FileInputStream(original);OutputStream out=new FileOutputStream(copy)){BookSource.copy(in,out);}
            fixture=new LibraryStore.Book();fixture.id="phase1-usb-test";fixture.file=copy.getName();fixture.title="Phase 1 USB test";store.save(fixture);
            activity=launch(fixture.id);waitPage(activity,0);Object source=field(activity,"source"),session=field(activity,"session");
            ReaderActivity current=activity;runOnMainSync(()->{try{((ZoomPage)field(current,"pageView")).restore(2f,.05f,.04f);}catch(Exception e){throw new RuntimeException(e);}});
            ActivityMonitor monitor=addMonitor(ReaderActivity.class.getName(),null,false);
            runOnMainSync(()->current.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE));
            ReaderActivity rotated=(ReaderActivity)monitor.waitForActivityWithTimeout(15000);removeMonitor(monitor);
            if(rotated==null||rotated==current)throw new AssertionError("Rotation did not recreate reader");activity=rotated;waitPage(activity,0);
            require(source==field(activity,"source"),"Rotation reopened archive");require(session==field(activity,"session"),"Rotation lost session");require(Math.abs(((ZoomPage)field(activity,"pageView")).zoom-2)<.01,"Rotation lost zoom");
            ReaderActivity active=activity;runOnMainSync(()->{for(int page:new int[]{8,2,12,3,15,1,5})invoke(active,"jump",page);});waitPage(activity,5);
            ReaderSession retained=(ReaderSession)field(activity,"session");Thread.sleep(500);require(retained.cache.size()<=retained.cache.maxSize(),"Bitmap budget exceeded");
            long extracted=((BookSource)source).cachedBytes();runOnMainSync(activity::finish);waitClosed(activity,retained);activity=launch(fixture.id);waitPage(activity,5);require(((BookSource)field(activity,"source")).cachedBytes()>=extracted,"Reopen discarded prepared cache");
            log.append("PASS rotation(source identity, session identity, zoom), rapid jumps(final page=5), reopen, bitmap release\n");result.putString("stream",log.toString());
        }catch(Throwable error){while(error instanceof InvocationTargetException&&error.getCause()!=null)error=error.getCause();StringWriter trace=new StringWriter();error.printStackTrace(new PrintWriter(trace));resultCode=Activity.RESULT_CANCELED;result.putString("stream",log+"FAIL "+trace);}
        finally{if(activity!=null){ReaderActivity remaining=activity;runOnMainSync(remaining::finish);}if(fixture!=null)store.remove(fixture);}
        finish(resultCode,result);
    }
    private void benchmark(File archive,String name)throws Exception {
        require(archive.length()>100L*1024*1024,"Large fixture missing: "+archive.getName());System.gc();Thread.sleep(80);long start=System.nanoTime(),before=used(),nativeBefore=Debug.getNativeHeapAllocatedSize();Thread sampler=sample();
        try(BookSource source=new BookSource(archive,getTargetContext().getCacheDir())){long indexed=System.nanoTime();require(source.pages.size()==16,"Wrong page count");require(source.cachedBytes()<archive.length()/2,"Eager extraction");
            Bitmap first=source.page(0,1600);long shown=System.nanoTime(),after=used(),firstPeak=Math.max(after,peak.get()),firstNativePeak=Math.max(Debug.getNativeHeapAllocatedSize(),nativePeak.get()),firstCache=source.cachedBytes();require(first!=null,"No first page");first.recycle();require(firstCache<archive.length()/2,"Full extraction");
            source.page(15,1600).recycle();source.page(5,1600).recycle();source.page(0,1600).recycle();
            log.append(String.format(Locale.ROOT,"AFTER %s bytes=%d prepare_ms=%.2f first_ms=%.2f heap_delta=%d peak_java_delta=%d peak_native_delta=%d first_cache_bytes=%d cache_bytes=%d PASS first/last/backward/revisit\n",name,archive.length(),(indexed-start)/1e6,(shown-start)/1e6,after-before,firstPeak-before,firstNativePeak-nativeBefore,firstCache,source.cachedBytes()));
        }finally{sampler.interrupt();sampler.join();}
    }
    private Thread sample(){peak.set(used());nativePeak.set(Debug.getNativeHeapAllocatedSize());Thread thread=new Thread(()->{while(!Thread.currentThread().isInterrupted()){peak.accumulateAndGet(used(),Math::max);nativePeak.accumulateAndGet(Debug.getNativeHeapAllocatedSize(),Math::max);try{Thread.sleep(2);}catch(InterruptedException e){return;}}});thread.start();return thread;}
    private void baseline(File archive,String name)throws Exception {
        Class<?> legacy=Class.forName("com.lucrazy.komicove.BaselineBookSource");Constructor<?> constructor=legacy.getDeclaredConstructor(File.class,File.class);constructor.setAccessible(true);Method page=legacy.getDeclaredMethod("page",int.class,int.class);page.setAccessible(true);
        System.gc();Thread.sleep(80);long before=used(),nativeBefore=Debug.getNativeHeapAllocatedSize(),start=System.nanoTime();Thread sampler=sample();Object source=null;
        try{source=constructor.newInstance(archive,getTargetContext().getCacheDir());long prepared=System.nanoTime();Bitmap bitmap=(Bitmap)page.invoke(source,0,1600);long first=System.nanoTime();bitmap.recycle();
            log.append(String.format(Locale.ROOT,"BEFORE %s prepare_ms=%.2f first_ms=%.2f peak_java_delta=%d peak_native_delta=%d%n",name,(prepared-start)/1e6,(first-start)/1e6,peak.get()-before,nativePeak.get()-nativeBefore));
        }finally{if(source!=null)((Closeable)source).close();sampler.interrupt();sampler.join();}
    }
    private long used(){return Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory();}
    private ReaderActivity launch(String id){return (ReaderActivity)startActivitySync(new Intent(getTargetContext(),ReaderActivity.class).putExtra("book",id).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}
    private void waitPage(ReaderActivity activity,int page)throws Exception{long deadline=System.currentTimeMillis()+20000;while(System.currentTimeMillis()<deadline){waitForIdleSync();if((int)field(activity,"displayedPage")==page&&!(boolean)field(activity,"loading"))return;Thread.sleep(30);}throw new AssertionError("Page did not load: "+page);}
    private void waitClosed(ReaderActivity activity,ReaderSession session)throws Exception{long deadline=System.currentTimeMillis()+10000;while(System.currentTimeMillis()<deadline){waitForIdleSync();if((boolean)field(activity,"destroyed")&&session.cache.size()==0)return;Thread.sleep(50);}throw new AssertionError("Reader close failed: destroyed="+field(activity,"destroyed")+", changingConfiguration="+activity.isChangingConfigurations()+", cache="+session.cache.size());}
    private static Object field(Object target,String name)throws Exception{Field field=target.getClass().getDeclaredField(name);field.setAccessible(true);return field.get(target);}
    private static void invoke(ReaderActivity activity,String method,int page){try{Method target=ReaderActivity.class.getDeclaredMethod(method,int.class);target.setAccessible(true);target.invoke(activity,page);}catch(Exception e){throw new RuntimeException(e);}}
    private static void require(boolean condition,String error){if(!condition)throw new AssertionError(error);}
}

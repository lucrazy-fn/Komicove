package com.lucrazy.komicove;

import android.graphics.*;
import android.os.*;
import android.view.*;
import android.widget.ImageView;
import java.io.File;
import java.util.*;
import java.util.concurrent.*;

/** Visible image bindings, cancellable work, sampled decoding and bounded LRU. */
final class LibraryCovers implements AutoCloseable {
    static final int MAX_ITEMS=96,MAX_BYTES=16*1024*1024;
    private final LibraryStore store;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ThreadPoolExecutor workers=new ThreadPoolExecutor(2,2,0,TimeUnit.MILLISECONDS,new LinkedBlockingQueue<>());
    private final LinkedHashMap<String,Bitmap> cache=new LinkedHashMap<>(16,.75f,true);
    private final Set<Binding> bindings=new HashSet<>();
    private int bytes;
    private volatile boolean closed;
    private final Object[] coverLocks=new Object[16];
    LibraryCovers(LibraryStore store){this.store=store;for(int i=0;i<coverLocks.length;i++)coverLocks[i]=new Object();}
    void bind(ImageView view,LibraryStore.Book book){new Binding(view,book);}
    void clearCache(){cache.clear();bytes=0;}
    int cacheBytes(){return bytes;}
    int cacheItems(){return cache.size();}
    int queued(){return workers.getQueue().size();}
    private Bitmap decode(LibraryStore.Book book)throws Exception{
        BookSource.checkCancelled();
        // Avoid simultaneous writes when the same cover appears in two sections.
        synchronized(coverLocks[(book.id.hashCode()&0x7fffffff)%coverLocks.length]){BookSource.checkCancelled();if(!store.cover(book).isFile())store.prepareCover(book);}
        BookSource.checkCancelled();File file=store.cover(book);
        BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;BitmapFactory.decodeFile(file.getAbsolutePath(),options);
        options.inSampleSize=1;while(Math.max(options.outWidth,options.outHeight)/options.inSampleSize>640)options.inSampleSize*=2;
        options.inJustDecodeBounds=false;options.inPreferredConfig=Bitmap.Config.RGB_565;
        return BitmapFactory.decodeFile(file.getAbsolutePath(),options);
    }
    private void put(String key,Bitmap image){
        Bitmap previous=cache.put(key,image);if(previous!=null)bytes-=previous.getAllocationByteCount();bytes+=image.getAllocationByteCount();
        while(bytes>MAX_BYTES||cache.size()>MAX_ITEMS){String eldest=cache.keySet().iterator().next();bytes-=cache.remove(eldest).getAllocationByteCount();}
    }
    @Override public void close(){closed=true;for(Binding b:new ArrayList<>(bindings))b.detach();workers.shutdownNow();main.removeCallbacksAndMessages(null);clearCache();}
    private final class Binding implements View.OnAttachStateChangeListener {
        final ImageView view;final LibraryStore.Book book;final Rect visible=new Rect();
        final ViewTreeObserver.OnScrollChangedListener scroll=this::check;
        final ViewTreeObserver.OnGlobalLayoutListener layout=this::check;
        Future<?> task;int generation;boolean showing,failed;
        ViewTreeObserver observer;
        Binding(ImageView view,LibraryStore.Book book){this.view=view;this.book=book;view.addOnAttachStateChangeListener(this);if(view.isAttachedToWindow())onViewAttachedToWindow(view);}
        @Override public void onViewAttachedToWindow(View ignored){if(closed)return;bindings.add(this);observer=view.getViewTreeObserver();observer.addOnScrollChangedListener(scroll);observer.addOnGlobalLayoutListener(layout);check();}
        @Override public void onViewDetachedFromWindow(View ignored){detach();}
        void cancel(){generation++;if(task!=null){task.cancel(true);if(task instanceof Runnable)workers.remove((Runnable)task);task=null;}}
        void detach(){cancel();if(observer!=null&&observer.isAlive()){observer.removeOnScrollChangedListener(scroll);observer.removeOnGlobalLayoutListener(layout);}observer=null;view.removeOnAttachStateChangeListener(this);view.setImageResource(R.drawable.comic_cover_placeholder);bindings.remove(this);}
        void check(){
            if(closed)return;
            if(!view.isShown()||!view.getGlobalVisibleRect(visible)){cancel();if(showing){view.setImageResource(R.drawable.comic_cover_placeholder);showing=false;}return;}
            if(showing||task!=null||failed)return;
            Bitmap hit=cache.get(book.id);if(hit!=null){view.setImageBitmap(hit);showing=true;return;}
            int ticket=++generation;
            task=workers.submit(()->{
                Bitmap decoded=null;try{decoded=decode(book);}catch(Exception ignored){}
                if(closed){if(decoded!=null)decoded.recycle();return;}
                Bitmap image=decoded;
                main.post(()->{if(closed||ticket!=generation||!view.isAttachedToWindow()){if(image!=null)image.recycle();return;}task=null;
                    if(image==null){failed=true;return;}
                    if(!view.getGlobalVisibleRect(visible)){image.recycle();return;}
                    put(book.id,image);view.setImageBitmap(image);showing=true;
                });
            });
        }
    }
}

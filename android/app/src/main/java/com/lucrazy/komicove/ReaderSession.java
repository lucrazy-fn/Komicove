package com.lucrazy.komicove;

import android.content.Context;
import android.graphics.Bitmap;
import android.util.LruCache;
import java.io.*;
import java.util.concurrent.*;

/** Retained on configuration changes; never stores an Activity or View. */
final class ReaderSession implements Closeable {
    private final ExecutorService preparation=Executors.newSingleThreadExecutor();
    private final ThreadPoolExecutor speculative=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new LinkedBlockingQueue<>());
    private final Future<BookSource> opening;private Future<?> prefetch;
    private final LibraryStore store;private final LibraryStore.Book book;
    private final ConcurrentMap<Integer,java.util.concurrent.locks.ReentrantLock> decodeLocks=new ConcurrentHashMap<>();
    private volatile boolean closed;private volatile BookSource source;
    final PanelDetector.Cache detections;
    PanelDetector.Result detection(int page,Bitmap bitmap,boolean manga,boolean force)throws InterruptedIOException{
        BookSource.checkCancelled();if(closed)throw new InterruptedIOException();
        PanelDetector.Result result=detections.detect(String.valueOf(page),bitmap,manga,force);
        BookSource.checkCancelled();if(closed)throw new InterruptedIOException();return result;
    }
    final LruCache<Integer,Bitmap> cache=new LruCache<Integer,Bitmap>((int)Math.min(24L*1024*1024,Runtime.getRuntime().maxMemory()/8)){
        protected int sizeOf(Integer key,Bitmap bitmap){return bitmap.getAllocationByteCount();}
    };
    ReaderSession(Context context,LibraryStore.Book book){this.store=new LibraryStore(context.getApplicationContext());this.book=book;
        detections=new PanelDetector.Cache(128,AiPanelDetector.available(context));
        opening=preparation.submit(()->{BookSource opened=new BookSource(store.file(book),store.context.getCacheDir());source=opened;if(closed){opened.close();throw new InterruptedIOException();}return opened;});
    }
    BookSource source()throws Exception{try{return opening.get();}catch(ExecutionException e){Throwable cause=e.getCause();if(cause instanceof Exception)throw (Exception)cause;throw new IOException("Arquivo incompatível ou danificado.",cause);}}
    Bitmap bitmap(int page)throws Exception {
        BookSource.checkCancelled();if(closed)throw new InterruptedIOException();Bitmap bitmap=cache.get(page);if(bitmap!=null)return bitmap;
        java.util.concurrent.locks.ReentrantLock lock=decodeLocks.computeIfAbsent(page,key->new java.util.concurrent.locks.ReentrantLock());lock.lockInterruptibly();
        try{BookSource.checkCancelled();bitmap=cache.get(page);if(bitmap!=null)return bitmap;Bitmap decoded=source().page(page,1600);
            synchronized(this){if(closed||Thread.currentThread().isInterrupted()){decoded.recycle();throw new InterruptedIOException();}cache.put(page,decoded);}return decoded;
        }finally{lock.unlock();}
    }
    synchronized void cancelPrefetch(){if(prefetch!=null){prefetch.cancel(true);prefetch=null;}speculative.purge();}
    synchronized void prefetch(int page){cancelPrefetch();if(closed||source==null||page<0||page>=source.pages.size()||cache.get(page)!=null)return;
        prefetch=speculative.submit(()->{android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);try{bitmap(page);}catch(Exception ignored){}});
    }
    void keepNear(int page){for(Integer key:cache.snapshot().keySet())if(Math.abs(key-page)>2)cache.remove(key);}
    void trimMemory(){cancelPrefetch();cache.evictAll();}
    public synchronized void close(){if(closed)return;closed=true;cancelPrefetch();opening.cancel(true);speculative.shutdownNow();cache.evictAll();detections.close();
        preparation.execute(()->{if(source!=null)source.close();store.release(book);ArchivePageCache.trimIdle(store.context.getCacheDir());});preparation.shutdown();
    }
}

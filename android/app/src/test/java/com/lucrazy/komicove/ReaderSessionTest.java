package com.lucrazy.komicove;

import android.graphics.Bitmap;
import java.io.*;
import java.util.concurrent.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=28)
public class ReaderSessionTest {
    @Test public void concurrentDecodeSharesBitmapAndCloseDropsCache()throws Exception {
        LibraryStore store=new LibraryStore(RuntimeEnvironment.getApplication());File file=ArchivePerformanceTest.tar(store.books,4,ArchivePerformanceTest.bmp(128,256));
        LibraryStore.Book book=new LibraryStore.Book();book.id="phase1-session-unit";book.title="Session test";book.file=file.getName();store.save(book);
        ReaderSession session=new ReaderSession(store.context,book);ExecutorService workers=Executors.newFixedThreadPool(2);
        try{session.source();CountDownLatch start=new CountDownLatch(1);Callable<Bitmap> decode=()->{start.await();return session.bitmap(0);};Future<Bitmap> a=workers.submit(decode),b=workers.submit(decode);start.countDown();assertSame(a.get(10,TimeUnit.SECONDS),b.get(10,TimeUnit.SECONDS));
            session.bitmap(3);session.keepNear(3);assertNull(session.cache.get(0));assertTrue(session.cache.size()<=session.cache.maxSize());session.close();assertEquals(0,session.cache.size());
            try{session.bitmap(0);fail();}catch(InterruptedIOException expected){}
        }finally{workers.shutdownNow();session.close();store.remove(book);}
    }
}

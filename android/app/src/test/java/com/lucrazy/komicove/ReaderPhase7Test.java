package com.lucrazy.komicove;

import android.graphics.Bitmap;
import java.io.*;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class ReaderPhase7Test {
    @Test public void aspectAndScreenDecodePreserveSourceAndCancellation()throws Exception{
        LibraryStore store=new LibraryStore(RuntimeEnvironment.getApplication());
        File file=ArchivePerformanceTest.tar(store.books,3,ArchivePerformanceTest.bmp(2400,3600));
        try(BookSource source=new BookSource(file,store.context.getCacheDir())){
            assertEquals(1.5f,source.aspectRatio(0),.001f);
            Bitmap bitmap=source.page(0,600);assertTrue(bitmap.getWidth()<=900);assertTrue((long)bitmap.getWidth()*bitmap.getHeight()<=BookSource.MAX_DECODE_PIXELS);bitmap.recycle();
            Thread.currentThread().interrupt();
            try{source.page(2,600);fail("Cancelled decode succeeded");}catch(InterruptedIOException expected){}finally{Thread.interrupted();}
        }finally{file.delete();}
    }
    @Test public void optionalPositionRoundTripsWithoutReplacingLegacyZoom()throws Exception{
        JSONObject legacy=new JSONObject().put("page",7).put("zoom",3).put("offsetY",-.25).put("unknown","keep");
        LibraryStore.Book book=LibraryStore.Book.parse(legacy);
        assertEquals(0,book.retained.optDouble("vertical_offset",0),0);
        book.retained.put("vertical_page",7).put("vertical_offset",.375);
        LibraryStore.Book reopened=LibraryStore.Book.parse(book.json());
        assertEquals(.375,reopened.retained.getDouble("vertical_offset"),0);
        assertEquals(7,reopened.retained.getInt("vertical_page"));assertEquals(3,reopened.zoom,0);assertEquals(-.25,reopened.offsetY,0);assertEquals("keep",reopened.retained.getString("unknown"));
    }
}

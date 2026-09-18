package com.lucrazy.panel;

import android.app.Activity;
import android.content.Intent;
import android.graphics.*;
import android.widget.TextView;
import android.view.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;
import java.io.*;
import java.util.zip.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=28)
public class ReaderIntegrationTest {
    private LibraryStore store;
    @Test public void guidedPositionSurvivesLibraryReload()throws Exception {
        LibraryStore.Book b=store.importStream(new ByteArrayInputStream(cbz()),"Guided.cbz");
        b.page=1;b.guidedPage=1;b.guidedPanel=4;store.save(b);
        LibraryStore.Book restored=new LibraryStore(RuntimeEnvironment.getApplication()).get(b.id);
        assertEquals(1,restored.guidedPage);assertEquals(4,restored.guidedPanel);
        assertEquals(-1,LibraryStore.Book.parse(new org.json.JSONObject()).guidedPage);
    }
    @Test public void overviewCanReturnToSameRegion(){
        ZoomPage view=new ZoomPage(RuntimeEnvironment.getApplication(),new ZoomPage.Actions(){public void next(){}public void previous(){}public void toggle(){}});
        view.layout(0,0,400,600);
        view.setImage(Bitmap.createBitmap(800,1200,Bitmap.Config.ARGB_8888));
        RectF region=new RectF(.1f,.2f,.45f,.5f);view.focus(region);
        float zoom=view.zoom,x=view.panX,y=view.panY;
        view.overview(region);assertEquals(1,view.zoom,0);assertEquals(0,view.panX,0);
        view.clearOverview();view.focus(region);
        assertEquals(zoom,view.zoom,.001);assertEquals(x,view.panX,.001);assertEquals(y,view.panY,.001);
    }
    @Before public void setup(){store=new LibraryStore(RuntimeEnvironment.getApplication());for(LibraryStore.Book b:store.all())store.remove(b);}
    private byte[] cbz()throws Exception {Bitmap bitmap=Bitmap.createBitmap(30,50,Bitmap.Config.ARGB_8888);bitmap.eraseColor(Color.RED);ByteArrayOutputStream image=new ByteArrayOutputStream();bitmap.compress(Bitmap.CompressFormat.PNG,100,image);ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(ZipOutputStream zip=new ZipOutputStream(bytes)){for(String name:new String[]{"page10.png","../page2.png","page1.png"}){zip.putNextEntry(new ZipEntry(name));zip.write(image.toByteArray());zip.closeEntry();}}return bytes.toByteArray();}
    @Test public void importDeduplicatesAndRestoresMetadata()throws Exception {
        byte[] archive=cbz();LibraryStore.Book b=store.importStream(new ByteArrayInputStream(archive),"Original.cbz");
        assertEquals(3,b.count);assertTrue(store.file(b).exists());assertTrue(store.cover(b).exists());
        assertEquals(b.id,store.importStream(new ByteArrayInputStream(archive),"Outro nome.zip").id);assertEquals(1,store.all().size());
        b.page=2;b.favorite=true;b.collection="Série";store.save(b);ByteArrayOutputStream backup=new ByteArrayOutputStream();store.exportBackup(backup);
        b.page=0;b.favorite=false;b.collection="";store.save(b);assertEquals(1,store.restoreBackup(new ByteArrayInputStream(backup.toByteArray())));
        LibraryStore.Book restored=store.get(b.id);assertEquals(2,restored.page);assertTrue(restored.favorite);assertEquals("Série",restored.collection);
        store.remove(restored);assertEquals(0,store.all().size());assertFalse(store.file(b).exists());
    }
    @Test public void invalidArchiveDoesNotCreateLibraryEntry()throws Exception {try{store.importStream(new ByteArrayInputStream(new byte[]{1,2,3}),"bad.cbz");fail("Should reject invalid data");}catch(Exception expected){}assertTrue(store.all().isEmpty());}
    @Test public void nativeHomeLaunchesInGuestMode(){try(var activity=Robolectric.buildActivity(MainActivity.class).setup()){assertNotNull(activity.get());assertTrue(findText(activity.get().getWindow().getDecorView(),"Biblioteca"));assertTrue(findText(activity.get().getWindow().getDecorView(),"Sua coleção começa aqui."));}}
    private boolean findText(View v,String text){if(v instanceof TextView&&((TextView)v).getText().toString().contains(text))return true;if(v instanceof ViewGroup){ViewGroup group=(ViewGroup)v;for(int i=0;i<group.getChildCount();i++)if(findText(group.getChildAt(i),text))return true;}return false;}
}

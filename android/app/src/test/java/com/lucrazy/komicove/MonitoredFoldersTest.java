package com.lucrazy.komicove;

import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import org.robolectric.shadows.ShadowContentResolver;
import java.io.*;
import java.nio.file.Files;
import java.util.*;
import java.util.zip.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class MonitoredFoldersTest {
    Context context;LibraryStore store;MonitoredFolders monitor;FixtureProvider provider;
    static final Uri ROOT=Uri.parse("content://phase2.test/tree/root");
    @Before public void setup()throws Exception{
        context=RuntimeEnvironment.getApplication();context.getSharedPreferences("library",0).edit().clear().commit();context.getSharedPreferences("library_folders",0).edit().clear().commit();
        store=new LibraryStore(context);monitor=new MonitoredFolders(context,store);provider=new FixtureProvider();provider.attachInfo(context,new android.content.pm.ProviderInfo());ShadowContentResolver.registerProviderInternal("phase2.test",provider);
        context.getSharedPreferences("library_folders",0).edit().putStringSet("uris",Collections.singleton(ROOT.toString())).commit();
    }
    @After public void close(){for(File file:provider.files.values())file.delete();}
    private File archive(String marker)throws Exception{File file=File.createTempFile("phase2-test-",".cbz",context.getCacheDir());try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(file))){zip.putNextEntry(new ZipEntry("001.jpg"));zip.write(new byte[]{1,2,3});zip.closeEntry();zip.putNextEntry(new ZipEntry("marker.txt"));zip.write(marker.getBytes());zip.closeEntry();}return file;}
    private void settle()throws Exception{monitor.scan();JSONObject observations=new JSONObject(context.getSharedPreferences("library_folders",0).getString("observations","{}"));Iterator<String> names=observations.keys();while(names.hasNext())observations.getJSONObject(names.next()).put("since",System.currentTimeMillis()-4000);context.getSharedPreferences("library_folders",0).edit().putString("observations",observations.toString()).commit();}
    @Test public void largeFolderDeduplicatesAndReusesMetadata()throws Exception{
        for(int i=0;i<300;i++)provider.files.put("book-"+i,archive("book-"+i));
        settle();MonitoredFolders.Result first=monitor.scan();assertEquals(monitor.folders().toString()+" opens="+provider.opens+" invalid="+first.invalid,300,first.added);assertEquals(300,store.all().size());int opened=provider.opens;
        MonitoredFolders.Result again=monitor.scan();assertEquals(0,again.added);assertEquals(300,again.duplicates);assertEquals(opened,provider.opens);
        assertEquals(1,new MonitoredFolders(context,store).folders().length());
    }
    @Test public void newDuplicateRemovedAndRenamePreserveProgress()throws Exception{
        File file=archive("first");provider.files.put("first",file);settle();assertEquals(1,monitor.scan().added);
        LibraryStore.Book book=store.all().get(0);book.page=4;book.favorite=true;book.collection="Mine";store.save(book);
        provider.files.put("copy",file);settle();assertEquals(0,monitor.scan().added);assertEquals(1,store.all().size());
        provider.files.remove("first");provider.files.remove("copy");monitor.scan();assertFalse(store.get(book.id).available);assertEquals(4,store.get(book.id).page);
        provider.files.put("renamed",file);settle();assertEquals(0,monitor.scan().added);LibraryStore.Book renamed=store.get(book.id);assertTrue(renamed.available);assertEquals(4,renamed.page);assertTrue(renamed.favorite);assertEquals("Mine",renamed.collection);assertTrue(renamed.uri.contains("renamed"));
        provider.files.put("new",archive("second"));settle();assertEquals(1,monitor.scan().added);assertEquals(2,store.all().size());
    }
    @Test public void partialCopyAndCorruptFileAreDeferred()throws Exception{
        provider.files.put("copy",archive("copy"));provider.partial=true;settle();assertEquals(0,monitor.scan().added);assertTrue(store.all().isEmpty());
        provider.partial=false;assertEquals(1,monitor.scan().added);
        File broken=archive("broken");Files.write(broken.toPath(),new byte[]{1,2,3});provider.files.put("broken",broken);settle();assertEquals(0,monitor.scan().added);assertEquals(1,monitor.scan().invalid);
    }
    @Test public void permissionLossPauseAndRemoveNeverEraseProgress()throws Exception{
        provider.files.put("first",archive("first"));settle();monitor.scan();String id=store.all().get(0).id;
        provider.fail=true;monitor.scan();assertFalse(store.get(id).available);assertEquals("unavailable",monitor.folders().getJSONObject(0).getString("status"));
        provider.fail=false;assertEquals(0,monitor.scan().added);assertTrue(store.get(id).available);
        monitor.configure(ROOT.toString(),"Comics",false,false);assertEquals("Comics",new MonitoredFolders(context,store).folders().getJSONObject(0).getString("name"));
        monitor.configure(ROOT.toString(),null,null,true);monitor.scan();assertEquals(1,store.all().size());assertEquals(0,monitor.folders().length());
    }
    @Test public void disabledFolderSkipsNewFilesAndResumesWithoutLosingProgress()throws Exception{
        provider.files.put("first",archive("first"));settle();monitor.scan();LibraryStore.Book book=store.all().get(0);book.page=8;book.favorite=true;store.save(book);int opened=provider.opens;
        monitor.configure(ROOT.toString(),null,false,false);provider.files.put("new",archive("new"));
        assertEquals(0,monitor.scan().added);assertEquals(opened,provider.opens);assertEquals(1,store.all().size());assertTrue(store.get(book.id).available);
        assertFalse(new MonitoredFolders(context,store).folders().getJSONObject(0).getBoolean("enabled"));
        assertTrue(monitor.visibleBooks().isEmpty());assertEquals(1,store.all().size());
        monitor.configure(ROOT.toString(),null,true,false);settle();assertEquals(1,monitor.scan().added);
        assertEquals(8,store.get(book.id).page);assertTrue(store.get(book.id).favorite);
        assertEquals(2,monitor.visibleBooks().size());
    }
    @Test public void visibilityKeepsActiveAlternateSourceAndStandaloneImports()throws Exception{
        provider.files.put("first",archive("first"));settle();monitor.scan();LibraryStore.Book book=store.all().get(0);
        String other="content://phase2.test/tree/other";JSONArray registry=monitor.folders();registry.put(new JSONObject().put("uri",other).put("enabled",true));context.getSharedPreferences("library_folders",0).edit().putString("registry",registry.toString()).commit();
        book.sources.put(new JSONObject().put("folder",other).put("uri","content://phase2.test/document/copy"));context.getSharedPreferences("library",0).edit().putString("items",new JSONArray().put(book.json()).toString()).commit();
        monitor.configure(ROOT.toString(),null,false,false);assertEquals(1,monitor.visibleBooks().size());
        monitor.configure(other,null,false,false);assertTrue(monitor.visibleBooks().isEmpty());assertEquals(1,store.all().size());
        LibraryStore.Book local=new LibraryStore.Book();local.id="standalone";local.title="Local";local.file="standalone.cbz";store.save(local);
        assertEquals("standalone",monitor.visibleBooks().get(0).id);
        monitor.configure(ROOT.toString(),null,true,false);assertEquals(2,monitor.visibleBooks().size());
    }
    @Test public void visibleFolderSwitchCallsRealPersistentSetting()throws Exception{
        android.widget.LinearLayout content=Ui.column(context);
        MonitoredFoldersView.render(context,content,monitor.folders(),store,command->{},new MonitoredFoldersView.Actions(){
            public void add(){}public void refresh(String uri){}public void menu(JSONObject row){}public void dismiss(){}
            public void enabled(String uri,boolean enabled){try{monitor.configure(uri,null,enabled,false);}catch(Exception error){throw new AssertionError(error);}}
        });
        android.widget.Switch control=findSwitch(content);assertNotNull(control);assertTrue(control.isChecked());
        control.setChecked(false);assertFalse(new MonitoredFolders(context,store).folders().getJSONObject(0).getBoolean("enabled"));
        control.setChecked(true);assertTrue(monitor.folders().getJSONObject(0).getBoolean("enabled"));
    }
    private android.widget.Switch findSwitch(android.view.View view){
        if(view instanceof android.widget.Switch)return (android.widget.Switch)view;
        if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++){android.widget.Switch control=findSwitch(group.getChildAt(i));if(control!=null)return control;}}
        return null;
    }
    @Test public void emptyLibraryHasVisibleFolderEntryAndRealAddAction(){
        context.getSharedPreferences("auth_state",0).edit().putString("mode","guest").commit();
        org.robolectric.android.controller.ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class).create();
        try{
            MainActivity activity=controller.get();android.view.View decor=activity.getWindow().getDecorView();
            int exact=android.view.View.MeasureSpec.EXACTLY;decor.measure(android.view.View.MeasureSpec.makeMeasureSpec(1080,exact),android.view.View.MeasureSpec.makeMeasureSpec(1920,exact));decor.layout(0,0,1080,1920);
            android.view.View entry=findDescription(decor,"Pastas monitoradas / adicionar pasta");assertNotNull(entry);assertTrue(entry.getWidth()>0);assertTrue(entry.performClick());
            android.widget.Button add=findButton(decor,"Adicionar pasta");assertNotNull(add);assertTrue(add.performClick());
            assertEquals(Intent.ACTION_OPEN_DOCUMENT_TREE,Shadows.shadowOf(activity).getNextStartedActivityForResult().intent.getAction());
        }finally{controller.destroy();context.getSharedPreferences("auth_state",0).edit().clear().commit();}
    }
    private android.view.View findDescription(android.view.View view,String description){
        if(description.contentEquals(view.getContentDescription()==null?"":view.getContentDescription()))return view;
        if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++){android.view.View result=findDescription(group.getChildAt(i),description);if(result!=null)return result;}}
        return null;
    }
    @Test public void showMoreKeepsExistingScrollViewAndPosition()throws Exception{
        JSONArray books=new JSONArray();for(int i=0;i<90;i++){LibraryStore.Book book=new LibraryStore.Book();book.id="more-"+i;book.title="HQ "+i;book.file=book.id+".cbz";books.put(book.json());}
        context.getSharedPreferences("library",0).edit().putString("items",books.toString()).commit();context.getSharedPreferences("auth_state",0).edit().putString("mode","guest").commit();
        org.robolectric.android.controller.ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class).create().start().visible();
        try{
            android.view.View decor=controller.get().getWindow().getDecorView();layout(decor);
            android.widget.ScrollView scroll=findScroll(decor);assertNotNull(scroll);scroll.scrollTo(0,2000);int position=scroll.getScrollY();assertTrue(position>0);
            android.widget.Button more=findButtonPrefix(decor,"Mostrar mais (");assertNotNull(more);assertTrue(more.performClick());layout(decor);Shadows.shadowOf(android.os.Looper.getMainLooper()).idle();
            assertSame(scroll,findScroll(decor));assertEquals(position,scroll.getScrollY());assertNull(findButtonPrefix(decor,"Mostrar mais ("));
        }finally{controller.stop().destroy();context.getSharedPreferences("auth_state",0).edit().clear().commit();}
    }
    private void layout(android.view.View view){int exact=android.view.View.MeasureSpec.EXACTLY;view.measure(android.view.View.MeasureSpec.makeMeasureSpec(1080,exact),android.view.View.MeasureSpec.makeMeasureSpec(1920,exact));view.layout(0,0,1080,1920);}
    private android.widget.ScrollView findScroll(android.view.View view){
        if(view instanceof android.widget.ScrollView)return (android.widget.ScrollView)view;
        if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++){android.widget.ScrollView result=findScroll(group.getChildAt(i));if(result!=null)return result;}}
        return null;
    }
    private android.widget.Button findButtonPrefix(android.view.View view,String prefix){
        if(view instanceof android.widget.Button&&((android.widget.Button)view).getText().toString().startsWith(prefix))return (android.widget.Button)view;
        if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++){android.widget.Button result=findButtonPrefix(group.getChildAt(i),prefix);if(result!=null)return result;}}
        return null;
    }
    private android.widget.Button findButton(android.view.View view,String text){
        if(view instanceof android.widget.Button&&text.contentEquals(((android.widget.Button)view).getText()))return (android.widget.Button)view;
        if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++){android.widget.Button result=findButton(group.getChildAt(i),text);if(result!=null)return result;}}
        return null;
    }
    @Test public void readerSaveCannotOverwriteNewSourceState()throws Exception{
        provider.files.put("first",archive("first"));settle();monitor.scan();LibraryStore.Book stale=store.all().get(0);provider.files.clear();monitor.scan();stale.page=6;store.save(stale);assertFalse(store.get(stale.id).available);assertEquals(6,store.get(stale.id).page);
    }
    @Test public void readerSaveCannotUndoPermissionLoss()throws Exception{
        provider.files.put("first",archive("first"));settle();monitor.scan();LibraryStore.Book stale=store.all().get(0);provider.fail=true;monitor.scan();stale.page=7;store.save(stale);assertFalse(store.get(stale.id).available);assertEquals(7,store.get(stale.id).page);
    }
    @Test public void sameDocumentRenameUpdatesNameWithoutLosingMetadata()throws Exception{
        provider.files.put("first",archive("first"));settle();monitor.scan();LibraryStore.Book book=store.all().get(0);book.page=3;store.save(book);int opened=provider.opens;
        provider.names.put("first","Renamed.cbz");monitor.scan();assertEquals("Renamed",store.get(book.id).title);assertEquals(3,store.get(book.id).page);assertEquals(opened,provider.opens);
        book=store.get(book.id);book.title="My custom title";store.save(book);provider.names.put("first","Again.cbz");monitor.scan();assertEquals("My custom title",store.get(book.id).title);
    }
    @Test public void manualRemovalDoesNotReimportOnNextScan()throws Exception{
        provider.files.put("first",archive("first"));settle();monitor.scan();store.remove(store.all().get(0));int opened=provider.opens;assertEquals(0,monitor.scan().added);assertTrue(store.all().isEmpty());assertEquals(opened,provider.opens);
    }
    public static final class FixtureProvider extends ContentProvider {
        final Map<String,File> files=new LinkedHashMap<>();final Map<String,String> names=new HashMap<>();int opens;boolean fail,partial;
        public boolean onCreate(){return true;}public String getType(Uri uri){return "application/zip";}public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
        @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){
            if(fail)throw new SecurityException("Revoked");MatrixCursor cursor=new MatrixCursor(projection);String id=DocumentsContract.getDocumentId(uri);
            if(uri.getPathSegments().contains("children")){for(Map.Entry<String,File> file:files.entrySet())row(cursor,projection,file.getKey(),file.getValue());}
            else if(id.equals("root"))row(cursor,projection,id,null);else if(files.containsKey(id))row(cursor,projection,id,files.get(id));return cursor;
        }
        private void row(MatrixCursor cursor,String[] columns,String id,File file){
            Object[] values=new Object[columns.length];
            for(int i=0;i<columns.length;i++)switch(columns[i]){
                case "document_id":values[i]=id;break;
                case "_display_name":values[i]=file==null?"Comics":names.getOrDefault(id,id+".cbz");break;
                case "mime_type":values[i]=file==null?DocumentsContract.Document.MIME_TYPE_DIR:"application/zip";break;
                case "_size":values[i]=file==null?0:file.length();break;
                case "last_modified":values[i]=file==null?0:file.lastModified();break;
                case "flags":values[i]=partial?DocumentsContract.Document.FLAG_PARTIAL:0;break;
                default:values[i]=null;
            }
            cursor.addRow(values);
            if(file!=null)Shadows.shadowOf(getContext().getContentResolver()).registerInputStreamSupplier(DocumentsContract.buildDocumentUriUsingTree(ROOT,id),()->{opens++;try{return new FileInputStream(file);}catch(IOException e){throw new IllegalStateException(e);}});
        }
        @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{opens++;return ParcelFileDescriptor.open(files.get(DocumentsContract.getDocumentId(uri)),ParcelFileDescriptor.MODE_READ_ONLY);}
    }
}

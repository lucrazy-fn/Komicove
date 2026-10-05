package com.lucrazy.komicove;

import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import org.robolectric.shadows.ShadowContentResolver;
import java.io.*;
import java.nio.file.Files;
import java.util.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class LibrarySyncTest {
    Context context;LibraryStore store;FixtureProvider provider;JSONObject contract;
    static final Uri URI=Uri.parse("content://phase5.test/document/comic");
    @Before public void setup()throws Exception {
        context=RuntimeEnvironment.getApplication();
        context.getSharedPreferences("library",0).edit().clear().commit();
        context.getSharedPreferences("content_identity",0).edit().clear().commit();
        store=new LibraryStore(context);
        try(InputStream input=getClass().getResourceAsStream("/portable_identity_v1.json")){
            contract=new JSONObject(new String(input.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));
        }
        provider=new FixtureProvider();provider.attachInfo(context,new android.content.pm.ProviderInfo());
        provider.file=File.createTempFile("phase5-",".cbz",context.getCacheDir());
        Files.write(provider.file.toPath(),contract.getString("utf8").getBytes(java.nio.charset.StandardCharsets.UTF_8));
        ShadowContentResolver.registerProviderInternal("phase5.test",provider);
        Shadows.shadowOf(context.getContentResolver()).registerInputStreamSupplier(URI,()->{
            if(provider.fail)throw new SecurityException("fixture denied");
            provider.opens++;try{return new FileInputStream(provider.file);}catch(IOException error){throw new IllegalStateException(error);}
        });
    }
    @After public void close(){provider.file.delete();}
    LibraryStore.Book linked()throws Exception {
        store.linkUris(Collections.singletonList(URI));LibraryStore.Book book=store.all().get(0);book.count=30;store.save(book);return store.get(book.id);
    }
    JSONObject remote(String key,int page,boolean favorite,double stamp)throws Exception {
        return new JSONObject().put("item_key",key).put("page",page).put("favorite",favorite).put("client_updated_at",stamp);
    }
    @Test public void pcToAndroidUriPreservesOldIdAndFutureLocalDomains()throws Exception {
        LibraryStore.Book book=linked();String id=book.id;book.collection="Local";book.marks.put(4);book.customPanels.put("3",new JSONArray().put("manual"));book.retained.put("future_field",42);store.save(book);
        assertTrue(LibrarySync.run(store,entries->{
            JSONObject row=entries.getJSONObject(0);assertEquals(contract.getString("sha256"),row.getString("item_key"));
            assertEquals(id,row.getJSONArray("legacy_keys").getString(0));assertTrue(row.isNull("page"));
            return new JSONArray().put(remote(row.getString("item_key"),8,true,100));
        }));
        LibraryStore.Book current=new LibraryStore(context).get(id);
        assertNotNull(current);assertEquals(8,current.page);assertTrue(current.favorite);assertEquals("Local",current.collection);
        assertEquals(4,current.marks.getInt(0));assertTrue(current.customPanels.has("3"));assertEquals(42,current.json().getInt("future_field"));
        int opens=provider.opens;store.prepareSyncPayload();new LibraryStore(context).prepareSyncPayload();assertEquals(opens,provider.opens);
    }
    @Test public void androidToPcAndConflictProtectsEditsDuringNetwork()throws Exception {
        LibraryStore.Book book=linked();book.page=12;book.favorite=true;book.updated=System.currentTimeMillis()/1000.0;store.save(book);
        LibrarySync.run(store,entries->{
            JSONObject row=entries.getJSONObject(0);assertEquals(contract.getString("sha256"),row.getString("item_key"));assertEquals(12,row.getInt("page"));assertTrue(row.getBoolean("favorite"));
            LibraryStore.Book edited=store.get(book.id);edited.page=2;edited.favorite=false;store.save(edited);
            return new JSONArray().put(remote(row.getString("item_key"),19,true,row.getDouble("client_updated_at")));
        });
        assertEquals(2,store.get(book.id).page);assertFalse(store.get(book.id).favorite);
        double stamp=store.get(book.id).syncUpdated;
        store.applySyncResponse(new JSONArray().put(remote(contract.getString("sha256"),3,true,stamp+1)));
        assertEquals(3,store.get(book.id).page);assertTrue(store.get(book.id).favorite);
    }
    @Test public void offlineNeverErasesProgressAndFavorites()throws Exception {
        LibraryStore.Book book=linked();book.page=7;book.favorite=true;store.save(book);
        try{LibrarySync.run(store,entries->{throw new IOException("offline");});fail();}catch(IOException expected){}
        assertEquals(7,new LibraryStore(context).get(book.id).page);assertTrue(new LibraryStore(context).get(book.id).favorite);
        book=store.get(book.id);book.favorite=false;store.save(book);
        JSONArray retry=new LibraryStore(context).prepareSyncPayload();assertFalse(retry.getJSONObject(0).getBoolean("favorite"));assertEquals(7,retry.getJSONObject(0).getInt("page"));
        assertTrue(retry.getJSONObject(0).getDouble("client_updated_at")>0);
    }
    @Test public void legacyUntouchedAndExistingReadStateMigrateWithoutReset()throws Exception {
        LibraryStore.Book book=linked();JSONObject legacy=book.json();legacy.remove("sync_updated_at");legacy.remove("item_key");legacy.put("page",6).put("favorite",true).put("updated",90);
        context.getSharedPreferences("library",0).edit().putString("items",new JSONArray().put(legacy).toString()).commit();
        JSONArray rows=new LibraryStore(context).prepareSyncPayload();assertEquals(90,rows.getJSONObject(0).getDouble("client_updated_at"),0);assertEquals(6,rows.getJSONObject(0).getInt("page"));assertTrue(rows.getJSONObject(0).getBoolean("favorite"));assertEquals(book.id,store.all().get(0).id);
    }
    @Test public void changedUriInvalidatesHashAndMissingAccessKeepsKnownIdentity()throws Exception {
        LibraryStore.Book book=linked();String first=store.prepareSyncPayload().getJSONObject(0).getString("item_key");int opens=provider.opens;
        Files.write(provider.file.toPath(),"changed comic bytes".getBytes());provider.modified++;
        JSONObject changed=store.prepareSyncPayload().getJSONObject(0);String next=changed.getString("item_key");assertNotEquals(first,next);assertTrue(provider.opens>opens);assertFalse(changed.has("legacy_keys"));
        store.applySyncResponse(new JSONArray().put(remote(book.id,20,true,System.currentTimeMillis()/1000.0+100)));
        assertEquals(0,store.get(book.id).page);
        provider.fail=true;assertEquals(next,store.prepareSyncPayload().getJSONObject(0).getString("item_key"));
    }
    @Test public void restoredLegacyBackupIsANewSyncEdit()throws Exception {
        LibraryStore.Book book=linked();store.prepareSyncPayload();
        JSONObject backup=new JSONObject().put("format","panel-android").put("version",1).put("items",new JSONArray().put(book.json().put("page",4).put("favorite",true)));
        assertEquals(1,store.restoreBackup(new ByteArrayInputStream(backup.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8))));
        JSONObject row=store.prepareSyncPayload().getJSONObject(0);assertEquals(4,row.getInt("page"));assertTrue(row.getBoolean("favorite"));assertTrue(row.getDouble("client_updated_at")>0);
    }
    @Test public void requestsAndLocalMergeRemainBatched()throws Exception {
        JSONArray books=new JSONArray();for(int i=0;i<5001;i++){
            LibraryStore.Book book=new LibraryStore.Book();book.id=String.format(Locale.ROOT,"%064x",i);book.title="Fixture";book.file="fixture.cbz";books.put(book.json());
        }
        context.getSharedPreferences("library",0).edit().putString("items",books.toString()).commit();List<Integer> sizes=new ArrayList<>();
        LibrarySync.run(store,entries->{sizes.add(entries.length());return new JSONArray();});assertEquals(Arrays.asList(5000,1),sizes);assertEquals(5001,store.all().size());
    }
    @Test public void automaticSyncDebouncesRepeatedChanges()throws Exception {
        context.getSharedPreferences("auth_state",0).edit().putString("mode","guest").commit();
        org.robolectric.android.controller.ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class).create();
        MainActivity activity=controller.get();RecordingExecutor executor=new RecordingExecutor();
        try{
            android.os.Handler handler=(android.os.Handler)field(activity,"handler").get(activity);handler.removeCallbacksAndMessages(null);
            ((java.util.concurrent.ExecutorService)field(activity,"syncWork").get(activity)).shutdownNow();field(activity,"syncWork").set(activity,executor);
            field(activity,"syncActive").setBoolean(activity,true);
            PanelApi api=(PanelApi)field(activity,"api").get(activity);field(api,"token").set(api,"isolated-test");
            java.lang.reflect.Method schedule=MainActivity.class.getDeclaredMethod("scheduleSync");schedule.setAccessible(true);
            schedule.invoke(activity);Shadows.shadowOf(android.os.Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(1000));
            schedule.invoke(activity);Shadows.shadowOf(android.os.Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(1499));assertEquals(0,executor.calls);
            Shadows.shadowOf(android.os.Looper.getMainLooper()).idleFor(java.time.Duration.ofMillis(1));assertEquals(1,executor.calls);
        }finally{controller.destroy();context.getSharedPreferences("auth_state",0).edit().clear().commit();}
    }
    @Test(timeout=10000) public void heavyHashDoesNotLockLibraryAndSnapshotUsesLatestEdit()throws Exception {
        LibraryStore.Book book=linked();java.util.concurrent.CountDownLatch started=new java.util.concurrent.CountDownLatch(1),release=new java.util.concurrent.CountDownLatch(1);
        Shadows.shadowOf(context.getContentResolver()).registerInputStreamSupplier(URI,()->{
            try{return new FilterInputStream(new FileInputStream(provider.file)){
                public int read(byte[] bytes,int offset,int length)throws IOException {
                    started.countDown();try{if(!release.await(5,java.util.concurrent.TimeUnit.SECONDS))throw new IOException("test timeout");}catch(InterruptedException interrupted){throw new IOException(interrupted);}
                    return super.read(bytes,offset,length);
                }
            };}catch(IOException error){throw new IllegalStateException(error);}
        });
        java.util.concurrent.ExecutorService worker=java.util.concurrent.Executors.newSingleThreadExecutor();
        try{
            java.util.concurrent.Future<JSONArray> task=worker.submit(()->store.prepareSyncPayload());assertTrue(started.await(3,java.util.concurrent.TimeUnit.SECONDS));
            book.page=5;store.save(book);release.countDown();assertEquals(5,task.get(3,java.util.concurrent.TimeUnit.SECONDS).getJSONObject(0).getInt("page"));
        }finally{release.countDown();worker.shutdownNow();}
    }
    private static java.lang.reflect.Field field(Object object,String name)throws Exception {java.lang.reflect.Field field=object.getClass().getDeclaredField(name);field.setAccessible(true);return field;}
    static class RecordingExecutor extends java.util.concurrent.AbstractExecutorService {
        int calls;boolean closed;
        public void execute(Runnable work){calls++;}
        public void shutdown(){closed=true;}
        public List<Runnable> shutdownNow(){closed=true;return Collections.emptyList();}
        public boolean isShutdown(){return closed;}
        public boolean isTerminated(){return closed;}
        public boolean awaitTermination(long timeout,java.util.concurrent.TimeUnit unit){return closed;}
    }
    public static class FixtureProvider extends ContentProvider {
        File file;int opens;long modified=10;boolean fail;
        public boolean onCreate(){return true;}
        public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){
            if(fail)throw new SecurityException("fixture denied");MatrixCursor cursor=new MatrixCursor(projection);Object[] row=new Object[projection.length];
            for(int i=0;i<projection.length;i++)row[i]=OpenableColumns.DISPLAY_NAME.equals(projection[i])?"Comic.cbz":OpenableColumns.SIZE.equals(projection[i])?file.length():DocumentsContract.Document.COLUMN_LAST_MODIFIED.equals(projection[i])?modified:0;
            cursor.addRow(row);return cursor;
        }
        public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException {if(fail)throw new SecurityException("fixture denied");opens++;return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);}
        public String getType(Uri uri){return "application/zip";}
        public Uri insert(Uri uri,ContentValues values){return null;}
        public int delete(Uri uri,String selection,String[] args){return 0;}
        public int update(Uri uri,ContentValues values,String selection,String[] args){return 0;}
    }
}

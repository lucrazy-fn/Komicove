package com.lucrazy.komicove;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import org.json.*;
import okhttp3.*;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.*;

/** Physical-device checks, restricted to the isolated .phase5test package. */
public final class LibraryPhase5Instrumentation extends Instrumentation {
    private static final Uri URI=Uri.parse("content://com.lucrazy.komicove.phase5fixtures/comic");
    private final OkHttpClient http=new OkHttpClient.Builder().connectTimeout(2,TimeUnit.SECONDS).readTimeout(30,TimeUnit.SECONDS).build();
    private final StringBuilder log=new StringBuilder();private Bundle options;private String base;
    private LibraryStore store;private Activity active;
    @Override public void onCreate(Bundle args){super.onCreate(args);options=args==null?new Bundle():args;start();}
    @Override public void onStart(){Bundle result=new Bundle();int status=Activity.RESULT_OK;
        try{
            require(getTargetContext().getPackageName().endsWith(".phase5test"),"Use tools/phase5-device.gradle");
            base=options.getString("base","http://127.0.0.1:18565");
            require(base.startsWith("http://127.0.0.1:"),"Only the disposable local server is allowed");
            Context context=getTargetContext();store=new LibraryStore(context);
            JSONObject info=json("GET","/phase5/info",null);require(info.optBoolean("fixture"),"Wrong server");
            String key=info.getString("item_key"),id=info.getString("legacy_key");
            if(options.getString("verifyOnly","").equals("true")){
                LibraryStore.Book persisted=store.get(id);require(persisted!=null&&persisted.page==3&&persisted.favorite,"State lost after process restart");
                require(persisted.itemKey.equals(key),"Identity lost after process restart");assertLocalDomains(persisted);
                pass("cold process restart preserves identity, reading, favorites and local fields");
            }else{
                context.getSharedPreferences("library",0).edit().clear().commit();
                context.getSharedPreferences("content_identity",0).edit().clear().commit();
                context.getSharedPreferences("auth_state",0).edit().putString("mode","guest").commit();
                Bundle fixture=new Bundle();fixture.putByteArray("bytes",bytes("/phase5/fixture"));
                context.getContentResolver().call(URI,"fixture",null,fixture);
                require(store.linkUris(Collections.singletonList(URI))==1,"URI import failed");
                LibraryStore.Book book=store.get(id);require(book!=null,"Legacy URI ID changed");book.count=info.getInt("pages");
                book.collection="Local fixture";book.marks.put(4);book.customPanels.put("3",new JSONArray().put("manual"));book.retained.put("future_fixture",42);store.save(book);
                JSONArray first=store.prepareSyncPayload();JSONObject row=first.getJSONObject(0);
                require(key.equals(row.getString("item_key")),"PC/URI digest mismatch");require(row.isNull("page"),"Untouched import published a reading reset");
                require(row.getJSONArray("legacy_keys").toString().contains(id),"Missing legacy migration alias");
                pass("original PC bytes and real ContentResolver URI have the same portable key");
                synchronize();book=new LibraryStore(context).get(id);require(book.page==7&&book.favorite,"PC -> Android failed");assertLocalDomains(book);
                JSONObject pc=json("GET","/phase5/pc-state",null);require(pc.getBoolean("legacy_alias"),"Existing account alias was not migrated");
                pass("PC -> Android plus existing-account legacy alias migration");
                int opens=opens();store.prepareSyncPayload();new LibraryStore(context).prepareSyncPayload();require(opens==opens(),"Unchanged URI was rehashed");
                pass("persisted hash cache avoids reopening unchanged URI");
                book.page=12;book.favorite=false;store.save(book);synchronize();assertPC(12,false);
                pass("Android -> PC, including removal of an existing favorite");
                LibrarySync.run(store,entries->{JSONArray remote=exchange(entries);LibraryStore.Book edited=store.get(id);edited.page=6;edited.favorite=true;store.save(edited);return remote;});
                book=store.get(id);require(book.page==6&&book.favorite,"Network response overwrote a newer local edit");synchronize();assertPC(6,true);
                pass("inflight edit remains local and then reaches PC");
                json("POST","/phase5/pc-edit",new JSONObject().put("page",2).put("favorite",false).put("minimum_stamp",book.syncUpdated));
                synchronize();book=store.get(id);require(book.page==2&&!book.favorite,"Newer PC edit lost");
                for(double stamp:new double[]{book.syncUpdated-1,book.syncUpdated}){
                    JSONArray rejected=exchange(new JSONArray().put(new JSONObject().put("item_key",key).put("page",15).put("favorite",true).put("client_updated_at",stamp)));
                    JSONObject kept=find(rejected,key);require(kept.getInt("page")==2&&!kept.getBoolean("favorite"),"Older/tied conflict changed persisted server state");
                }
                pass("newer client_updated_at wins; positive ties preserve server state");
                book=store.get(id);book.page=5;book.favorite=true;store.save(book);
                boolean unavailable=false;try{LibrarySync.run(store,entries->{try(Response response=http.newCall(new Request.Builder().url("http://127.0.0.1:18566/account/library-state").build()).execute()){throw new IOException("No fixture server");}});}catch(IOException expected){unavailable=true;}
                book=new LibraryStore(context).get(id);require(unavailable&&book.page==5&&book.favorite,"Offline state was lost");synchronize();assertPC(5,true);
                pass("real connection failure preserves persisted state; retry reaches PC");
                checkBatches(context);pass("5001 items use two batches of 5000 and 1");
                checkDebounce(context);pass("real main-thread Handler debounces automatic sync at 1500 ms");
                book=store.get(id);book.page=2;book.favorite=true;store.save(book);
                active=startActivitySync(new Intent(context,ReaderActivity.class).putExtra("book",id).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));ready(2);
                runOnMainSync(()->{try{Method jump=ReaderActivity.class.getDeclaredMethod("jump",int.class);jump.setAccessible(true);jump.invoke(active,3);}catch(Exception error){throw new RuntimeException(error);}});ready(3);closeActivity();
                book=new LibraryStore(context).get(id);require(book.page==3&&book.favorite,"Reader did not preserve reading/favorite");assertLocalDomains(book);
                synchronize();assertPC(3,true);pass("real reader opens URI, changes page and persists after closing");
            }
            result.putString("stream",log.toString());
        }catch(Throwable error){StringWriter trace=new StringWriter();error.printStackTrace(new PrintWriter(trace));status=Activity.RESULT_CANCELED;result.putString("stream",log+"FAIL "+trace);}
        finally{closeActivity();http.connectionPool().evictAll();http.dispatcher().executorService().shutdown();}
        finish(status,result);
    }
    private void synchronize()throws Exception{LibrarySync.run(store,this::exchange);}
    private JSONArray exchange(JSONArray entries)throws Exception{return (JSONArray)request("PUT","/account/library-state",new JSONObject().put("items",entries));}
    private JSONObject json(String method,String path,JSONObject body)throws Exception{return (JSONObject)request(method,path,body);}
    private Object request(String method,String path,JSONObject data)throws Exception{
        RequestBody body=data==null?null:RequestBody.create(data.toString(),MediaType.get("application/json"));
        try(Response response=http.newCall(new Request.Builder().url(base+path).method(method,body).build()).execute()){
            require(response.isSuccessful(),"Fixture HTTP "+response.code());return new JSONTokener(response.body().string()).nextValue();
        }
    }
    private byte[] bytes(String path)throws Exception{try(Response response=http.newCall(new Request.Builder().url(base+path).build()).execute()){require(response.isSuccessful(),"Fixture unavailable");return response.body().bytes();}}
    private void assertPC(int page,boolean favorite)throws Exception{JSONObject pc=json("GET","/phase5/pc-state",null);require(pc.getInt("page")==page&&pc.getBoolean("favorite")==favorite&&pc.getInt("extra")==42,"Desktop state mismatch");}
    private static JSONObject find(JSONArray rows,String key)throws Exception{for(int i=0;i<rows.length();i++)if(rows.getJSONObject(i).getString("item_key").equals(key))return rows.getJSONObject(i);throw new AssertionError("Missing canonical row");}
    private int opens(){return getTargetContext().getContentResolver().call(URI,"stats",null,null).getInt("opens");}
    private static void assertLocalDomains(LibraryStore.Book book)throws Exception{require(book.collection.equals("Local fixture")&&book.marks.getInt(0)==4&&book.customPanels.has("3")&&book.json().getInt("future_fixture")==42,"Local-only fields lost");}
    private void checkBatches(Context context)throws Exception{
        SharedPreferences prefs=context.getSharedPreferences("library",0);String saved=prefs.getString("items","[]");
        try{JSONArray rows=new JSONArray();for(int i=0;i<5001;i++){LibraryStore.Book item=new LibraryStore.Book();item.id=String.format(Locale.ROOT,"%064x",i);item.file="batch.cbz";item.title="Batch fixture";rows.put(item.json());}
            prefs.edit().putString("items",rows.toString()).commit();List<Integer> sizes=new ArrayList<>();LibrarySync.run(store,entries->{sizes.add(entries.length());return new JSONArray();});require(sizes.equals(Arrays.asList(5000,1)),"Sync stopped batching");
        }finally{prefs.edit().putString("items",saved).commit();}
    }
    private void checkDebounce(Context context)throws Exception{
        active=startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));MainActivity main=(MainActivity)active;
        final RecordingExecutor recorder=new RecordingExecutor();
        runOnMainSync(()->{try{
            ((Handler)field(main,"handler")).removeCallbacksAndMessages(null);((ExecutorService)field(main,"syncWork")).shutdownNow();set(main,"syncWork",recorder);set(main,"syncActive",true);set(field(main,"api"),"token","disposable-fixture");invokeSchedule(main);
        }catch(Exception error){throw new RuntimeException(error);}});
        SystemClock.sleep(900);runOnMainSync(()->invokeSchedule(main));SystemClock.sleep(900);require(recorder.calls==0,"Debounce fired before last edit settled");
        long until=SystemClock.elapsedRealtime()+3000;while(recorder.calls==0&&SystemClock.elapsedRealtime()<until)SystemClock.sleep(20);require(recorder.calls==1,"Automatic sync did not fire once");closeActivity();
    }
    private static void invokeSchedule(MainActivity main){try{Method method=MainActivity.class.getDeclaredMethod("scheduleSync");method.setAccessible(true);method.invoke(main);}catch(Exception error){throw new RuntimeException(error);}}
    private void ready(int page)throws Exception{long end=SystemClock.elapsedRealtime()+20000;do{waitForIdleSync();if((int)field(active,"displayedPage")==page&&!(boolean)field(active,"loading"))return;SystemClock.sleep(30);}while(SystemClock.elapsedRealtime()<end);throw new AssertionError("Reader page load timed out");}
    private void closeActivity(){if(active==null)return;Activity closing=active;active=null;runOnMainSync(closing::finish);waitForIdleSync();}
    private static Object field(Object object,String name)throws Exception{Field field=object.getClass().getDeclaredField(name);field.setAccessible(true);return field.get(object);}
    private static void set(Object object,String name,Object value)throws Exception{Field field=object.getClass().getDeclaredField(name);field.setAccessible(true);field.set(object,value);}
    private void pass(String message){log.append("PASS ").append(message).append('\n');}
    private static void require(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    static final class RecordingExecutor extends AbstractExecutorService{
        volatile int calls;boolean closed;public void execute(Runnable task){calls++;}public void shutdown(){closed=true;}public List<Runnable> shutdownNow(){closed=true;return Collections.emptyList();}public boolean isShutdown(){return closed;}public boolean isTerminated(){return closed;}public boolean awaitTermination(long timeout,TimeUnit unit){return closed;}
    }
}

package com.lucrazy.komicove;

import android.app.*;
import android.content.*;
import android.graphics.*;
import android.net.Uri;
import android.os.*;
import android.provider.DocumentsContract;
import org.json.*;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.zip.*;

/** Opt-in acceptance suite; refuses to run against the user's installed app. */
public final class FolderPhase2Instrumentation extends Instrumentation {
    private Bundle args;private final StringBuilder log=new StringBuilder();
    public void onCreate(Bundle args){super.onCreate(args);this.args=args;start();}
    public void onStart(){Bundle result=new Bundle();int code=Activity.RESULT_OK;
        try{
            require(getTargetContext().getPackageName().endsWith(".phase2test"),"Use isolated test app");
            Context target=getTargetContext();LibraryStore store=new LibraryStore(target);MonitoredFolders monitor=new MonitoredFolders(target,store);
            if(!args.getString("cleanup","false").equals("true"))require(!((android.app.KeyguardManager)target.getSystemService(Context.KEYGUARD_SERVICE)).isKeyguardLocked(),"Unlock the test device before running acceptance tests");
            if(args.getString("preview","false").equals("true")){showPreview(target,monitor);Thread.sleep(30000);log.append("PASS isolated visual preview\n");finish(code,bundle());return;}
            if(args.getString("cleanup","false").equals("true")){for(LibraryStore.Book book:store.all())require(book.uri.startsWith("content://"+FolderFixtureProvider.AUTHORITY+"/"),"Non-fixture book found: refusing cleanup");for(int i=0;i<monitor.folders().length();i++)require(monitor.folders().getJSONObject(i).getString("uri").startsWith("content://"+FolderFixtureProvider.AUTHORITY+"/"),"Non-fixture folder found: refusing cleanup");target.getSharedPreferences("library",0).edit().clear().commit();target.getSharedPreferences("library_folders",0).edit().clear().commit();cleanupFixtures();log.append("PASS isolated fixture cleanup\n");finish(code,bundle());return;}
            require(store.all().isEmpty(),"Test app already contains books; refusing to overwrite");
            provider("seed");provider("grant");
            for(String directory:new String[]{"Quadrinhos de teste","Leituras pendentes","Independentes"}){Uri tree=DocumentsContract.buildTreeDocumentUri(FolderFixtureProvider.AUTHORITY,"root/"+directory);monitor.add(tree);monitor.add(tree);}
            require(monitor.folders().length()==3,"Duplicate roots");require(monitor.scan().added==0,"Imported before settling");Thread.sleep(3200);require(monitor.scan().added==302,"Large folder import");require(store.all().size()==302,"Library size");require(monitor.scan().added==0,"Repeated duplicate import");
            require(target.getContentResolver().getPersistedUriPermissions().size()>=3,"SAF permission not persisted");require(new MonitoredFolders(target,store).folders().length()==3,"Registry reload");log.append("PASS 302 HQs, repeated folder, silent duplicates, persistent registry and SAF grants\n");
            LibraryStore.Book original=null;for(LibraryStore.Book book:store.all())if(book.title.equals("Teste 000"))original=book;require(original!=null,"Original missing");original.page=1;original.favorite=true;original.collection="Teste";store.save(original);String id=original.id;
            provider("move_first");monitor.scan();Thread.sleep(3200);require(monitor.scan().added==0,"Move duplicated book");require(store.get(id).uri.contains("Renomeada"),"Move not located");require(store.get(id).page==1&&store.get(id).favorite,"Move lost progress");
            provider("delete_first");monitor.scan();require(!store.get(id).available&&store.get(id).page==1,"Removed book lost data");
            provider("add_new");monitor.scan();Thread.sleep(3200);require(monitor.scan().added==1,"New file detection");log.append("PASS new, removed, cross-folder rename, progress/favorites retained\n");
            LibraryStore.Book red=null,blue=null;for(LibraryStore.Book book:store.all()){if(book.title.equals("Teste 001"))red=book;if(book.title.equals("Outra HQ"))blue=book;}
            try(BookSource a=new BookSource(store.file(red),target.getCacheDir());BookSource b=new BookSource(store.file(blue),target.getCacheDir())){Bitmap ar=a.page(0,100),bb=b.page(0,100);require(ar.getPixel(0,0)!=bb.getPixel(0,0),"Same internal filename collided");ar.recycle();bb.recycle();}
            log.append("PASS independent 001.jpg / 002.jpg across comics\n");
            for(LibraryStore.Book book:store.all())if(book.available&&book.uri.contains("Teste%20001"))store.prepareCover(book);
            for(LibraryStore.Book book:store.all())if(book.title.equals("Outra HQ")||book.title.equals("Nova HQ"))store.prepareCover(book);
            target.getSharedPreferences("auth_state",0).edit().putString("mode","guest").commit();
            showPreview(target,monitor);
            log.append("PASS native folder screen opens, existing header / navigation retained\n");
            int count=store.all().size();provider("add_automatic");long deadline=System.currentTimeMillis()+28000;
            while(store.all().size()==count&&System.currentTimeMillis()<deadline)Thread.sleep(300);
            require(store.all().size()==count+1,"Foreground watcher did not detect new HQ automatically");log.append("PASS automatic detection while folder screen is open\n");
        }catch(Throwable error){code=Activity.RESULT_CANCELED;StringWriter trace=new StringWriter();error.printStackTrace(new PrintWriter(trace));log.append("FAIL ").append(trace);}
        finish(code,bundle());
    }
    private Bundle bundle(){Bundle result=new Bundle();result.putString("stream",log.toString());return result;}
    private void showPreview(Context target,MonitoredFolders monitor)throws Exception{
        MainActivity activity=(MainActivity)startActivitySync(new Intent(target,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));waitForIdleSync();
        JSONArray snapshot=monitor.folders();
        runOnMainSync(()->{try{activity.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);Field rows=MainActivity.class.getDeclaredField("folderRows");rows.setAccessible(true);rows.set(activity,snapshot);Method show=MainActivity.class.getDeclaredMethod("showFolders");show.setAccessible(true);show.invoke(activity);}catch(Exception e){throw new RuntimeException(e);}});
    }
    private void cleanupFixtures(){provider("cleanup");}
    private void provider(String operation){Bundle result=getTargetContext().getContentResolver().call(Uri.parse("content://"+FolderFixtureProvider.AUTHORITY+".control"),operation,null,null);require(result!=null&&result.getBoolean("ok"),"Fixture provider: "+(result==null?"missing":result.getString("error")));}
    private static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
}

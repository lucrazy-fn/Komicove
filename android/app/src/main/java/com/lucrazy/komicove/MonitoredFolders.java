package com.lucrazy.komicove;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import org.json.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

/** SAF registry and foreground rescanner. No source document is modified. */
final class MonitoredFolders {
    static final long SETTLE_MS=3000, MAX_BYTES=768L*1024*1024;
    final Context context;final LibraryStore store;final android.content.SharedPreferences prefs;
    private final Object scanLock=new Object();
    MonitoredFolders(Context c,LibraryStore s){context=c.getApplicationContext();store=s;prefs=context.getSharedPreferences("library_folders",0);}
    synchronized JSONArray folders()throws JSONException{
        if(prefs.contains("registry"))return new JSONArray(prefs.getString("registry","[]"));
        JSONArray rows=new JSONArray();for(String uri:prefs.getStringSet("uris",Collections.emptySet()))rows.put(folder(uri));
        persist(rows);return rows;
    }
    private JSONObject folder(String uri)throws JSONException{return new JSONObject().put("uri",uri).put("name",displayName(uri)).put("enabled",true).put("count",0).put("checked",0).put("status","checking").put("new",0);}
    private String displayName(String uri){try{Uri root=Uri.parse(uri);return store.name(DocumentsContract.buildDocumentUriUsingTree(root,DocumentsContract.getTreeDocumentId(root)));}catch(Exception e){return "Pasta";}}
    private void persist(JSONArray rows){Set<String> roots=new LinkedHashSet<>();for(int i=0;i<rows.length();i++)roots.add(rows.optJSONObject(i).optString("uri"));if(!prefs.edit().putString("registry",rows.toString()).putStringSet("uris",roots).commit())throw new IllegalStateException("Não foi possível salvar as pastas.");}
    synchronized void add(Uri root)throws Exception{context.getContentResolver().takePersistableUriPermission(root,Intent.FLAG_GRANT_READ_URI_PERMISSION);JSONArray rows=folders();for(int i=0;i<rows.length();i++)if(root.toString().equals(rows.getJSONObject(i).getString("uri")))return;rows.put(folder(root.toString()));persist(rows);}
    synchronized void configure(String uri,String name,Boolean enabled,boolean remove)throws Exception{JSONArray result=new JSONArray(),rows=folders();for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);if(uri.equals(row.getString("uri"))){if(remove)continue;if(name!=null&&!name.trim().isEmpty())row.put("name",name.trim());if(enabled!=null)row.put("enabled",enabled);}result.put(row);}persist(result);}
    List<LibraryStore.Book> visibleBooks(){
        Set<String> disabled=new HashSet<>();JSONArray registry;
        try{registry=new JSONArray(prefs.getString("registry","[]"));}catch(JSONException error){android.util.Log.w("Komicove","Folder visibility preferences could not be read");return store.all();}
        for(int i=0;i<registry.length();i++){JSONObject row=registry.optJSONObject(i);if(row!=null&&!row.optBoolean("enabled",true))disabled.add(row.optString("uri"));}
        List<LibraryStore.Book> result=new ArrayList<>();
        for(LibraryStore.Book book:store.all()){
            boolean visible=book.uri.isEmpty()||book.sources.length()==0;
            for(int i=0;!visible&&i<book.sources.length();i++){JSONObject source=book.sources.optJSONObject(i);if(source!=null&&!disabled.contains(source.optString("folder")))visible=true;}
            if(visible)result.add(book);
        }
        return result;
    }
    private void list(Uri root,Uri directory,List<JSONObject> out,Set<String> visited,int depth)throws Exception{
        if(depth>32||visited.size()>100000)throw new IOException("Limite de arquivos da pasta.");
        String id=DocumentsContract.getDocumentId(directory);if(!visited.add(id))return;
        Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(root,id);
        String[] projection={DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE,DocumentsContract.Document.COLUMN_SIZE,DocumentsContract.Document.COLUMN_LAST_MODIFIED,DocumentsContract.Document.COLUMN_FLAGS};
        try(Cursor cursor=context.getContentResolver().query(children,projection,null,null,null)){
            if(cursor==null)throw new IOException("Pasta indisponível.");
            while(cursor.moveToNext()){BookSource.checkCancelled();Uri uri=DocumentsContract.buildDocumentUriUsingTree(root,cursor.getString(0));String name=cursor.getString(1);
                if(DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(2)))list(root,uri,out,visited,depth+1);
                else if(name!=null&&BookSource.supported(name)){if(out.size()>=100000)throw new IOException("Limite de arquivos da pasta.");out.add(new JSONObject().put("uri",uri.toString()).put("name",name).put("folder",root.toString()).put("size",cursor.isNull(3)?-1:cursor.getLong(3)).put("modified",cursor.isNull(4)?0:cursor.getLong(4)).put("partial",(cursor.getInt(5)&DocumentsContract.Document.FLAG_PARTIAL)!=0));}
            }
        }
    }
    private JSONObject signature(Uri uri)throws Exception{
        try(Cursor c=context.getContentResolver().query(uri,new String[]{DocumentsContract.Document.COLUMN_SIZE,DocumentsContract.Document.COLUMN_LAST_MODIFIED},null,null,null)){
            if(c==null||!c.moveToFirst())throw new IOException("Arquivo indisponível.");return new JSONObject().put("size",c.isNull(0)?-1:c.getLong(0)).put("modified",c.isNull(1)?0:c.getLong(1));
        }
    }
    private static boolean same(JSONObject a,JSONObject b){return a.optLong("size")==b.optLong("size")&&a.optLong("modified")==b.optLong("modified");}
    private static final class InvalidArchive extends IOException{InvalidArchive(){super("HQ inválida ou fora dos limites de segurança.");}}
    private String fingerprint(JSONObject entry)throws Exception{
        Uri uri=Uri.parse(entry.getString("uri"));String name=entry.getString("name");File temp=File.createTempFile("folder-check-",name.substring(name.lastIndexOf('.')),context.getCacheDir());
        try{MessageDigest digest=MessageDigest.getInstance("SHA-256");long total=0;
            try(InputStream in=context.getContentResolver().openInputStream(uri);OutputStream out=new FileOutputStream(temp)){
                if(in==null)throw new IOException("Arquivo indisponível.");byte[] buffer=new byte[65536];int n;
                while((n=in.read(buffer))!=-1){BookSource.checkCancelled();total+=n;if(total>MAX_BYTES)throw new IOException("Arquivo maior que 768 MB.");digest.update(buffer,0,n);out.write(buffer,0,n);}
            }
            if(!same(entry,signature(uri))||entry.optLong("size",-1)>=0&&total!=entry.optLong("size"))throw new IOException("Arquivo ainda sendo copiado.");
            try(BookSource source=new BookSource(temp,context.getCacheDir())){if(source.pages.isEmpty())throw new InvalidArchive();}catch(Exception error){BookSource.checkCancelled();throw new InvalidArchive();}
            StringBuilder hash=new StringBuilder();for(byte value:digest.digest())hash.append(String.format(Locale.ROOT,"%02x",value&255));return hash.toString();
        }finally{temp.delete();}
    }
    static final class Result{int added,duplicates,invalid;boolean waiting,changed;}
    Result scan()throws Exception{synchronized(scanLock){return scanLocked();}}
    private Result scanLocked()throws Exception{
        JSONArray rows=folders();JSONObject observations=new JSONObject(prefs.getString("observations","{}")),next=new JSONObject();Map<String,JSONObject> known=new HashMap<>();
        JSONObject validated=new JSONObject(prefs.getString("validated","{}"));Iterator<String> saved=validated.keys();while(saved.hasNext()){String uri=saved.next();known.put(uri,validated.getJSONObject(uri));}
        for(LibraryStore.Book b:store.all())for(int i=0;i<b.sources.length();i++){JSONObject source=b.sources.getJSONObject(i);known.put(source.optString("uri"),source);}
        List<JSONObject> accepted=new ArrayList<>();Set<String> scanned=new HashSet<>(),unavailable=new HashSet<>();Result result=new Result();long now=System.currentTimeMillis();
        String before=prefs.getString("last-library","");
        for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);if(!row.optBoolean("enabled",true))continue;String rootString=row.getString("uri");
            List<JSONObject> candidates=new ArrayList<>();try{Uri root=Uri.parse(rootString);list(root,DocumentsContract.buildDocumentUriUsingTree(root,DocumentsContract.getTreeDocumentId(root)),candidates,new HashSet<>(),0);}catch(Exception e){BookSource.checkCancelled();row.put("status","unavailable").put("checked",now).put("error",e.getClass().getSimpleName());unavailable.add(rootString);continue;}
            scanned.add(rootString);int count=0;boolean pending=false;
            for(JSONObject entry:candidates){String uri=entry.getString("uri");JSONObject cached=known.get(uri),seen=observations.optJSONObject(uri);
                if(cached!=null&&same(entry,cached)&&!entry.optBoolean("partial")){entry.put("hash",cached.getString("hash")).put("available",true);accepted.add(entry);count++;result.duplicates++;continue;}
                if(seen==null||!same(seen,entry)){seen=new JSONObject(entry.toString()).put("since",now);}next.put(uri,seen);
                if(entry.optBoolean("partial")||now-seen.optLong("since",now)<SETTLE_MS){pending=true;continue;}
                if(seen.optBoolean("invalid")){result.invalid++;continue;}
                if(entry.optLong("size")>MAX_BYTES||entry.optLong("size")==0){result.invalid++;continue;}
                try{entry.put("hash",fingerprint(entry)).put("available",true);accepted.add(entry);count++;next.remove(uri);}catch(Exception e){BookSource.checkCancelled();if(e instanceof InvalidArchive)seen.put("invalid",true);result.invalid++;}
            }
            row.put("count",count).put("status",pending?"checking":"updated").put("checked",now);result.waiting|=pending;
        }
        Set<String> previous=new HashSet<>();for(LibraryStore.Book book:store.all())previous.add(book.fingerprint.isEmpty()?book.id:book.fingerprint);
        BookSource.checkCancelled();result.added=store.reconcileFolders(accepted,scanned,unavailable);Set<String> ids=new HashSet<>();Map<String,Set<String>> newByFolder=new HashMap<>();
        Map<String,Set<String>> countByFolder=new HashMap<>();
        for(LibraryStore.Book book:store.all())for(int j=0;j<book.sources.length();j++){JSONObject source=book.sources.getJSONObject(j);countByFolder.computeIfAbsent(source.optString("folder"),k->new HashSet<>()).add(book.id);}
        for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);row.put("count",countByFolder.getOrDefault(row.getString("uri"),Collections.emptySet()).size());}
        JSONObject freshValidated=new JSONObject();for(JSONObject entry:accepted)freshValidated.put(entry.getString("uri"),entry);
        result.duplicates=0;for(JSONObject entry:accepted){String hash=entry.getString("hash"),root=entry.getString("folder");if(previous.contains(hash)||!ids.add(hash))result.duplicates++;if(!previous.contains(hash))newByFolder.computeIfAbsent(root,k->new HashSet<>()).add(hash);}
        JSONArray identity=new JSONArray();for(LibraryStore.Book b:store.all())identity.put(new JSONObject().put("id",b.id).put("uri",b.uri).put("available",b.available));result.changed=!identity.toString().equals(before);
        if(!prefs.edit().putString("observations",next.toString()).putString("validated",freshValidated.toString()).putString("last-library",identity.toString()).commit())throw new IOException("Não foi possível salvar as pastas.");
        synchronized(this){JSONArray current=folders();for(int i=0;i<current.length();i++){JSONObject row=current.getJSONObject(i);for(int j=0;j<rows.length();j++){JSONObject checked=rows.getJSONObject(j);if(row.getString("uri").equals(checked.getString("uri"))){for(String field:new String[]{"count","status","checked"})row.put(field,checked.opt(field));row.put("new",newByFolder.getOrDefault(row.getString("uri"),Collections.emptySet()).size());}}}persist(current);}return result;
    }
}

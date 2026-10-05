package com.lucrazy.komicove;

import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import org.json.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.Locale;

/** Sync v2 hashes ordered image bytes; raw digests remain migration aliases. */
final class ContentIdentity {
    private final Context context;
    private final SharedPreferences prefs;
    private final JSONObject index;
    private boolean dirty;
    ContentIdentity(Context context)throws JSONException {
        this.context=context; prefs=context.getSharedPreferences("content_identity",0);
        JSONObject loaded;
        try{loaded=new JSONObject(prefs.getString("index","{}"));}catch(JSONException corrupt){loaded=new JSONObject();}
        index=loaded;
    }
    private JSONObject signature(Uri uri)throws IOException,JSONException {
        long size=-1,modified=0;
        try(Cursor cursor=context.getContentResolver().query(uri,new String[]{OpenableColumns.SIZE,DocumentsContract.Document.COLUMN_LAST_MODIFIED},null,null,null)){
            if(cursor!=null&&cursor.moveToFirst()){
                int s=cursor.getColumnIndex(OpenableColumns.SIZE),m=cursor.getColumnIndex(DocumentsContract.Document.COLUMN_LAST_MODIFIED);
                if(s>=0&&!cursor.isNull(s))size=cursor.getLong(s);
                if(m>=0&&!cursor.isNull(m))modified=cursor.getLong(m);
            }
        }catch(IllegalArgumentException unsupported){
            try(Cursor cursor=context.getContentResolver().query(uri,new String[]{OpenableColumns.SIZE},null,null,null)){
                if(cursor!=null&&cursor.moveToFirst()&&!cursor.isNull(0))size=cursor.getLong(0);
            }
        }
        return new JSONObject().put("size",size).put("modified",modified);
    }
    private static boolean same(JSONObject a,JSONObject b){return a.optLong("size")==b.optLong("size")&&a.optLong("modified")==b.optLong("modified");}
    private String location(LibraryStore.Book book,File books){return book.uri.isEmpty()?new File(books,book.file).getAbsolutePath():book.uri;}
    String rawKey(LibraryStore.Book book,File books){JSONObject entry=index.optJSONObject(location(book,books));return entry!=null?entry.optString("sha256",""):book.id.matches("[0-9a-f]{64}")?book.id:"";}
    String key(LibraryStore.Book book,File books)throws Exception {
        String location=location(book,books);
        File file=new File(books,book.file);
        if(book.uri.isEmpty()&&!file.isFile()){
            if(!book.itemKey.isEmpty())return book.itemKey;
            if(book.id.matches("[0-9a-f]{64}"))return book.id;
            throw new IOException("Comic unavailable");
        }
        JSONObject before=book.uri.isEmpty()?new JSONObject().put("size",file.length()).put("modified",file.lastModified()):signature(Uri.parse(book.uri));
        JSONObject cached=index.optJSONObject(location);
        if(cached!=null&&same(cached,before)&&cached.optInt("identity_version")==2&&!cached.optString("item_key").isEmpty())return cached.getString("item_key");
        String raw=book.uri.isEmpty()&&book.id.matches("[0-9a-f]{64}")?book.id:"";
        File temporary=null;
        try{
            if(!book.uri.isEmpty())temporary=File.createTempFile("identity-",book.file.substring(book.file.lastIndexOf('.')),context.getCacheDir());
            if(temporary!=null||raw.isEmpty()){
                MessageDigest digest=MessageDigest.getInstance("SHA-256");long total=0;
                try(InputStream input=book.uri.isEmpty()?new FileInputStream(file):context.getContentResolver().openInputStream(Uri.parse(book.uri));OutputStream copy=temporary==null?null:new FileOutputStream(temporary)){
                    if(input==null)throw new IOException("Comic unavailable");byte[] buffer=new byte[1024*1024];int count;
                    while((count=input.read(buffer))!=-1){BookSource.checkCancelled();total+=count;if(total>MonitoredFolders.MAX_BYTES)throw new IOException("Comic exceeds import limit");digest.update(buffer,0,count);if(copy!=null)copy.write(buffer,0,count);}
                }
                if(before.optLong("size",-1)>=0&&total!=before.optLong("size"))throw new IOException("Comic changed while hashing");
                StringBuilder value=new StringBuilder();for(byte b:digest.digest())value.append(String.format(Locale.ROOT,"%02x",b&255));raw=value.toString();
            }
            String portable=raw;
            try(BookSource source=new BookSource(temporary==null?file:temporary,context.getCacheDir())){
                String value=source.contentKey();if(value!=null)portable=value;
            }catch(InterruptedIOException cancelled){throw cancelled;}
            catch(Exception unsupported){BookSource.checkCancelled();} // Existing raw identity remains valid for PDFs/unavailable decoders.
            JSONObject after=book.uri.isEmpty()?new JSONObject().put("size",file.length()).put("modified",file.lastModified()):signature(Uri.parse(book.uri));
            if(!same(before,after))throw new IOException("Comic changed while hashing");
            index.put(location,before.put("sha256",raw).put("item_key",portable).put("identity_version",2));dirty=true;return portable;
        }finally{if(temporary!=null)temporary.delete();}
    }
    void flush()throws IOException {
        if(dirty&&!prefs.edit().putString("index",index.toString()).commit())throw new IOException("Não foi possível salvar a biblioteca.");
        dirty=false;
    }
}

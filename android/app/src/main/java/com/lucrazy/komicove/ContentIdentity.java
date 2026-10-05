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

/** v1 item_key is the SHA-256 of original bytes, independent of path or SAF URI. */
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
    String key(LibraryStore.Book book,File books)throws Exception {
        if(book.uri.isEmpty()&&book.id.matches("[0-9a-f]{64}"))return book.id; // Import already hashed its copy.
        String location=book.uri.isEmpty()?new File(books,book.file).getAbsolutePath():book.uri;
        File file=new File(books,book.file);
        JSONObject before=book.uri.isEmpty()?new JSONObject().put("size",file.length()).put("modified",file.lastModified()):signature(Uri.parse(book.uri));
        JSONObject cached=index.optJSONObject(location);
        if(cached!=null&&same(cached,before))return cached.getString("sha256");
        // Folder scans validate content and metadata together; reuse their digest.
        for(int i=0;i<book.sources.length();i++){
            JSONObject source=book.sources.getJSONObject(i);
            if(location.equals(source.optString("uri"))&&same(source,before)&&source.optString("hash").matches("[0-9a-f]{64}")){
                String value=source.getString("hash");index.put(location,before.put("sha256",value));dirty=true;return value;
            }
        }
        MessageDigest digest=MessageDigest.getInstance("SHA-256");long total=0;
        try(InputStream in=book.uri.isEmpty()?new FileInputStream(file):context.getContentResolver().openInputStream(Uri.parse(book.uri))){
            if(in==null)throw new IOException("Comic unavailable");byte[] buffer=new byte[1024*1024];int count;
            while((count=in.read(buffer))!=-1){BookSource.checkCancelled();total+=count;if(total>MonitoredFolders.MAX_BYTES)throw new IOException("Comic exceeds import limit");digest.update(buffer,0,count);}
        }
        JSONObject after=book.uri.isEmpty()?new JSONObject().put("size",file.length()).put("modified",file.lastModified()):signature(Uri.parse(book.uri));
        if(!same(before,after)||before.optLong("size",-1)>=0&&total!=before.optLong("size"))throw new IOException("Comic changed while hashing");
        StringBuilder value=new StringBuilder();for(byte b:digest.digest())value.append(String.format(Locale.ROOT,"%02x",b&255));
        index.put(location,before.put("sha256",value.toString()));dirty=true;return value.toString();
    }
    void flush()throws IOException {
        if(dirty&&!prefs.edit().putString("index",index.toString()).commit())throw new IOException("Não foi possível salvar a biblioteca.");
        dirty=false;
    }
}

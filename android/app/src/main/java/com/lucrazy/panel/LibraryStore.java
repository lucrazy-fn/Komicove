package com.lucrazy.panel;

import android.content.*;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.net.Uri;
import android.provider.OpenableColumns;
import org.json.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

final class LibraryStore {
    static class Book {
        String series="",author="",issue="";boolean duplicateImport;String id,title,file,collection="";int page,count;int guidedPage=-1,guidedPanel=0;boolean favorite;double updated;float zoom=1,offsetX=0,offsetY=0;String mode="normal";JSONArray marks=new JSONArray(),readPages=new JSONArray();JSONObject customPanels=new JSONObject();long readingSeconds;boolean completed;
        JSONObject json()throws JSONException{return new JSONObject().put("series",series).put("author",author).put("issue",issue).put("id",id).put("title",title).put("file",file).put("collection",collection).put("page",page).put("count",count).put("favorite",favorite).put("updated",updated).put("zoom",zoom).put("offsetX",offsetX).put("offsetY",offsetY).put("mode",mode).put("marks",marks).put("guidedPage",guidedPage).put("guidedPanel",guidedPanel).put("readPages",readPages).put("readingSeconds",readingSeconds).put("completed",completed).put("customPanels",customPanels);}
        static Book parse(JSONObject j){Book b=new Book();b.series=j.optString("series");b.author=j.optString("author");b.issue=j.optString("issue");b.id=j.optString("id");b.title=j.optString("title");b.file=j.optString("file");b.collection=j.optString("collection");b.page=j.optInt("page");b.guidedPage=j.optInt("guidedPage",-1);b.guidedPanel=Math.max(0,j.optInt("guidedPanel",0));b.count=j.optInt("count");b.favorite=j.optBoolean("favorite");b.updated=j.optDouble("updated",0);b.zoom=(float)j.optDouble("zoom",1);b.offsetX=(float)j.optDouble("offsetX",0);b.offsetY=(float)j.optDouble("offsetY",0);b.mode=j.optString("mode","normal");b.marks=j.optJSONArray("marks");if(b.marks==null)b.marks=new JSONArray();b.readPages=j.optJSONArray("readPages");if(b.readPages==null)b.readPages=new JSONArray();b.readingSeconds=j.optLong("readingSeconds",0);b.completed=j.optBoolean("completed",false);b.customPanels=j.optJSONObject("customPanels");if(b.customPanels==null)b.customPanels=new JSONObject();return b;}
    }
    final Context context;final File books,covers;private final SharedPreferences prefs;
    LibraryStore(Context c){context=c.getApplicationContext();prefs=context.getSharedPreferences("library",0);books=new File(context.getFilesDir(),"books");covers=new File(context.getFilesDir(),"covers");books.mkdirs();covers.mkdirs();}
    synchronized List<Book> all(){List<Book> result=new ArrayList<>();try{JSONArray a=new JSONArray(prefs.getString("items","[]"));for(int i=0;i<a.length();i++)result.add(Book.parse(a.getJSONObject(i)));}catch(JSONException ignored){}result.sort((a,b)->Double.compare(b.updated,a.updated));return result;}
    synchronized Book get(String id){for(Book b:all())if(b.id.equals(id))return b;return null;}
    synchronized void save(Book book){List<Book> list=all();list.removeIf(b->b.id.equals(book.id));list.add(book);write(list);}
    private void write(List<Book> list){JSONArray a=new JSONArray();try{for(Book b:list)a.put(b.json());}catch(JSONException e){throw new IllegalStateException(e);}if(!prefs.edit().putString("items",a.toString()).commit())throw new IllegalStateException("Não foi possível salvar a biblioteca.");}
    synchronized void remove(Book b){List<Book> list=all();list.removeIf(x->x.id.equals(b.id));write(list);file(b).delete();cover(b).delete();}
    File file(Book b){return new File(books,b.file);}
    File cover(Book b){return new File(covers,b.id+".jpg");}
    void replaceCover(Book book,Uri uri)throws IOException {
        android.graphics.BitmapFactory.Options opts=new android.graphics.BitmapFactory.Options();opts.inJustDecodeBounds=true;
        try(InputStream in=context.getContentResolver().openInputStream(uri)){android.graphics.BitmapFactory.decodeStream(in,null,opts);}
        if(opts.outWidth<=0||opts.outHeight<=0)throw new IOException("Imagem inválida.");
        opts.inSampleSize=1;while(Math.max(opts.outWidth,opts.outHeight)/opts.inSampleSize>1200)opts.inSampleSize*=2;opts.inJustDecodeBounds=false;
        Bitmap bitmap;try(InputStream in=context.getContentResolver().openInputStream(uri)){bitmap=android.graphics.BitmapFactory.decodeStream(in,null,opts);}
        if(bitmap==null)throw new IOException("Não foi possível abrir a capa.");
        File temp=File.createTempFile("cover-",".jpg",covers);
        try {try(OutputStream out=new FileOutputStream(temp)){if(!bitmap.compress(Bitmap.CompressFormat.JPEG,88,out))throw new IOException("Falha ao salvar capa.");}
            if(!temp.renameTo(cover(book)))throw new IOException("Falha ao substituir capa.");
        }finally{bitmap.recycle();temp.delete();}
    }
    Book nextIssue(Book current){return ReadingOrder.next(current,all());}
    String name(Uri uri){String name="";try(Cursor c=context.getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(c!=null&&c.moveToFirst())name=c.getString(0);}catch(Exception ignored){}return name.isEmpty()?"Quadrinho.cbz":name;}
    Book importUri(Uri uri)throws Exception {try(InputStream in=context.getContentResolver().openInputStream(uri)){if(in==null)throw new IOException("Arquivo indisponível.");return importStream(in,name(uri));}}
    Book importStream(InputStream in,String name)throws Exception {
        if(!BookSource.supported(name))throw new IOException("Use CBZ, ZIP, PDF, CBR, RAR, 7Z, CB7, TAR, CBT ou EPUB de HQ.");
        File temp=File.createTempFile("import-",".part",books);File finalFile=null;boolean added=false;
        try{
            MessageDigest hash=MessageDigest.getInstance("SHA-256");long total=0;
            try(OutputStream out=new FileOutputStream(temp)){byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1){total+=n;if(total>768L*1024*1024)throw new IOException("Limite de importação: 768 MB por arquivo.");if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();hash.update(buffer,0,n);out.write(buffer,0,n);}}
            StringBuilder hex=new StringBuilder();for(byte b:hash.digest())hex.append(String.format(Locale.ROOT,"%02x",b&255));String id=hex.toString();
            Book existing=get(id);if(existing!=null){temp.delete();existing.duplicateImport=true;return existing;}
            String extension=name.substring(name.lastIndexOf('.')).toLowerCase(Locale.ROOT);finalFile=new File(books,id+extension);
            if(!temp.renameTo(finalFile))throw new IOException("Não foi possível salvar o arquivo.");
            Book b=new Book();b.id=id;b.file=finalFile.getName();b.title=name.substring(0,name.lastIndexOf('.'));b.updated=System.currentTimeMillis()/1000.0;
            try(BookSource source=new BookSource(finalFile,context.getCacheDir())){b.count=source.pages.size();Bitmap image=source.page(0,320);try(OutputStream out=new FileOutputStream(cover(b))){image.compress(Bitmap.CompressFormat.JPEG,85,out);}image.recycle();}
            save(b);added=true;return b;
        }finally{temp.delete();if(!added&&finalFile!=null)finalFile.delete();}
    }
    synchronized void exportBackup(OutputStream out)throws Exception {JSONArray a=new JSONArray();for(Book b:all())a.put(b.json());JSONObject root=new JSONObject().put("format","panel-android").put("version",1).put("items",a);out.write(root.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8));}
    synchronized int restoreBackup(InputStream in)throws Exception {
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buf=new byte[4096];int n;while((n=in.read(buf))!=-1){if(out.size()+n>5*1024*1024)throw new IOException("Backup grande demais.");out.write(buf,0,n);}
        JSONObject root=new JSONObject(out.toString("UTF-8"));if(!root.optString("format").equals("panel-android")||root.optInt("version")!=1)throw new IOException("Use um backup do PANEL Android.");
        JSONArray a=root.getJSONArray("items");List<Book> list=all();int restored=0;
        for(Book local:list)for(int i=0;i<a.length();i++){JSONObject j=a.getJSONObject(i);if(local.id.equals(j.optString("id"))){local.page=Math.max(0,Math.min(local.count-1,j.optInt("page")));local.favorite=j.optBoolean("favorite");local.collection=j.optString("collection");local.marks=j.optJSONArray("marks");if(local.marks==null)local.marks=new JSONArray();local.updated=System.currentTimeMillis()/1000.0;restored++;break;}}
        write(list);return restored;
    }
}

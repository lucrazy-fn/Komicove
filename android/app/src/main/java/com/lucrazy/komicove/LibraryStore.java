package com.lucrazy.komicove;

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
        JSONObject retained=new JSONObject();String itemKey="",legacyItemKey="";double syncUpdated;boolean available=true;String fingerprint="";JSONArray sources=new JSONArray();
        String series="",author="",issue="",uri="";boolean duplicateImport;String id,title,file,collection="";int page,count;int guidedPage=-1,guidedPanel=0;boolean favorite;double updated;float zoom=1,offsetX=0,offsetY=0;String mode="normal";JSONArray marks=new JSONArray(),readPages=new JSONArray();JSONObject customPanels=new JSONObject();long readingSeconds;boolean completed;
        JSONObject json()throws JSONException{return new JSONObject(retained.toString()).put("item_key",itemKey).put("legacy_item_key",legacyItemKey).put("sync_updated_at",syncUpdated).put("available",available).put("fingerprint",fingerprint).put("sources",sources).put("series",series).put("author",author).put("issue",issue).put("id",id).put("title",title).put("file",file).put("uri",uri).put("collection",collection).put("page",page).put("count",count).put("favorite",favorite).put("updated",updated).put("zoom",zoom).put("offsetX",offsetX).put("offsetY",offsetY).put("mode",mode).put("marks",marks).put("guidedPage",guidedPage).put("guidedPanel",guidedPanel).put("readPages",readPages).put("readingSeconds",readingSeconds).put("completed",completed).put("customPanels",customPanels);}
        static Book parse(JSONObject j){Book b=new Book();try{b.retained=new JSONObject(j.toString());}catch(JSONException ignored){}b.itemKey=j.optString("item_key","");b.legacyItemKey=j.optString("legacy_item_key",b.itemKey);b.available=j.optBoolean("available",true);b.fingerprint=j.optString("fingerprint","");b.sources=j.optJSONArray("sources");if(b.sources==null)b.sources=new JSONArray();b.series=j.optString("series");b.author=j.optString("author");b.issue=j.optString("issue");b.id=j.optString("id");b.title=j.optString("title");b.file=j.optString("file");b.uri=j.optString("uri","");b.collection=j.optString("collection");b.page=j.optInt("page");b.guidedPage=j.optInt("guidedPage",-1);b.guidedPanel=Math.max(0,j.optInt("guidedPanel",0));b.count=j.optInt("count");b.favorite=j.optBoolean("favorite");b.updated=j.optDouble("updated",0);b.syncUpdated=j.optDouble("sync_updated_at",(b.favorite||b.page>0)?b.updated:0);b.zoom=(float)j.optDouble("zoom",1);b.offsetX=(float)j.optDouble("offsetX",0);b.offsetY=(float)j.optDouble("offsetY",0);b.mode=j.optString("mode","normal");b.marks=j.optJSONArray("marks");if(b.marks==null)b.marks=new JSONArray();b.readPages=j.optJSONArray("readPages");if(b.readPages==null)b.readPages=new JSONArray();if(!j.has("sync_updated_at")&&b.readPages.length()>0)b.syncUpdated=b.updated;b.readingSeconds=j.optLong("readingSeconds",0);b.completed=j.optBoolean("completed",false);b.customPanels=j.optJSONObject("customPanels");if(b.customPanels==null)b.customPanels=new JSONObject();return b;}
    }
    final Context context;final File books,covers;private final SharedPreferences prefs;
    LibraryStore(Context c){context=c.getApplicationContext();prefs=context.getSharedPreferences("library",0);books=new File(context.getFilesDir(),"books");covers=new File(context.getFilesDir(),"covers");books.mkdirs();covers.mkdirs();}
    synchronized List<Book> all(){List<Book> result=new ArrayList<>();try{JSONArray a=new JSONArray(prefs.getString("items","[]"));for(int i=0;i<a.length();i++)result.add(Book.parse(a.getJSONObject(i)));}catch(JSONException ignored){}result.sort((a,b)->Double.compare(b.updated,a.updated));return result;}
    synchronized Book get(String id){for(Book b:all())if(b.id.equals(id))return b;return null;}
    synchronized void save(Book book){
        List<Book> list=all();
        for(Book current:list)if(current.id.equals(book.id)){
            // Identity and sources belong to the store, not a stale reader snapshot.
            book.itemKey=current.itemKey;book.legacyItemKey=current.legacyItemKey;
            Iterator<String> retainedKeys=current.retained.keys();
            while(retainedKeys.hasNext()){String key=retainedKeys.next();if(!book.retained.has(key))try{book.retained.put(key,current.retained.get(key));}catch(JSONException invalid){throw new IllegalStateException(invalid);}}
            if(current.sources.length()>0||!current.sources.toString().equals(book.sources.toString())){
                book.uri=current.uri;book.file=current.file;book.sources=current.sources;book.available=current.available;book.fingerprint=current.fingerprint;
            }
            if(book.page!=current.page||book.favorite!=current.favorite||book.updated>current.updated&&book.readPages.length()>0)
                book.syncUpdated=Math.max(System.currentTimeMillis()/1000.0,current.syncUpdated+.000001);
            else book.syncUpdated=Math.max(book.syncUpdated,current.syncUpdated);
            break;
        }
        list.removeIf(b->b.id.equals(book.id));list.add(book);write(list);
    }
    JSONArray prepareSyncPayload()throws Exception {
        List<Book> snapshot=all();ContentIdentity identity=new ContentIdentity(context);
        Map<String,String> keys=new HashMap<>(),rawKeys=new HashMap<>();
        try{
            for(Book book:snapshot){
                try{String key=identity.key(book,books);keys.put(book.id,key);rawKeys.put(book.id,identity.rawKey(book,books));}catch(IOException|SecurityException unavailable){
                    if(!book.itemKey.isEmpty())keys.put(book.id,book.itemKey);
                    else if(book.id.matches("[0-9a-f]{64}"))keys.put(book.id,book.id);
                }
            }
        }finally{identity.flush();}
        synchronized(this){
        List<Book> current=all();boolean changed=false;JSONArray payload=new JSONArray();
        for(Book book:current){String key=keys.get(book.id);if(key==null)continue;
            String raw=rawKeys.getOrDefault(book.id,"");
            if(book.legacyItemKey.isEmpty()&&book.id.startsWith("uri-")){book.legacyItemKey=raw;changed=true;}
            if(!key.equals(book.itemKey)){book.itemKey=key;changed=true;}
            JSONObject row=new JSONObject().put("item_key",key).put("page",book.syncUpdated==0&&book.page==0&&!book.favorite?JSONObject.NULL:book.page)
                .put("favorite",book.favorite).put("client_updated_at",book.syncUpdated);
            JSONArray aliases=new JSONArray();if(!raw.isEmpty()&&!raw.equals(key))aliases.put(raw);
            if(book.legacyItemKey.equals(raw)&&!raw.isEmpty()&&book.id.matches("uri-[0-9a-f]{64}"))aliases.put(book.id);
            if(aliases.length()>0)row.put("legacy_keys",aliases);
            payload.put(row);
        }
        if(changed)write(current);return payload;
        }
    }
    synchronized boolean applySyncResponse(JSONArray remote)throws JSONException {
        List<Book> list=all();Map<String,List<Book>> index=new HashMap<>();
        for(Book book:list){index.computeIfAbsent(book.itemKey,k->new ArrayList<>()).add(book);if(!book.id.equals(book.itemKey)&&book.legacyItemKey.equals(book.itemKey))index.computeIfAbsent(book.id,k->new ArrayList<>()).add(book);}
        boolean changed=false;
        for(int i=0;i<remote.length();i++){
            JSONObject row=remote.getJSONObject(i);List<Book> matches=index.get(row.getString("item_key"));if(matches==null)continue;
            double stamp=row.optDouble("client_updated_at",0);
            for(Book book:matches){if(stamp<book.syncUpdated)continue;
                int page=row.isNull("page")?book.page:Math.max(0,row.optInt("page"));
                if(book.count>0)page=Math.min(book.count-1,page);
                boolean favorite=row.optBoolean("favorite");
                if(book.page==page&&book.favorite==favorite&&book.syncUpdated==stamp)continue;
                book.page=page;book.favorite=favorite;book.syncUpdated=stamp;book.updated=Math.max(book.updated,stamp);changed=true;
            }
        }
        if(changed)write(list);return changed;
    }
    synchronized void setCollection(Set<String> ids,String collection){List<Book> list=all();for(Book b:list)if(ids.contains(b.id))b.collection=collection;write(list);}
    synchronized void renameCollection(String oldName,String newName){List<Book> list=all();for(Book b:list)if(oldName.equals(b.collection))b.collection=newName;write(list);}
    String collectionAlias(String key,String fallback){return prefs.getString("alias:"+key,fallback);}
    void setCollectionAlias(String key,String name){prefs.edit().putString("alias:"+key,name).apply();}
    private void write(List<Book> list){JSONArray a=new JSONArray();try{for(Book b:list)a.put(b.json());}catch(JSONException e){throw new IllegalStateException(e);}if(!prefs.edit().putString("items",a.toString()).commit())throw new IllegalStateException("Não foi possível salvar a biblioteca.");}
    synchronized void remove(Book b){List<Book> list=all();list.removeIf(x->x.id.equals(b.id));Set<String> ignored=new HashSet<>(prefs.getStringSet("excluded",Collections.emptySet()));ignored.add(b.fingerprint.isEmpty()?b.id:b.fingerprint);if(!b.uri.isEmpty())ignored.add("uri:"+b.uri);prefs.edit().putStringSet("excluded",ignored).commit();write(list);if(b.uri.isEmpty())new File(books,b.file).delete();else release(b);cover(b).delete();}
    File file(Book b)throws IOException {
        if(!b.available)throw new IOException("HQ indisponível. Atualize a pasta. Seu progresso foi mantido.");
        if(b.uri.isEmpty())return new File(books,b.file);
        File cache=new File(context.getCacheDir(),"linked-"+b.file);
        if(cache.isFile())return cache;
        File temp=File.createTempFile("linked-",".part",context.getCacheDir());
        try(InputStream in=context.getContentResolver().openInputStream(Uri.parse(b.uri));OutputStream out=new FileOutputStream(temp)){
            if(in==null)throw new IOException("Arquivo indisponível. Confira o acesso à pasta.");
            byte[] bytes=new byte[65536];int n;long total=0;
            while((n=in.read(bytes))!=-1){BookSource.checkCancelled();total+=n;if(total>768L*1024*1024)throw new IOException("Arquivo maior que 768 MB.");out.write(bytes,0,n);}
            if(!temp.renameTo(cache))throw new IOException("Sem espaço para abrir a HQ.");
            return cache;
        }catch(SecurityException e){throw new IOException("Permissão da pasta perdida. Selecione a pasta novamente.",e);}
        finally{temp.delete();}
    }
    void release(Book b){if(!b.uri.isEmpty())new File(context.getCacheDir(),"linked-"+b.file).delete();}
    void prepareCover(Book b)throws Exception {
        BookSource.checkCancelled();
        if(cover(b).isFile())return;
        File archive=b.uri.isEmpty()?new File(books,b.file):File.createTempFile("cover-source-",b.file.substring(b.file.lastIndexOf('.')),context.getCacheDir());
        try{
            if(!b.uri.isEmpty())try(InputStream in=context.getContentResolver().openInputStream(Uri.parse(b.uri));OutputStream out=new FileOutputStream(archive)){
                if(in==null)throw new IOException("Arquivo indisponível.");byte[] bytes=new byte[65536];int n;long total=0;
                while((n=in.read(bytes))!=-1){BookSource.checkCancelled();total+=n;if(total>768L*1024*1024)throw new IOException("Arquivo maior que 768 MB.");out.write(bytes,0,n);}
            }
            try(BookSource source=new BookSource(archive,context.getCacheDir())){
            int count=source.pages.size();Bitmap image=source.page(0,320);
            if(Thread.currentThread().isInterrupted()){image.recycle();BookSource.checkCancelled();}
            try(OutputStream out=new FileOutputStream(cover(b))){image.compress(Bitmap.CompressFormat.JPEG,85,out);}
            image.recycle();Book current=get(b.id);if(current!=null){current.count=count;save(current);}
            }
        }finally{if(!b.uri.isEmpty())archive.delete();}
    }
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
    synchronized int linkUris(List<Uri> uris)throws Exception {
        List<Book> list=all();Set<String> known=new HashSet<>();for(Book b:list)known.add(b.uri);
        int added=0;for(Uri uri:uris){String filename=name(uri);if(!BookSource.supported(filename)||known.contains(uri.toString()))continue;
            MessageDigest digest=MessageDigest.getInstance("SHA-256");byte[] hash=digest.digest(uri.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));StringBuilder id=new StringBuilder("uri-");for(byte byteValue:hash)id.append(String.format(Locale.ROOT,"%02x",byteValue&255));
            Book b=new Book();b.id=id.toString();b.uri=uri.toString();b.file=b.id+filename.substring(filename.lastIndexOf('.')).toLowerCase(Locale.ROOT);b.title=filename.substring(0,filename.lastIndexOf('.'));b.updated=System.currentTimeMillis()/1000.0;
            list.add(b);known.add(b.uri);added++;
        }if(added>0)write(list);return added;
    }
    Book importUri(Uri uri)throws Exception {try(InputStream in=context.getContentResolver().openInputStream(uri)){if(in==null)throw new IOException("Arquivo indisponível.");return importStream(in,name(uri));}}
    Book importStream(InputStream in,String name)throws Exception {
        if(!BookSource.supported(name))throw new IOException("Use CBZ, ZIP, PDF, CBR, RAR, 7Z, CB7, TAR, CBT ou EPUB de HQ.");
        File temp=File.createTempFile("import-",".part",books);File finalFile=null;boolean added=false;
        try{
            MessageDigest hash=MessageDigest.getInstance("SHA-256");long total=0;
            try(OutputStream out=new FileOutputStream(temp)){byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1){total+=n;if(total>768L*1024*1024)throw new IOException("Limite de importação: 768 MB por arquivo.");if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();hash.update(buffer,0,n);out.write(buffer,0,n);}}
            StringBuilder hex=new StringBuilder();for(byte b:hash.digest())hex.append(String.format(Locale.ROOT,"%02x",b&255));String id=hex.toString();
            Book existing=get(id);if(existing==null)for(Book candidate:all())if(id.equals(candidate.fingerprint)||id.equals(candidate.itemKey)){existing=candidate;break;}if(existing!=null){temp.delete();existing.duplicateImport=true;return existing;}
            String extension=name.substring(name.lastIndexOf('.')).toLowerCase(Locale.ROOT);finalFile=new File(books,id+extension);
            if(!temp.renameTo(finalFile))throw new IOException("Não foi possível salvar o arquivo.");
            Book b=new Book();b.id=id;b.file=finalFile.getName();b.title=name.substring(0,name.lastIndexOf('.'));b.updated=System.currentTimeMillis()/1000.0;
            try(BookSource source=new BookSource(finalFile,context.getCacheDir())){b.count=source.pages.size();Bitmap image=source.page(0,320);try(OutputStream out=new FileOutputStream(cover(b))){image.compress(Bitmap.CompressFormat.JPEG,85,out);}image.recycle();}
            save(b);added=true;return b;
        }finally{temp.delete();if(!added&&finalFile!=null)finalFile.delete();}
    }
    synchronized void exportBackup(OutputStream out)throws Exception {JSONArray a=new JSONArray();for(Book b:all())a.put(b.json());JSONObject root=new JSONObject().put("format","komicove-android").put("version",1).put("items",a);out.write(root.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8));}

    synchronized int reconcileFolders(List<JSONObject> entries,Set<String> scanned,Set<String> unavailable)throws Exception {
        List<Book> list=all();Map<String,Book> hashes=new HashMap<>(),uris=new HashMap<>();
        Set<String> excluded=prefs.getStringSet("excluded",Collections.emptySet());
        for(Book b:list){hashes.put(!b.itemKey.isEmpty()?b.itemKey:b.fingerprint.isEmpty()?b.id:b.fingerprint,b);uris.put(b.uri,b);for(int i=0;i<b.sources.length();i++)uris.put(b.sources.getJSONObject(i).optString("uri"),b);}
        int added=0;Set<String> touched=new HashSet<>();Map<Book,JSONArray> retained=new HashMap<>();Map<Book,String> sourceNames=new HashMap<>();
        for(Book b:list)for(int i=0;i<b.sources.length();i++){JSONObject source=b.sources.getJSONObject(i);if(b.uri.equals(source.optString("uri")))sourceNames.put(b,source.optString("name").replaceFirst("\\.[^.]+$",""));}
        for(Book b:list){JSONArray keep=new JSONArray();for(int i=0;i<b.sources.length();i++){JSONObject s=new JSONObject(b.sources.getJSONObject(i).toString());if(scanned.contains(s.optString("folder")))s.put("available",false);keep.put(s);}retained.put(b,keep);if(b.sources.length()>0)touched.add(b.id);}
        for(JSONObject entry:entries){String hash=entry.getString("hash"),uri=entry.getString("uri"),name=entry.getString("name");Book b=hashes.get(hash);if(b==null){b=uris.get(uri);if(b!=null&&!b.fingerprint.isEmpty()&&!b.fingerprint.equals(hash))b=null;}
            if(excluded.contains(hash)||excluded.contains("uri:"+uri))continue;
            if(b==null){b=new Book();b.id=hash;b.file=hash+name.substring(name.lastIndexOf('.')).toLowerCase(Locale.ROOT);b.title=name.substring(0,name.lastIndexOf('.'));b.updated=System.currentTimeMillis()/1000.0;list.add(b);retained.put(b,new JSONArray());added++;}
            b.fingerprint=hash;b.itemKey=hash;hashes.put(hash,b);uris.put(uri,b);JSONArray locations=retained.get(b);for(int i=locations.length()-1;i>=0;i--){JSONObject old=locations.getJSONObject(i);if(uri.equals(old.optString("uri"))&&entry.optString("folder").equals(old.optString("folder")))locations.remove(i);}locations.put(entry);touched.add(b.id);
        }
        for(Book b:list){if(!touched.contains(b.id))continue;JSONArray locations=retained.get(b);boolean wasMonitored=b.sources.length()>0;b.sources=locations;JSONObject chosen=null;
            for(int i=0;i<locations.length();i++){JSONObject s=locations.getJSONObject(i);if(!s.optBoolean("available",true)||unavailable.contains(s.optString("folder")))continue;if(chosen==null||b.uri.equals(s.optString("uri")))chosen=s;}
            if(b.uri.isEmpty()&&new File(books,b.file).isFile()){b.available=true;continue;}
            if(chosen!=null){String next=chosen.getString("uri"),name=chosen.getString("name").replaceFirst("\\.[^.]+$","");if(!next.equals(b.uri)||!b.available||b.title.equals(sourceNames.get(b)))b.title=name;b.uri=next;b.available=true;}
            else if(wasMonitored||locations.length()>0)b.available=false;
        }
        write(list);return added;
    }
    synchronized int restoreBackup(InputStream in)throws Exception {
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buf=new byte[4096];int n;while((n=in.read(buf))!=-1){if(out.size()+n>5*1024*1024)throw new IOException("Backup grande demais.");out.write(buf,0,n);}
        JSONObject root=new JSONObject(out.toString("UTF-8"));String format=root.optString("format");if((!format.equals("komicove-android")&&!format.equals("panel-android"))||root.optInt("version")!=1)throw new IOException("Use um backup Android compatível com o Komicove.");
        JSONArray a=root.getJSONArray("items");List<Book> list=all();int restored=0;
        for(Book local:list)for(int i=0;i<a.length();i++){JSONObject j=a.getJSONObject(i);if(local.id.equals(j.optString("id"))){local.page=Math.max(0,Math.min(local.count-1,j.optInt("page")));local.favorite=j.optBoolean("favorite");local.collection=j.optString("collection");local.marks=j.optJSONArray("marks");if(local.marks==null)local.marks=new JSONArray();local.updated=System.currentTimeMillis()/1000.0;local.syncUpdated=Math.max(local.updated,local.syncUpdated+.000001);restored++;break;}}
        write(list);return restored;
    }
}

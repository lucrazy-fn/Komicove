package com.lucrazy.komicove;

import android.database.*;
import android.os.*;
import android.provider.DocumentsContract;
import android.provider.DocumentsProvider;
import java.io.*;
import android.graphics.*;
import android.content.ContentValues;
import java.util.zip.*;

/** Test APK only. Exposes only synthetic fixtures in this test app's files. */
public final class FolderFixtureProvider extends DocumentsProvider {
    static final String AUTHORITY="com.lucrazy.komicove.phase2fixtures.v2";
    public boolean onCreate(){return true;}
    @Override public Bundle call(String method,String arg,Bundle extras){Bundle result=new Bundle();try{File root=file("root");if(method.equals("seed")){if(root.exists())throw new IOException("Fixtures already exist");if(!root.mkdir())throw new IOException("Fixture mkdir");File first=new File(root,"Quadrinhos de teste"),second=new File(root,"Leituras pendentes"),third=new File(root,"Independentes");if(!first.mkdir()||!second.mkdir()||!third.mkdir())throw new IOException("Folder mkdir");for(int i=0;i<300;i++)comic(new File(first,String.format(java.util.Locale.ROOT,"Teste %03d.cbz",i)),Color.RED,"first-"+i);comic(new File(second,"Outra HQ.cbz"),Color.BLUE,"second");comic(new File(third,"Nova HQ.cbz"),Color.GREEN,"third");}
        else if(method.equals("move_first")){if(!file("root/Quadrinhos de teste/Teste 000.cbz").renameTo(file("root/Leituras pendentes/Renomeada.cbz")))throw new IOException("Move");}
        else if(method.equals("delete_first")){if(!file("root/Leituras pendentes/Renomeada.cbz").delete())throw new IOException("Delete fixture");}
        else if(method.equals("add_new"))comic(file("root/Leituras pendentes/Adicionada agora.cbz"),Color.YELLOW,"new");
        else if(method.equals("add_automatic"))comic(file("root/Independentes/Detectada automaticamente.cbz"),Color.CYAN,"automatic");
        else if(method.equals("cleanup")){File[] dirs=root.listFiles();if(dirs!=null)for(File dir:dirs){File[] files=dir.listFiles();if(files!=null)for(File child:files)child.delete();dir.delete();}root.delete();}
        else throw new IOException("Unknown fixture operation");result.putBoolean("ok",true);
        }catch(Exception e){result.putString("error",e.getMessage());}return result;}
    private void comic(File file,int color,String marker)throws Exception{Bitmap bitmap=Bitmap.createBitmap(40,60,Bitmap.Config.ARGB_8888);bitmap.eraseColor(color);ByteArrayOutputStream png=new ByteArrayOutputStream();bitmap.compress(Bitmap.CompressFormat.PNG,100,png);bitmap.recycle();try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(file))){for(String name:new String[]{"001.jpg","002.jpg"}){zip.putNextEntry(new ZipEntry(name));zip.write(png.toByteArray());zip.closeEntry();}zip.putNextEntry(new ZipEntry("marker.txt"));zip.write(marker.getBytes(java.nio.charset.StandardCharsets.UTF_8));zip.closeEntry();}}
    File file(String id)throws FileNotFoundException{
        try{File base=new File(getContext().getFilesDir(),"phase2-fixtures").getCanonicalFile();File result=id.equals("root")?base:new File(base,id.substring(5)).getCanonicalFile();if(!result.equals(base)&&!result.toPath().startsWith(base.toPath()))throw new IOException("Outside fixture directory");return result;}catch(Exception e){throw new FileNotFoundException("Invalid fixture ID");}
    }
    public Cursor queryRoots(String[] projection){String[] columns=projection==null?new String[]{"root_id","document_id","title","flags"}:projection;MatrixCursor rows=new MatrixCursor(columns);Object[] row=new Object[columns.length];for(int i=0;i<columns.length;i++){switch(columns[i]){case "root_id":case "document_id":row[i]="root";break;case "title":row[i]="Komicove Phase 2 tests";break;case "flags":row[i]=DocumentsContract.Root.FLAG_SUPPORTS_IS_CHILD;break;}}rows.addRow(row);return rows;}
    public Cursor queryDocument(String id,String[] projection)throws FileNotFoundException{MatrixCursor result=cursor(projection);File file=file(id);if(file.exists())add(result,id,file);return result;}
    public Cursor queryChildDocuments(String id,String[] projection,String order)throws FileNotFoundException{File[] children=file(id).listFiles();if(children==null)throw new FileNotFoundException("Fixture folder missing");MatrixCursor result=cursor(projection);for(File child:children)add(result,id+"/"+child.getName(),child);return result;}
    private MatrixCursor cursor(String[] projection){return new MatrixCursor(projection==null?new String[]{"document_id","_display_name","mime_type","_size","last_modified","flags"}:projection);}
    private void add(MatrixCursor rows,String id,File file){String[] columns=rows.getColumnNames();Object[] values=new Object[columns.length];for(int i=0;i<columns.length;i++){switch(columns[i]){case "document_id":values[i]=id;break;case "_display_name":values[i]=file.getName();break;case "mime_type":values[i]=file.isDirectory()?DocumentsContract.Document.MIME_TYPE_DIR:"application/zip";break;case "_size":values[i]=file.length();break;case "last_modified":values[i]=file.lastModified();break;case "flags":values[i]=0;break;}}rows.addRow(values);}
    public ParcelFileDescriptor openDocument(String id,String mode,CancellationSignal signal)throws FileNotFoundException{if(!mode.equals("r"))throw new FileNotFoundException("Read only fixtures");return ParcelFileDescriptor.open(file(id),ParcelFileDescriptor.MODE_READ_ONLY);}
    public boolean isChildDocument(String parent,String child){try{return file(child).toPath().startsWith(file(parent).toPath());}catch(FileNotFoundException e){return false;}}
}

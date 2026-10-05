package com.lucrazy.komicove;

import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.*;
import android.provider.*;
import java.io.*;

/** Only installed in the disposable instrumentation APK. */
public final class LibraryPhase5FixtureProvider extends ContentProvider {
    private File file;private int opens;
    @Override public boolean onCreate(){file=new File(getContext().getCacheDir(),"phase5-fixture.cbz");return true;}
    @Override public Bundle call(String method,String arg,Bundle extras){
        Bundle result=new Bundle();
        if("fixture".equals(method)){
            try(FileOutputStream out=new FileOutputStream(file)){out.write(extras.getByteArray("bytes"));}
            catch(IOException error){throw new IllegalStateException(error);}
            opens=0;
        }
        result.putInt("opens",opens);return result;
    }
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] args,String sort){
        MatrixCursor cursor=new MatrixCursor(projection);Object[] row=new Object[projection.length];
        for(int i=0;i<projection.length;i++)row[i]=OpenableColumns.DISPLAY_NAME.equals(projection[i])?"Phase5.cbz":OpenableColumns.SIZE.equals(projection[i])?file.length():DocumentsContract.Document.COLUMN_LAST_MODIFIED.equals(projection[i])?file.lastModified():0;
        cursor.addRow(row);return cursor;
    }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException {
        if(!"r".equals(mode))throw new FileNotFoundException("Read-only fixture");opens++;
        return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);
    }
    @Override public String getType(Uri uri){return "application/vnd.comicbook+zip";}
    @Override public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
    @Override public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
    @Override public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
}

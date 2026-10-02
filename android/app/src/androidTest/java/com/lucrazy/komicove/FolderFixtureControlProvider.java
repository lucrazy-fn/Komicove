package com.lucrazy.komicove;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.provider.DocumentsContract;

/** Test APK only: fixture administration runs as the fixture owner, never as the real app. */
public final class FolderFixtureControlProvider extends ContentProvider {
    public boolean onCreate() { return true; }
    public Bundle call(String method, String arg, Bundle extras) {
        String target = getContext().getPackageName().replaceFirst("\\.test$", "");
        if (!target.endsWith(".phase2test")) throw new SecurityException("Isolated fixture app required");
        long identity = Binder.clearCallingIdentity();
        try {
            if ("grant".equals(method)) {
                for (String name : new String[]{"Quadrinhos de teste", "Leituras pendentes", "Independentes"}) {
                    Uri tree = DocumentsContract.buildTreeDocumentUri(FolderFixtureProvider.AUTHORITY, "root/" + name);
                    getContext().grantUriPermission(target, tree, Intent.FLAG_GRANT_READ_URI_PERMISSION
                        | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
                }
                Bundle result = new Bundle(); result.putBoolean("ok", true); return result;
            }
            if (!java.util.Arrays.asList("seed", "move_first", "delete_first", "add_new", "add_automatic", "cleanup").contains(method))
                throw new IllegalArgumentException("Unknown fixture operation");
            return getContext().getContentResolver().call(Uri.parse("content://" + FolderFixtureProvider.AUTHORITY), method, null, null);
        } finally { Binder.restoreCallingIdentity(identity); }
    }
    public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) { return null; }
    public String getType(Uri uri) { return null; }
    public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException(); }
    public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException(); }
}

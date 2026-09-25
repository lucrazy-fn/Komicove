package com.lucrazy.komicove;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.assertEquals;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=28)
public class KomicoveBackupTest {
    @Test public void newBackupNameKeepsOldBackupsReadable() throws Exception {
        LibraryStore store = new LibraryStore(RuntimeEnvironment.getApplication());
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        store.exportBackup(output);
        JSONObject fresh = new JSONObject(output.toString("UTF-8"));
        assertEquals("komicove-android", fresh.getString("format"));
        fresh.put("format", "panel-android");
        fresh.put("items", new org.json.JSONArray());
        assertEquals(0, store.restoreBackup(new ByteArrayInputStream(
                fresh.toString().getBytes(StandardCharsets.UTF_8))));
    }
}

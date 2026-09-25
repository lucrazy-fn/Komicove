package com.lucrazy.komicove;

import android.net.Uri;
import java.io.File;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.HashSet;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=28)
public class LibraryStoreLinkTest {
    private LibraryStore store;

    @Before public void setup() {
        store = new LibraryStore(RuntimeEnvironment.getApplication());
        for (LibraryStore.Book book : store.all()) store.remove(book);
    }

    @Test public void linkedComicIsNotPermanentlyCopied() throws Exception {
        File original = File.createTempFile("komicove-link-", ".cbz");
        try {
            Files.write(original.toPath(), new byte[]{1, 2, 3});
            Uri uri = Uri.fromFile(original);
            assertEquals(1, store.linkUris(Arrays.asList(uri)));
            assertEquals(0, store.linkUris(Arrays.asList(uri)));
            LibraryStore.Book book = store.all().get(0);
            assertEquals(uri.toString(), book.uri);
            assertFalse(new File(store.books, book.file).exists());
            assertTrue(original.exists());
            store.remove(book);
            assertTrue(original.exists());
        } finally {
            original.delete();
        }
    }

    @Test public void selectedComicsJoinOneCollection() throws Exception {
        File first = File.createTempFile("komicove-first-", ".cbz");
        File second = File.createTempFile("komicove-second-", ".cbz");
        try {
            assertEquals(2, store.linkUris(Arrays.asList(Uri.fromFile(first), Uri.fromFile(second))));
            HashSet<String> ids = new HashSet<>();
            for (LibraryStore.Book book : store.all()) ids.add(book.id);
            store.setCollection(ids, "Favoritas");
            for (LibraryStore.Book book : new LibraryStore(RuntimeEnvironment.getApplication()).all())
                assertEquals("Favoritas", book.collection);
        } finally {
            first.delete();
            second.delete();
        }
    }

    @Test public void renamingManualCollectionUpdatesEveryBook() throws Exception {
        File first = File.createTempFile("komicove-rename-first-", ".cbz");
        File second = File.createTempFile("komicove-rename-second-", ".cbz");
        try {
            store.linkUris(Arrays.asList(Uri.fromFile(first), Uri.fromFile(second)));
            HashSet<String> ids = new HashSet<>();
            for (LibraryStore.Book book : store.all()) ids.add(book.id);
            store.setCollection(ids, "Antiga");
            store.renameCollection("Antiga", "Nova");
            for (LibraryStore.Book book : new LibraryStore(RuntimeEnvironment.getApplication()).all())
                assertEquals("Nova", book.collection);
            assertEquals(1, CollectionGroups.build(store.all(),store).stream().filter(g->g.kind.equals("manual")).count());
        } finally {
            first.delete();
            second.delete();
        }
    }
}

package com.lucrazy.panel;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import java.util.Arrays;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=28)
public class ReadingOrderTest {
    @Test public void metadataSurvivesSerialization()throws Exception {
        LibraryStore.Book original=book("1","Serie","2.5");original.author="Autor";original.title="Titulo";
        LibraryStore.Book restored=LibraryStore.Book.parse(original.json());
        assertEquals("Serie",restored.series);assertEquals("Autor",restored.author);assertEquals("2.5",restored.issue);
    }
    private LibraryStore.Book book(String id,String series,String issue){
        LibraryStore.Book b=new LibraryStore.Book();b.id=id;b.series=series;b.issue=issue;return b;
    }
    @Test public void choosesNumericSuccessor(){
        LibraryStore.Book first=book("1","Serie","1"),second=book("2","serie","2"),tenth=book("10","Serie","10");
        assertSame(second,ReadingOrder.next(first,Arrays.asList(tenth,first,second)));
    }
    @Test public void rejectsAmbiguousOrMissingMetadata(){
        LibraryStore.Book first=book("1","Serie","1");
        assertNull(ReadingOrder.next(first,Arrays.asList(book("2","Serie","2"),book("3","Serie","2"))));
        assertNull(ReadingOrder.next(book("0","","1"),Arrays.asList(book("2","","2"))));
        assertNull(ReadingOrder.next(first,Arrays.asList(book("2","Outra","2"))));
    }
}

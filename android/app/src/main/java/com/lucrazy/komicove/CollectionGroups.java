package com.lucrazy.komicove;

import android.net.Uri;
import android.provider.DocumentsContract;
import java.util.*;

final class CollectionGroups {
    static final class Group {
        final String kind, source, key;
        String name;
        final List<LibraryStore.Book> books=new ArrayList<>();
        Group(String kind,String source,LibraryStore store){
            this.kind=kind;this.source=source;this.key=kind+":"+source;
            this.name=kind.equals("manual")?source:store.collectionAlias(key,source);
        }
        int read(){int count=0;for(LibraryStore.Book b:books)if(b.completed||b.count>0&&b.page>=b.count-1)count++;return count;}
        double latest(){double date=0;for(LibraryStore.Book b:books)date=Math.max(date,b.updated);return date;}
        boolean contains(LibraryStore.Book book){for(LibraryStore.Book b:books)if(b.id.equals(book.id))return true;return false;}
    }

    static List<Group> build(List<LibraryStore.Book> books,LibraryStore store){
        Map<String,Group> groups=new LinkedHashMap<>();
        for(LibraryStore.Book book:books){
            String folder=folderName(book);
            if(!folder.isEmpty())add(groups,"folder",folder,book,store);
            String series=book.series.trim();
            if(series.isEmpty())series=inferSeries(book.title);
            if(!series.isEmpty())add(groups,"series",series,book,store);
            if(!book.collection.trim().isEmpty())add(groups,"manual",book.collection.trim(),book,store);
        }
        List<Group> result=new ArrayList<>();
        for(Group group:groups.values())if(!group.kind.equals("series")||group.books.size()>=2)result.add(group);
        return result;
    }

    private static void add(Map<String,Group> groups,String kind,String source,LibraryStore.Book book,LibraryStore store){
        String key=kind+":"+source;
        Group group=groups.get(key);
        if(group==null){group=new Group(kind,source,store);groups.put(key,group);}
        group.books.add(book);
    }

    static String folderName(LibraryStore.Book book){
        if(book.uri.isEmpty())return "";
        try{
            Uri uri=Uri.parse(book.uri);
            String id=DocumentsContract.getDocumentId(uri);
            int slash=id.lastIndexOf('/');
            if(slash<1)return "";
            String parent=id.substring(0,slash);
            int parentSlash=parent.lastIndexOf('/');
            String name=parent.substring(parentSlash+1).trim();
            return name.contains(":")?"":name;
        }catch(Exception ignored){return "";}
    }

    static String inferSeries(String title){
        String value=title.replaceFirst("(?i)\\s*\\(?20\\d{2}\\)?.*$", "")
            .replaceFirst("(?i)\\s*(?:#|n[ºo.]?|vol\\.?|edição)\\s*\\d+.*$", "")
            .replaceFirst("\\s+\\d{3,4}$", "").trim();
        return value.equals(title.trim())?"":value;
    }
}

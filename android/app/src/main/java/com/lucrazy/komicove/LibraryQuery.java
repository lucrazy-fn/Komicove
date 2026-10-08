package com.lucrazy.komicove;

import java.util.*;

/** Search/sort caches are restricted to one immutable library snapshot. */
final class LibraryQuery {
    final List<LibraryStore.Book> books;
    private final Map<String,String> text=new HashMap<>();
    private final Map<String,List<LibraryStore.Book>> orders=new HashMap<>();
    private final LinkedHashMap<List<Object>,List<LibraryStore.Book>> results=new LinkedHashMap<>(8,.75f,true);
    LibraryQuery(List<LibraryStore.Book> snapshot){
        books=Collections.unmodifiableList(new ArrayList<>(snapshot));
        for(LibraryStore.Book b:books)text.put(b.id,(b.title+" "+b.series+" "+b.author).toLowerCase(Locale.ROOT));
    }
    synchronized List<LibraryStore.Book> select(String query,String mode,String status,boolean favorite,String series,String author,Set<String> collection){
        query=query.toLowerCase(Locale.ROOT);
        List<Object> key=Arrays.asList(query,mode,status,favorite,series,author,collection);
        List<LibraryStore.Book> hit=results.get(key);if(hit!=null)return hit;
        List<LibraryStore.Book> ordered=orders.get(mode);
        if(ordered==null){
            ordered=new ArrayList<>(books);NaturalOrder natural=new NaturalOrder();
            if(mode.equals("title"))ordered.sort((a,b)->natural.compare(a.title,b.title));
            else if(mode.equals("title_desc"))ordered.sort((a,b)->natural.compare(b.title,a.title));
            else if(mode.equals("series"))ordered.sort((a,b)->{int n=natural.compare(a.series,b.series);return n!=0?n:natural.compare(a.title,b.title);});
            orders.put(mode,ordered);
        }
        List<LibraryStore.Book> candidates=ordered;
        for(Map.Entry<List<Object>,List<LibraryStore.Book>> previous:results.entrySet()){
            List<Object> old=previous.getKey();
            if(old.subList(1,old.size()).equals(key.subList(1,key.size()))&&query.startsWith((String)old.get(0)))candidates=previous.getValue();
        }
        List<LibraryStore.Book> matched=new ArrayList<>();
        for(LibraryStore.Book b:candidates){
            if(Thread.currentThread().isInterrupted())return Collections.emptyList();
            if(favorite&&!b.favorite||collection!=null&&!collection.contains(b.id)||!text.get(b.id).contains(query)
                ||!series.isEmpty()&&!b.series.equalsIgnoreCase(series)||!author.isEmpty()&&!b.author.equalsIgnoreCase(author))continue;
            boolean done=b.count>0&&b.page>=b.count-1;
            if(status.equals("Todos")||status.equals("Concluídas")&&done||status.equals("Não lidas")&&b.page==0&&!done||status.equals("Em andamento")&&b.page>0&&!done)matched.add(b);
        }
        List<LibraryStore.Book> value=Collections.unmodifiableList(matched);results.put(key,value);
        while(results.size()>8)results.remove(results.keySet().iterator().next());
        return value;
    }
}

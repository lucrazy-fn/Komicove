package com.lucrazy.panel;

import java.math.BigDecimal;
import java.util.List;

final class ReadingOrder {
    static LibraryStore.Book next(LibraryStore.Book current,List<LibraryStore.Book> books){
        if(current.series.trim().isEmpty())return null;
        BigDecimal number;
        try{number=new BigDecimal(current.issue.trim());}catch(NumberFormatException e){return null;}
        LibraryStore.Book result=null;BigDecimal best=null;boolean ambiguous=false;
        for(LibraryStore.Book book:books){
            if(book.id.equals(current.id)||!book.series.trim().equalsIgnoreCase(current.series.trim()))continue;
            BigDecimal candidate;
            try{candidate=new BigDecimal(book.issue.trim());}catch(NumberFormatException e){continue;}
            if(candidate.compareTo(number)<=0)continue;
            if(best==null||candidate.compareTo(best)<0){best=candidate;result=book;ambiguous=false;}
            else if(candidate.compareTo(best)==0)ambiguous=true;
        }
        return ambiguous?null:result;
    }
}

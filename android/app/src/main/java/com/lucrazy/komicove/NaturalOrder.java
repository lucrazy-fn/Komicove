package com.lucrazy.komicove;

import java.util.Comparator;

final class NaturalOrder implements Comparator<String> {
    @Override public int compare(String a,String b) {
        int i=0,j=0;
        while(i<a.length()&&j<b.length()) {
            char x=Character.toLowerCase(a.charAt(i)),y=Character.toLowerCase(b.charAt(j));
            if(Character.isDigit(x)&&Character.isDigit(y)) {
                int ai=i,bj=j; while(i<a.length()&&Character.isDigit(a.charAt(i)))i++; while(j<b.length()&&Character.isDigit(b.charAt(j)))j++;
                while(ai<i-1&&a.charAt(ai)=='0')ai++;while(bj<j-1&&b.charAt(bj)=='0')bj++;
                String an=a.substring(ai,i),bn=b.substring(bj,j);
                int cmp=Integer.compare(an.length(),bn.length()); if(cmp==0)cmp=an.compareTo(bn); if(cmp!=0)return cmp;
            } else {if(x!=y)return Character.compare(x,y); i++;j++;}
        }
        return Integer.compare(a.length(),b.length());
    }
}

package com.lucrazy.panel;

import android.graphics.*;
import java.util.*;

final class PanelDetector {
    static List<RectF> readingRegions(int width,int height,boolean manga) {
        List<RectF> regions=new ArrayList<>();
        int columns=width>height?4:2;
        int rows=3;
        float overlap=.06f;
        // Traverse each half of a scanned spread separately.
        int halves=width>height?2:1;
        for(int half=0;half<halves;half++) {
            int physicalHalf=manga?halves-1-half:half;
            for(int y=0;y<rows;y++)for(int x=0;x<2;x++) {
                int col=physicalHalf*2+(manga?1-x:x);
                regions.add(new RectF(Math.max(0,col/(float)columns-overlap),Math.max(0,y/(float)rows-overlap),Math.min(1,(col+1f)/columns+overlap),Math.min(1,(y+1f)/rows+overlap)));
            }
        }
        return regions;
    }
    static List<RectF> detect(Bitmap source,boolean manga) {
        int w=Math.min(320,source.getWidth()),h=Math.max(1,source.getHeight()*w/source.getWidth());
        Bitmap small=Bitmap.createScaledBitmap(source,w,h,false);
        List<RectF> result=new ArrayList<>();
        split(small,0,0,w,h,0,manga,result);
        if(small!=source)small.recycle();
        return result;
    }
    private static void split(Bitmap b,int l,int t,int r,int bottom,int depth,boolean manga,List<RectF> out) {
        if(depth<5)for(int axis=0;axis<2;axis++) {
            int start=axis==0?t:l,end=axis==0?bottom:r,span=end-start;
            int run=0,best=0,cut=0;
            for(int p=start+span/6;p<end-span/6;p++) {
                int white=0,total=axis==0?r-l:bottom-t;
                for(int q=axis==0?l:t;q<(axis==0?r:bottom);q++) {
                    int color=b.getPixel(axis==0?q:p,axis==0?p:q);
                    if(Color.red(color)>235&&Color.green(color)>235&&Color.blue(color)>235)white++;
                }
                if(white>=total*.98){run++;if(run>best){best=run;cut=p-run/2;}}else run=0;
            }
            if(best>=Math.max(3,span/100)&&best<span/4) {
                if(axis==0){split(b,l,t,r,cut,depth+1,manga,out);split(b,l,cut,r,bottom,depth+1,manga,out);}
                else if(manga){split(b,cut,t,r,bottom,depth+1,manga,out);split(b,l,t,cut,bottom,depth+1,manga,out);}
                else {split(b,l,t,cut,bottom,depth+1,manga,out);split(b,cut,t,r,bottom,depth+1,manga,out);}
                return;
            }
        }
        out.add(new RectF(l/(float)b.getWidth(),t/(float)b.getHeight(),r/(float)b.getWidth(),bottom/(float)b.getHeight()));
    }
}

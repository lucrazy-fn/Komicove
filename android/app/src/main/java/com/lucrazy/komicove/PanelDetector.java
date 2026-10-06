package com.lucrazy.komicove;

import android.graphics.*;
import java.util.*;
import java.util.concurrent.CancellationException;

/** Bounded metadata detection; never retains the supplied bitmap. */
final class PanelDetector {
    static final int VERSION=3,MAX_PANELS=64;
    static final class Result {
        private final List<RectF> boxes;
        final boolean fallback;
        final float confidence;
        final String method;
        Result(List<RectF> regions,boolean fallback,float confidence,String method){
            boxes=copy(regions);this.fallback=fallback;this.confidence=confidence;this.method=method;
        }
        List<RectF> regions(){return copy(boxes);}
    }
    static final class Cache {
        private final int capacity;
        private final AiPanelDetector ai;
        private final LinkedHashMap<String,Result> entries=new LinkedHashMap<>(16,.75f,true);
        Cache(int capacity){this(capacity,null);}
        Cache(int capacity,AiPanelDetector ai){this.capacity=Math.max(1,capacity);this.ai=ai;}
        Result detect(String pageKey,Bitmap bitmap,boolean manga,boolean force){
            String key=VERSION+":"+pageKey+":"+manga;
            synchronized(this){Result found=entries.get(key);if(!force&&found!=null)return found;}
            Result result=analyze(bitmap,manga);checkCancelled();
            if(ai!=null)result=ai.detect(bitmap,result,manga);checkCancelled();
            synchronized(this){entries.put(key,result);while(entries.size()>capacity)entries.remove(entries.keySet().iterator().next());}
            return result;
        }
        synchronized void clear(){entries.clear();}
        synchronized int size(){return entries.size();}
        void close(){clear();if(ai!=null)ai.close();}
    }
    private static List<RectF> copy(List<RectF> source){List<RectF> result=new ArrayList<>();for(RectF r:source)result.add(new RectF(r));return result;}
    private static void checkCancelled(){if(Thread.currentThread().isInterrupted())throw new CancellationException();}
    static List<RectF> readingRegions(int width,int height,boolean manga){
        List<RectF> regions=new ArrayList<>();int columns=width>height?4:2,halves=columns/2;
        for(int half=0;half<halves;half++)for(int y=0;y<3;y++)for(int x=0;x<2;x++){
            int col=(manga?halves-1-half:half)*2+(manga?1-x:x);
            regions.add(new RectF(Math.max(0,col/(float)columns-.06f),Math.max(0,y/3f-.06f),Math.min(1,(col+1f)/columns+.06f),Math.min(1,(y+1f)/3+.06f)));
        }
        return regions;
    }
    static List<RectF> clean(List<RectF> regions){
        List<RectF> result=new ArrayList<>();
        for(RectF raw:regions){
            if(!Float.isFinite(raw.left)||!Float.isFinite(raw.top)||!Float.isFinite(raw.right)||!Float.isFinite(raw.bottom))continue;
            RectF r=new RectF(Math.max(0,Math.min(1,raw.left)),Math.max(0,Math.min(1,raw.top)),Math.max(0,Math.min(1,raw.right)),Math.max(0,Math.min(1,raw.bottom)));
            float area=r.width()*r.height();if(r.width()<.06f||r.height()<.045f||area<.012f)continue;
            boolean duplicate=false;
            for(RectF a:result){
                float intersection=Math.max(0,Math.min(r.right,a.right)-Math.max(r.left,a.left))*Math.max(0,Math.min(r.bottom,a.bottom)-Math.max(r.top,a.top));
                float union=area+a.width()*a.height()-intersection;
                float edges=Math.max(Math.max(Math.abs(r.left-a.left),Math.abs(r.top-a.top)),Math.max(Math.abs(r.right-a.right),Math.abs(r.bottom-a.bottom)));
                if(intersection/Math.max(union,1e-9f)>=.88f||edges<=.015f){duplicate=true;break;}
            }
            if(!duplicate)result.add(r);if(result.size()>=MAX_PANELS)break;
        }
        return result;
    }
    static List<RectF> order(List<RectF> regions,boolean manga,boolean spread){
        List<RectF> pending=copy(regions);
        pending.sort(Comparator.comparingDouble((RectF r)->r.top).thenComparingDouble(r->r.left));
        if(spread){
            List<RectF> left=new ArrayList<>(),right=new ArrayList<>();boolean separate=true;
            for(RectF r:pending){if(r.centerX()<.5f){left.add(r);if(r.right>.54f)separate=false;}else {right.add(r);if(r.left<.46f)separate=false;}}
            if(separate&&!left.isEmpty()&&!right.isEmpty()){
                List<RectF> result=order(manga?right:left,manga,false);result.addAll(order(manga?left:right,manga,false));return result;
            }
        }
        List<RectF> ordered=new ArrayList<>();
        while(!pending.isEmpty()){
            RectF anchor=pending.get(0);float tolerance=Math.min(.08f,anchor.height()*.25f);
            List<RectF> row=new ArrayList<>();for(RectF r:pending)if(r.top-anchor.top<=tolerance)row.add(r);
            row.sort(Comparator.comparingDouble(r->manga?-r.centerX():r.centerX()));
            ordered.addAll(row);pending.removeAll(row);
        }
        return ordered;
    }
    /** Legacy raw detector API: one whole-page rectangle still means fallback. */
    static List<RectF> detect(Bitmap source,boolean manga){
        Result result=analyze(source,manga);
        return result.fallback?Collections.singletonList(new RectF(0,0,1,1)):result.regions();
    }
    static Result analyze(Bitmap source,boolean manga){
        checkCancelled();
        float scale=Math.min(1f,Math.min(320f/source.getWidth(),480f/source.getHeight()));
        int w=Math.max(1,Math.round(source.getWidth()*scale)),h=Math.max(1,Math.round(source.getHeight()*scale));
        Bitmap small=Bitmap.createScaledBitmap(source,w,h,false);
        int[] pixels=new int[w*h];
        try{small.getPixels(pixels,0,w,0,0,w,h);}finally{if(small!=source)small.recycle();}
        boolean[] white=new boolean[w*h],black=new boolean[w*h],neutral=new boolean[w*h];
        int whiteCount=0,blackEdge=0,edge=0,low=255,high=0;
        for(int y=0;y<h;y++){checkCancelled();for(int x=0;x<w;x++){
            int i=y*w+x,c=pixels[i],min=Math.min(Color.red(c),Math.min(Color.green(c),Color.blue(c))),max=Math.max(Color.red(c),Math.max(Color.green(c),Color.blue(c)));
            white[i]=min>235;black[i]=max<20;neutral[i]=min>185&&max-min<30;if(white[i])whiteCount++;low=Math.min(low,min);high=Math.max(high,max);
            if(x==0||y==0||x==w-1||y==h-1){edge++;if(black[i])blackEdge++;}
        }}
        List<RectF> best=new ArrayList<>(),whiteComponents=Collections.emptyList();String method="gutters";float confidence=0;
        int maskCount=blackEdge>=edge*.6?2:1;
        for(int index=0;index<maskCount;index++){
            boolean[] mask=index==0?white:black;List<RectF> splits=new ArrayList<>();
            split(mask,w,h,0,0,w,h,0,splits,.98f,3);splits=clean(splits);
            Iterator<RectF> scan=splits.iterator();while(scan.hasNext()){
                RectF rect=scan.next();int x0=Math.round(rect.left*w),x1=Math.round(rect.right*w),y0=Math.round(rect.top*h),y1=Math.round(rect.bottom*h),ink=0;
                for(int y=y0;y<y1;y++){checkCancelled();for(int x=x0;x<x1;x++)if(!mask[y*w+x])ink++;}
                if(ink<w*h*.004f||ink<(x1-x0)*(y1-y0)*.06f)scan.remove();
            }
            List<RectF> components=components(mask,w,h);if(index==0)whiteComponents=components;
            boolean useComponents=components.size()>splits.size();List<RectF> candidates=useComponents?components:splits;
            float score=(useComponents?.78f:.94f)-index*.10f;
            if(candidates.size()>1&&(best.isEmpty()||score>confidence||candidates.size()>best.size()&&score>=confidence-.08f)){
                best=candidates;method=useComponents?"components":"gutters";confidence=score;
            }
        }
        boolean scanThin=confidence<.84f;
        for(boolean[] mask:scanThin?new boolean[][]{neutral,black}:new boolean[0][]){
            float score=mask==neutral?.66f:.72f,threshold=mask==neutral?.80f:.90f;
            List<RectF> candidates=new ArrayList<>();split(mask,w,h,0,0,w,h,0,candidates,threshold,1);candidates=clean(candidates);
            Iterator<RectF> scan=candidates.iterator();while(scan.hasNext()){
                RectF rect=scan.next();int x0=Math.round(rect.left*w),x1=Math.round(rect.right*w),y0=Math.round(rect.top*h),y1=Math.round(rect.bottom*h),ink=0;
                for(int y=y0;y<y1;y++){checkCancelled();for(int x=x0;x<x1;x++)if(!mask[y*w+x])ink++;}
                if(ink<w*h*.004f||ink<(x1-x0)*(y1-y0)*.06f)scan.remove();
            }
            if(candidates.size()>1&&(best.isEmpty()||candidates.size()>best.size()&&score>=confidence-.08f)){best=candidates;method="thin_borders";confidence=score;}
        }
        if(!best.isEmpty()){
            for(int i=0;i<best.size();i++)for(int j=i+1;j<best.size();j++){RectF a=best.get(i),b=best.get(j);if(Math.min(a.right,b.right)>Math.max(a.left,b.left)&&Math.min(a.bottom,b.bottom)>Math.max(a.top,b.top))confidence=Math.min(confidence,.68f);}
            return new Result(order(best,manga,w>h),false,confidence,method);
        }
        boolean whole=high-low>40&&whiteCount<white.length*.25&&whiteComponents.size()==1;
        return new Result(whole?Collections.singletonList(new RectF(0,0,1,1)):readingRegions(source.getWidth(),source.getHeight(),manga),true,whole?.30f:.15f,whole?"whole_page":"approximate");
    }
    private static void split(boolean[] mask,int w,int h,int l,int t,int r,int b,int depth,List<RectF> out,float threshold,int minimumRun){
        checkCancelled();
        if(depth<5)for(int axis=0;axis<2;axis++){
            int start=axis==0?t:l,end=axis==0?b:r,span=end-start,low=axis==0?l:t,high=axis==0?r:b,run=0,best=0,cut=0;
            for(int p=start+span/6;p<end-span/6;p++){
                checkCancelled();int count=0;
                for(int q=low;q<high;q++)if(mask[axis==0?p*w+q:q*w+p])count++;
                run=count>=(high-low)*threshold?run+1:0;if(run>best){best=run;cut=p-run/2;}
            }
            if(best>=Math.max(minimumRun,minimumRun==1?span/300:span/100)&&best<span/4f){
                if(axis==0){split(mask,w,h,l,t,r,cut,depth+1,out,threshold,minimumRun);split(mask,w,h,l,cut,r,b,depth+1,out,threshold,minimumRun);}
                else{split(mask,w,h,l,t,cut,b,depth+1,out,threshold,minimumRun);split(mask,w,h,cut,t,r,b,depth+1,out,threshold,minimumRun);}return;
            }
        }
        out.add(new RectF(l/(float)w,t/(float)h,r/(float)w,b/(float)h));
    }
    private static List<RectF> components(boolean[] mask,int w,int h){
        boolean[] seen=new boolean[mask.length];int[] queue=new int[mask.length];List<RectF> result=new ArrayList<>();int foreground=0,kept=0;
        for(boolean background:mask)if(!background)foreground++;
        for(int start=0;start<mask.length;start++){
            if((start&1023)==0)checkCancelled();if(mask[start]||seen[start])continue;
            int head=0,tail=1;queue[0]=start;seen[start]=true;int l=start%w,r=l,t=start/w,b=t,count=0;
            while(head<tail){
                if((head&1023)==0)checkCancelled();int point=queue[head++],x=point%w,y=point/w;count++;l=Math.min(l,x);r=Math.max(r,x);t=Math.min(t,y);b=Math.max(b,y);
                if(x>0&&!seen[point-1]&&!mask[point-1]){seen[point-1]=true;queue[tail++]=point-1;}
                if(x+1<w&&!seen[point+1]&&!mask[point+1]){seen[point+1]=true;queue[tail++]=point+1;}
                if(y>0&&!seen[point-w]&&!mask[point-w]){seen[point-w]=true;queue[tail++]=point-w;}
                if(y+1<h&&!seen[point+w]&&!mask[point+w]){seen[point+w]=true;queue[tail++]=point+w;}
            }
            int area=(r-l+1)*(b-t+1);
            if(count>=w*h*.012f&&area>=w*h*.02f&&count/(float)area>=.18f){
                List<RectF> valid=clean(Collections.singletonList(new RectF(l/(float)w,t/(float)h,(r+1f)/w,(b+1f)/h)));
                if(!valid.isEmpty()){result.add(valid.get(0));kept+=count;}
            }
        }
        if(result.size()>MAX_PANELS||kept<foreground*.65f)return Collections.emptyList();
        return clean(result);
    }
}

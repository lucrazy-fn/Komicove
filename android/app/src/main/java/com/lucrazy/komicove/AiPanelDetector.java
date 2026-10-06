package com.lucrazy.komicove;

import android.content.Context;
import android.graphics.*;
import android.util.Log;
import java.io.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.CancellationException;

/** Offline detector contract and shared geometry. Native runtime is shared by all build variants. */
class AiPanelDetector implements Closeable {
    static final String SHA256="f240e1296efd048126b26ea4ffeddc97d7c3aa667a37e3127c2afc6d5e9b9578";
    static final int BYTES=12256396,SIZE=640;
    AiPanelDetector(Context context){}
    static AiPanelDetector available(Context context){
        try{
            String[] files=context.getAssets().list("guided-ai");
            if(files!=null)for(String file:files)if(file.equals("inkwell.onnx"))
                return (AiPanelDetector)Class.forName("com.lucrazy.komicove.OnnxPanelDetector")
                    .getDeclaredConstructor(Context.class).newInstance(context);
        }catch(IOException|ReflectiveOperationException|LinkageError error){
            Log.w("KomicoveAI","Optional local runtime unavailable; existing detector retained");
        }
        return null;
    }
    static void check(){if(Thread.currentThread().isInterrupted())throw new CancellationException();}
    static boolean valid(File file)throws IOException,NoSuchAlgorithmException {
        if(!file.isFile()||file.length()!=BYTES)return false;
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream in=new FileInputStream(file)){byte[] bytes=new byte[65536];int count;while((count=in.read(bytes))!=-1){check();digest.update(bytes,0,count);}}
        StringBuilder hex=new StringBuilder();for(byte b:digest.digest())hex.append(String.format(Locale.ROOT,"%02x",b&255));return SHA256.equals(hex.toString());
    }
    PanelDetector.Result detect(Bitmap image,PanelDetector.Result baseline,boolean manga){check();return baseline;}
    static final class Detection{final float score;final RectF rect;Detection(float score,RectF rect){this.score=score;this.rect=new RectF(rect);}}
    static float iou(RectF a,RectF b){float intersection=Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left))*Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));return intersection/Math.max(1e-9f,a.width()*a.height()+b.width()*b.height()-intersection);}
    static List<Detection> decode(float[][] rows,int left,int top,int width,int height)throws IOException {
        if(rows.length!=5||rows[0].length==0||rows[0].length>10000)throw new IOException("Model output mismatch");
        for(float[] row:rows)if(row.length!=rows[0].length)throw new IOException("Model output mismatch");
        List<Detection> candidates=new ArrayList<>();
        for(int i=0;i<rows[0].length;i++){
            if((i&1023)==0)check();float score=rows[4][i],cx=rows[0][i],cy=rows[1][i],w=rows[2][i],h=rows[3][i];
            if(!Float.isFinite(score)||score<.25f||score>1||!Float.isFinite(cx)||!Float.isFinite(cy)||!Float.isFinite(w)||!Float.isFinite(h)||w<=0||h<=0)continue;
            List<RectF> valid=PanelDetector.clean(Collections.singletonList(new RectF((cx-w/2-left)/width,(cy-h/2-top)/height,(cx+w/2-left)/width,(cy+h/2-top)/height)));
            if(!valid.isEmpty())candidates.add(new Detection(score,valid.get(0)));
        }
        candidates.sort((a,b)->Float.compare(b.score,a.score));List<Detection> kept=new ArrayList<>();
        for(Detection candidate:candidates.subList(0,Math.min(300,candidates.size()))){boolean duplicate=false;for(Detection prior:kept)if(iou(candidate.rect,prior.rect)>.5f){duplicate=true;break;}if(!duplicate)kept.add(candidate);if(kept.size()==PanelDetector.MAX_PANELS)break;}
        return kept;
    }
    static PanelDetector.Result combine(List<Detection> kept,PanelDetector.Result baseline,boolean manga,boolean spread){
        if(kept.isEmpty())return !baseline.fallback&&baseline.confidence>=.84f?baseline:new PanelDetector.Result(Collections.singletonList(new RectF(0,0,1,1)),true,.30f,"ai_whole_page");
        if(!baseline.fallback&&baseline.confidence>=.84f&&baseline.regions().size()>kept.size())return baseline;
        List<RectF> regions=new ArrayList<>();float score=0;for(Detection box:kept){regions.add(new RectF(box.rect));score+=box.score;}
        if(regions.size()==1){RectF rect=regions.get(0);if(rect.width()*rect.height()<.5f){
            if(rect.width()>=.75f&&rect.top<=.06f&&rect.bottom>=.08f&&rect.bottom<=.45f){regions.add(new RectF(0,Math.min(1,rect.bottom+.005f),1,1));return new PanelDetector.Result(PanelDetector.order(regions,manga,spread),true,.40f,"ai_partial");}
            return new PanelDetector.Result(Collections.singletonList(new RectF(0,0,1,1)),true,.30f,"ai_partial");
        }}
        return new PanelDetector.Result(PanelDetector.order(regions,manga,spread),false,score/kept.size(),"ai_local");
    }
    public void close(){}
}

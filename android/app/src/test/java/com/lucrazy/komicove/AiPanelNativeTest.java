package com.lucrazy.komicove;

import android.graphics.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.lang.reflect.Field;
import java.util.*;
import java.util.concurrent.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import static org.junit.Assert.*;

/** Opt-in actual CPU inference. Local comic pages stay in ignored build fixtures. */
@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35)
@org.robolectric.annotation.GraphicsMode(org.robolectric.annotation.GraphicsMode.Mode.NATIVE)
public class AiPanelNativeTest {
    private static Object field(AiPanelDetector ai,String name)throws Exception{
        Field f=ai.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(ai);
    }
    private static boolean match(int i,List<RectF> actual,List<RectF> expected,int[] matched,boolean[] seen){
        for(int target=0;target<expected.size();target++)if(!seen[target]&&AiPanelDetector.iou(actual.get(i),expected.get(target))>=.5f){
            seen[target]=true;if(matched[target]<0||match(matched[target],actual,expected,matched,seen)){matched[target]=i;return true;}
        }return false;
    }
    @Test public void realPagesNativeInferenceCacheForceAndCancellation()throws Exception{
        Assume.assumeTrue(Boolean.getBoolean("komicove.nativeAI"));
        String fixturePath=System.getenv("KOMICOVE_AI_FIXTURES");Assume.assumeNotNull(fixturePath);
        File directory=new File(fixturePath);
        JSONObject manifest=new JSONObject(new String(java.nio.file.Files.readAllBytes(new File(directory,"cases.json").toPath()),StandardCharsets.UTF_8));
        AiPanelDetector ai=AiPanelDetector.available(RuntimeEnvironment.getApplication());assertNotNull(ai);
        PanelDetector.Cache cache=new PanelDetector.Cache(128,ai);int tp=0,fp=0,fn=0,covers=0;
        Bitmap last=null;
        try{
            JSONArray cases=manifest.getJSONArray("cases");
            for(int c=0;c<cases.length();c++){
                JSONObject item=cases.getJSONObject(c);String key=item.getString("file");
                Bitmap image=BitmapFactory.decodeFile(new File(directory,key).getAbsolutePath());assertNotNull(image);
                try{
                    long start=System.nanoTime();PanelDetector.Result result=cache.detect(key,image,false,false);
                    assertNotNull("Native session must really load, not silently fall back",field(ai,"session"));
                    assertFalse((boolean)field(ai,"disabled"));assertTrue(result.method.startsWith("ai_"));
                    assertSame(result,cache.detect(key,image,false,false));
                    PanelDetector.Result fresh=cache.detect(key,image,false,true);assertNotSame(result,fresh);assertEquals(result.regions(),fresh.regions());
                    PanelDetector.Result manga=cache.detect(key,image,true,false);assertEquals(new HashSet<>(result.regions()),new HashSet<>(manga.regions()));
                    JSONArray boxes=item.getJSONArray("regions");List<RectF> expected=new ArrayList<>();
                    for(int b=0;b<boxes.length();b++){JSONArray r=boxes.getJSONArray(b);expected.add(new RectF((float)r.getDouble(0),(float)r.getDouble(1),(float)r.getDouble(2),(float)r.getDouble(3)));}
                    if(expected.isEmpty()){covers++;assertTrue(result.fallback);assertEquals(1,result.regions().size());}
                    else{
                        int[] matched=new int[expected.size()];Arrays.fill(matched,-1);int count=0;
                        for(int b=0;b<result.regions().size();b++)if(match(b,result.regions(),expected,matched,new boolean[expected.size()]))count++;
                        tp+=count;fp+=result.regions().size()-count;fn+=expected.size()-count;
                    }
                    System.out.println("Local Java AI case "+c+": "+result.regions().size()+" regions, "+result.method+", detect+cache+force+manga_ms="+(System.nanoTime()-start)/1e6);
                }finally{image.recycle();}
            }
            assertEquals(5,covers);assertTrue("Reviewed difficult pages must improve over the 16 matched baseline",tp>=26);assertTrue(fp<=2);assertTrue(fn<=2);
            System.out.println("Local Java AI diagnostic subset: matched="+tp+", extra="+fp+", missed="+fn+" (approximate fallback included)");
            last=BitmapFactory.decodeFile(new File(directory,cases.getJSONObject(5).getString("file")).getAbsolutePath());
            Bitmap input=last;Object session=field(ai,"session");
            ExecutorService worker=Executors.newSingleThreadExecutor();CountDownLatch finished=new CountDownLatch(1);
            java.util.concurrent.atomic.AtomicBoolean cancelled=new java.util.concurrent.atomic.AtomicBoolean();
            Future<?> task=worker.submit(()->{try{ai.detect(input,PanelDetector.analyze(input,false),false);}catch(CancellationException expected){cancelled.set(true);}finally{finished.countDown();}});
            try{
                long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(10);
                while(field(ai,"active")==null&&finished.getCount()>0&&System.nanoTime()<deadline)Thread.sleep(1);
                assertNotNull("Observe a real native inference in progress",field(ai,"active"));task.cancel(true);
                assertTrue(finished.await(5,TimeUnit.SECONDS));assertTrue(cancelled.get());assertFalse((boolean)field(ai,"disabled"));assertSame(session,field(ai,"session"));
                assertTrue(ai.detect(input,PanelDetector.analyze(input,false),false).method.startsWith("ai_"));
            }finally{worker.shutdownNow();assertTrue(worker.awaitTermination(5,TimeUnit.SECONDS));}
        }finally{if(last!=null)last.recycle();cache.close();}
        assertNull(field(ai,"session"));assertNull(field(ai,"buffer"));assertEquals(0,cache.size());
    }
}

package com.lucrazy.komicove;

import android.app.*;
import android.content.*;
import android.graphics.Bitmap;
import android.os.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;

/** Same real Activity workload on the baseline and Phase 6 APKs. */
public final class LibraryPhase6Instrumentation extends Instrumentation {
    private Activity active;
    private Bundle options;
    @Override public void onCreate(Bundle args){super.onCreate(args);options=args==null?new Bundle():args;start();}
    @Override public void onStart(){Bundle result=new Bundle();int status=Activity.RESULT_OK;
        try {
            Context context=getTargetContext();
            require(context.getPackageName().endsWith(".phase6test"),"Use isolated phase6-device.gradle");
            int size=Integer.parseInt(options.getString("size","1000"));
            require(size==1000||size==5000||size==10000,"Invalid size");
            context.getSharedPreferences("auth_state",0).edit().putString("mode","guest").commit();
            context.getSharedPreferences("panel_ui",0).edit().putString("lang",options.getString("lang","pt")).commit();
            LibraryStore store=new LibraryStore(context);JSONArray rows=new JSONArray();
            Bitmap cover=Bitmap.createBitmap(136,188,Bitmap.Config.RGB_565);cover.eraseColor(0xffff0000);
            for(int i=0;i<size;i++){
                LibraryStore.Book b=new LibraryStore.Book();b.id="fixture-"+i;b.file=b.id+".cbz";
                b.title="Issue "+i;b.series="Series "+(i%20);b.author="Author";b.updated=i;
                b.count=24;b.page=i%3==0?23:i%3==1?4:0;b.favorite=i%10==0;
                rows.put(b.json());
                try(OutputStream out=new FileOutputStream(store.cover(b))){cover.compress(Bitmap.CompressFormat.JPEG,85,out);}
            }
            cover.recycle();context.getSharedPreferences("library",0).edit().clear().putString("items",rows.toString()).commit();
            long start=SystemClock.elapsedRealtimeNanos();
            active=startActivitySync(new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            runOnMainSync(()->{active.setShowWhenLocked(true);active.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);});ready();
            double first=(SystemClock.elapsedRealtimeNanos()-start)/1e6;
            List<Double> searches=new ArrayList<>(),sorts=new ArrayList<>();
            for(String query:new String[]{"Issue 9","Issue 99","Issue 999","Author","","Issue 9","Issue 99","Issue 999","Author",""}){
                EditText search=find(active.getWindow().getDecorView(),EditText.class);require(search!=null,"Missing search");
                start=SystemClock.elapsedRealtimeNanos();runOnMainSync(()->search.setText(query));ready();searches.add((SystemClock.elapsedRealtimeNanos()-start)/1e6);
            }
            for(String mode:new String[]{"title_desc","series","recent","title"}){
                start=SystemClock.elapsedRealtimeNanos();runOnMainSync(()->{set(active,"sortMode",mode);invoke(active,"showLibrary");});ready();sorts.add((SystemClock.elapsedRealtimeNanos()-start)/1e6);
            }
            long before=usedHeap();int maxViews=0;
            // Same six Show more actions, then 30 viewport jumps, before and after.
            for(int i=0;i<6;i++){runOnMainSync(()->{set(active,"visibleLimit",(int)get(active,"visibleLimit")+80);invoke(active,"showLibrary");});ready();}
            for(int i=0;i<30;i++){
                final int step=i%5;ScrollView scroll=find(active.getWindow().getDecorView(),ScrollView.class);
                runOnMainSync(()->scroll.scrollTo(0,Math.max(0,scroll.getChildAt(0).getHeight()-scroll.getHeight())*step/4));
                waitForIdleSync();SystemClock.sleep(40);maxViews=Math.max(maxViews,count(active.getWindow().getDecorView()));
            }
            long after=usedHeap();Collections.sort(searches);Collections.sort(sorts);
            JSONObject metrics=new JSONObject().put("size",size).put("device",Build.MODEL).put("api",Build.VERSION.SDK_INT)
                .put("language",options.getString("lang","pt")).put("first_ms",first)
                .put("search_median_ms",searches.get(searches.size()/2)).put("search_max_ms",searches.get(searches.size()-1))
                .put("sort_median_ms",sorts.get(sorts.size()/2)).put("heap_before_navigation_bytes",before)
                .put("heap_after_navigation_bytes",after).put("max_view_count",maxViews)
                .put("pss_kb",pss());
            if(options.getString("verify","").equals("true"))verify(size,metrics);
            int soakSeconds=Integer.parseInt(options.getString("soakSeconds","0"));
            require(soakSeconds>=0&&soakSeconds<=600,"Invalid soak duration");
            if(soakSeconds>0)soak(size,soakSeconds,metrics);
            result.putString("stream","PHASE6 "+metrics+"\n");
        }catch(Throwable error){StringWriter trace=new StringWriter();error.printStackTrace(new PrintWriter(trace));status=Activity.RESULT_CANCELED;result.putString("stream",trace.toString());}
        finally{if(active!=null){runOnMainSync(active::finish);waitForIdleSync();}}
        finish(status,result);
    }
    private void soak(int size,int seconds,JSONObject metrics)throws Exception{
        runOnMainSync(()->{set(active,"tab","Biblioteca");set(active,"activeCollection",null);set(active,"visibleLimit",size);set(active,"selectMode",false);invoke(active,"showLibrary");});ready();
        require(find(active.getWindow().getDecorView(),EditText.class)!=null,"Missing soak search");
        Handler handler=new Handler(Looper.getMainLooper());List<Double> delays=new ArrayList<>();
        boolean[] running={true};long[] expected={SystemClock.elapsedRealtime()+16};
        Runnable beat=new Runnable(){public void run(){long now=SystemClock.elapsedRealtime();delays.add((double)Math.max(0,now-expected[0]));expected[0]=now+16;if(running[0])handler.postDelayed(this,16);}};
        handler.postDelayed(beat,16);
        JSONArray samples=new JSONArray(),queries=new JSONArray();long start=SystemClock.elapsedRealtime(),last=start,cpu=android.os.Process.getElapsedCpuTime(),nextQuery=start+10000;int step=0;
        while(SystemClock.elapsedRealtime()-start<seconds*1000L){
            ScrollView scroll=find(active.getWindow().getDecorView(),ScrollView.class);int position=step++%21;
            runOnMainSync(()->scroll.scrollTo(0,Math.max(0,scroll.getChildAt(0).getHeight()-scroll.getHeight())*position/20));
            long now=SystemClock.elapsedRealtime();
            if(now>=nextQuery){String query=new String[]{"Issue 99","Author",""}[queries.length()%3];EditText search=find(active.getWindow().getDecorView(),EditText.class);long queryStart=SystemClock.elapsedRealtimeNanos();runOnMainSync(()->search.setText(query));ready();queries.put((SystemClock.elapsedRealtimeNanos()-queryStart)/1e6);nextQuery=now+10000;}
            now=SystemClock.elapsedRealtime();
            if(now-last>=1000){long currentCpu=android.os.Process.getElapsedCpuTime();Runtime runtime=Runtime.getRuntime();Intent battery=getTargetContext().registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));PowerManager power=(PowerManager)getTargetContext().getSystemService(Context.POWER_SERVICE);
                JSONObject sample=new JSONObject().put("seconds",(now-start)/1000d).put("heap_bytes",runtime.totalMemory()-runtime.freeMemory()).put("pss_kb",pss())
                    .put("process_cpu_percent_one_core",100d*(currentCpu-cpu)/(now-last));
                if(battery!=null)sample.put("battery_celsius",battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,0)/10d).put("battery_plugged",battery.getIntExtra(BatteryManager.EXTRA_PLUGGED,0));
                if(Build.VERSION.SDK_INT>=29)sample.put("thermal_status",power.getCurrentThermalStatus());
                runOnMainSync(()->{try{Object covers=get(active,"libraryCovers");sample.put("view_count",count(active.getWindow().getDecorView())).put("cache_items",value(covers,"cacheItems")).put("cache_bytes",value(covers,"cacheBytes"));}catch(Exception e){throw new RuntimeException(e);}});
                samples.put(sample);last=now;cpu=currentCpu;
            }
            SystemClock.sleep(100);
        }
        runOnMainSync(()->{running[0]=false;handler.removeCallbacks(beat);});Collections.sort(delays);
        JSONObject soak=new JSONObject().put("duration_seconds",seconds).put("cpu_logical_cores",Runtime.getRuntime().availableProcessors()).put("samples",samples).put("search_ms",queries)
            .put("heartbeat_delay_p95_ms",delays.get((int)(delays.size()*.95))).put("heartbeat_delay_max_ms",delays.get(delays.size()-1)).put("heap_after_gc_bytes",usedHeap())
            .put("workload","10 scroll jumps/s; query every 10s; all items accessible; JPEG covers; USB connected");
        metrics.put("soak",soak);
    }
    private void verify(int size,JSONObject metrics)throws Exception{
        runOnMainSync(()->{set(active,"visibleLimit",size);set(active,"selectMode",true);invoke(active,"showLibrary");});ready();
        ScrollView scroll=find(active.getWindow().getDecorView(),ScrollView.class);
        runOnMainSync(()->scroll.fullScroll(View.FOCUS_DOWN));waitForIdleSync();SystemClock.sleep(120);
        TextView last=findText(active.getWindow().getDecorView(),"Issue "+(size-1));require(last!=null,"Last item not reachable");
        runOnMainSync(()->require(((View)last.getParent()).performClick(),"Card has no action"));
        require(((Set<?>)get(active,"selected")).contains("fixture-"+(size-1)),"Selection has wrong item");
        runOnMainSync(()->scroll.fullScroll(View.FOCUS_UP));waitForIdleSync();SystemClock.sleep(100);
        runOnMainSync(()->scroll.fullScroll(View.FOCUS_DOWN));waitForIdleSync();SystemClock.sleep(100);
        require(((Set<?>)get(active,"selected")).contains("fixture-"+(size-1)),"Recycling lost selection");
        View grid=findNamed(active.getWindow().getDecorView(),"LibraryViewport");require(grid!=null&&(int)value(grid,"mountedCount")<=40,"Unbounded viewport");
        Object covers=get(active,"libraryCovers");
        require((int)value(covers,"cacheItems")<=96&&(int)value(covers,"cacheBytes")<=16*1024*1024,"Unbounded cover cache");
        long warm=usedHeap();
        for(int i=0;i<20;i++){
            runOnMainSync(()->invoke(active,"settings"));waitForIdleSync();
            runOnMainSync(()->{set(active,"selectMode",false);invoke(active,"showLibrary");});ready();
            ScrollView current=find(active.getWindow().getDecorView(),ScrollView.class);
            runOnMainSync(()->current.fullScroll(View.FOCUS_DOWN));waitForIdleSync();SystemClock.sleep(60);
            require(count(active.getWindow().getDecorView())<400,"Views retained while navigating");
        }
        long stable=usedHeap();
        if(stable>=warm+24L*1024*1024)Debug.dumpHprofData(new File(getTargetContext().getExternalFilesDir(null),"phase6-navigation.hprof").getAbsolutePath());
        require(stable<warm+24L*1024*1024,"Navigation heap did not stabilize: warm="+warm+", after="+stable+", cover bindings="+((Set<?>)get(covers,"bindings")).size());
        require((int)value(covers,"cacheBytes")<=16*1024*1024&&(int)value(covers,"cacheItems")<=96,"Cache grew while navigating");
        runOnMainSync(()->{set(active,"tab","Coleções");invoke(active,"showLibrary");});ready();
        View collections=findNamed(active.getWindow().getDecorView(),"LibraryViewport");
        require(collections!=null&&(int)value(collections,"mountedCount")<=30,"Collections are not virtualized");
        metrics.put("verified_last_selection",true).put("verified_navigation_cycles",20)
            .put("heap_warm_bytes",warm).put("heap_after_20_navigation_bytes",stable)
            .put("cover_cache_bytes",value(covers,"cacheBytes")).put("cover_cache_items",value(covers,"cacheItems"));
    }
    private void ready(){
        long end=SystemClock.elapsedRealtime()+60000;
        while(SystemClock.elapsedRealtime()<end){waitForIdleSync();EditText search=find(active.getWindow().getDecorView(),EditText.class);
            boolean preparing=false;try{preparing=(boolean)get(active,"libraryPreparing");}catch(RuntimeException oldVersion){}
            if(search!=null&&!preparing){SystemClock.sleep(280);waitForIdleSync();try{preparing=(boolean)get(active,"libraryPreparing");}catch(RuntimeException oldVersion){}if(!preparing)return;}
            SystemClock.sleep(10);
        }throw new AssertionError("Library timeout");
    }
    private static long usedHeap(){Runtime r=Runtime.getRuntime();r.gc();SystemClock.sleep(40);return r.totalMemory()-r.freeMemory();}
    private static int pss(){Debug.MemoryInfo info=new Debug.MemoryInfo();Debug.getMemoryInfo(info);return info.getTotalPss();}
    private static int count(View v){int n=1;if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++)n+=count(((ViewGroup)v).getChildAt(i));return n;}
    private static <T extends View>T find(View v,Class<T> type){if(type.isInstance(v))return type.cast(v);if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++){T child=find(((ViewGroup)v).getChildAt(i),type);if(child!=null)return child;}return null;}
    private static TextView findText(View v,String text){if(v instanceof TextView&&text.contentEquals(((TextView)v).getText()))return (TextView)v;if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++){TextView found=findText(((ViewGroup)v).getChildAt(i),text);if(found!=null)return found;}return null;}
    private static View findNamed(View v,String name){if(v.getClass().getSimpleName().equals(name))return v;if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++){View found=findNamed(((ViewGroup)v).getChildAt(i),name);if(found!=null)return found;}return null;}
    private static Object get(Object object,String name){try{Field f=object.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(object);}catch(Exception e){throw new RuntimeException(e);}}
    private static void set(Object object,String name,Object value){try{Field f=object.getClass().getDeclaredField(name);f.setAccessible(true);f.set(object,value);}catch(Exception e){throw new RuntimeException(e);}}
    private static void invoke(Object object,String name){try{Method m=object.getClass().getDeclaredMethod(name);m.setAccessible(true);m.invoke(object);}catch(Exception e){throw new RuntimeException(e);}}
    private static Object value(Object object,String name){try{Method m=object.getClass().getDeclaredMethod(name);m.setAccessible(true);return m.invoke(object);}catch(Exception e){throw new RuntimeException(e);}}
    private static void require(boolean ok,String message){if(!ok)throw new AssertionError(message);}
}

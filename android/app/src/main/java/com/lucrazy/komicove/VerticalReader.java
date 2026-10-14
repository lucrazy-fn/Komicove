package com.lucrazy.komicove;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.ColorFilter;
import android.os.Handler;
import android.os.Looper;
import android.view.*;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;

/** ListView owns the visible rows; this loader owns only viewport bitmaps. */
final class VerticalReader extends ListView implements AutoCloseable {
    interface Listener {void page(int page);void idle();}
    private static final long CACHE_BYTES=16L*1024*1024;
    private final ReaderSession session;private final int count;private final Listener listener;
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final ThreadPoolExecutor decoder=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(1));
    private final Map<Integer,Bitmap> images=new HashMap<>();private final Set<Integer> failed=new HashSet<>();
    private final Map<Integer,Integer> decodedWidths=new HashMap<>();
    private final Rows rows=new Rows();private Future<?> task;private int active=-1,serial,first,last,width;
    private boolean closed,labels=true,prefetchBlocked;private ColorFilter filter;private final Runnable click;
    private int restorePage=-1;private float restoreOffset;private long bytes;
    VerticalReader(Context context,ReaderSession session,int count,Listener listener,Runnable click){
        super(context);this.session=session;this.count=count;this.listener=listener;this.click=click;
        session.trimMemory();setAdapter(rows);setRecyclerListener(view->{if(view instanceof LinearLayout)((ImageView)((LinearLayout)view).getChildAt(1)).setImageDrawable(null);});
        setOnScrollListener(new OnScrollListener(){
            public void onScrollStateChanged(AbsListView v,int state){if(state==SCROLL_STATE_IDLE)listener.idle();}
            public void onScroll(AbsListView v,int start,int visible,int total){
                if(closed||visible==0)return;if(first!=start||last!=Math.min(count-1,start+visible-1))prefetchBlocked=false;first=start;last=Math.min(count-1,start+visible-1);
                if(restorePage<0)listener.page(start);updateWindow();
            }
        });
    }
    void presentation(boolean labels,ColorFilter filter){this.labels=labels;this.filter=filter;refreshRows();}
    void restore(int page,float offset){restorePage=Math.max(0,Math.min(count-1,page));restoreOffset=Math.max(0,Math.min(.999f,offset));setSelectionFromTop(restorePage,0);applyRestore();}
    private void applyRestore(){if(restorePage>=0&&width>0&&session.verticalRatios.containsKey(restorePage)){int anchor=restorePage;float offset=restoreOffset;restorePage=-1;setSelectionFromTop(anchor,-Math.round(rowHeight(anchor)*offset));listener.page(anchor);}}
    int page(){return restorePage>=0?restorePage:getFirstVisiblePosition();}
    float offset(){View row=getChildAt(0);return restorePage>=0?restoreOffset:row==null?0:Math.max(0,Math.min(.999f,(getPaddingTop()-row.getTop())/(float)Math.max(1,row.getHeight())));}
    void jumpTo(int page){restore(page,0);}
    private boolean near(int page){return page>=Math.max(0,first-1)&&page<=Math.min(count-1,last+1);}
    private int rowHeight(int page){return Math.max(1,Math.round(Math.max(1,width)*session.verticalRatios.getOrDefault(page,1.4f)))+(labels?Ui.dp(getContext(),24):0);}
    @Override protected void onSizeChanged(int w,int h,int oldw,int oldh){
        int anchor=page();float offset=offset();super.onSizeChanged(w,h,oldw,oldh);
        if(w>0&&w!=width){width=w;cancel();failed.clear();prefetchBlocked=false;restore(anchor,offset);rows.notifyDataSetChanged();post(this::updateWindow);}
    }
    private void cancel(){serial++;if(task!=null)task.cancel(true);task=null;active=-1;decoder.purge();}
    private void updateWindow(){
        if(closed||width<=0)return;
        if(active>=0&&!near(active))cancel();
        for(int page:new ArrayList<>(images.keySet()))if(!near(page))drop(page);
        schedule();
    }
    private void schedule(){
        if(closed||active>=0||width<=0||count==0)return;
        int next=-1,target=Math.max(200,Math.min(width,2200));
        for(int page=first;page<=last;page++)if((!images.containsKey(page)||decodedWidths.getOrDefault(page,0)!=target)&&!failed.contains(page)){next=page;break;}
        // At most one adjacent page on each side, and one decode in flight.
        if(next<0&&!prefetchBlocked&&bytes<CACHE_BYTES)for(int page:new int[]{last+1,first-1})if(page>=0&&page<count&&!images.containsKey(page)&&!failed.contains(page)){next=page;break;}
        if(next<0)return;final int page=next,ticket=serial;active=page;
        try{task=decoder.submit(()->{
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
            Bitmap result=null;float ratio=1.4f;Exception failure=null;
            try{BookSource source=session.source();ratio=session.verticalRatios.containsKey(page)?session.verticalRatios.get(page):source.aspectRatio(page);BookSource.checkCancelled();result=source.page(page,target);}
            catch(Exception e){failure=e;}
            final Bitmap bitmap=result;final float aspect=ratio;final Exception error=failure;
            ui.post(()->{
                if(closed||ticket!=serial||!near(page)){if(bitmap!=null)bitmap.recycle();return;}
                active=-1;task=null;
                if(error==null){session.verticalRatios.put(page,aspect);Bitmap previous=images.put(page,bitmap);decodedWidths.put(page,target);bytes+=bitmap.getAllocationByteCount();refreshRows();if(previous!=null){bytes-=previous.getAllocationByteCount();previous.recycle();}
                    applyRestore();
                }else{failed.add(page);refreshRows();if(restorePage==page){restorePage=-1;listener.page(page);}}
                // Keep visible images even on a very short-page comic, discard speculative ones first.
                if(bytes>CACHE_BYTES){prefetchBlocked=true;for(int cached:new ArrayList<>(images.keySet()))if(cached<first||cached>last)drop(cached);}
                schedule();
            });
        });}catch(RejectedExecutionException ignored){active=-1;}
    }
    private void refreshRows(){for(int i=0;i<getChildCount();i++){View child=getChildAt(i);if(child instanceof LinearLayout&&child.getTag() instanceof Integer)bind((LinearLayout)child,(Integer)child.getTag());}}
    private void bind(LinearLayout cell,int page){
        TextView label=(TextView)cell.getChildAt(0);ImageView image=(ImageView)cell.getChildAt(1);
        label.setText(I18n.t(getContext(),"Página ")+(page+1)+(failed.contains(page)?I18n.t(getContext()," indisponível"):""));label.setVisibility(labels?View.VISIBLE:View.GONE);
        image.setContentDescription(I18n.t(getContext(),"Página ")+(page+1));image.setColorFilter(filter);image.setImageBitmap(images.get(page));
        int height=Math.max(1,rowHeight(page)-(labels?Ui.dp(getContext(),24):0));if(image.getLayoutParams().height!=height){image.getLayoutParams().height=height;image.requestLayout();}
    }
    private void drop(int page){
        Bitmap bitmap=images.remove(page);decodedWidths.remove(page);if(bitmap==null)return;
        for(int i=0;i<getChildCount();i++){View child=getChildAt(i);if(Integer.valueOf(page).equals(child.getTag()))((ImageView)((LinearLayout)child).getChildAt(1)).setImageDrawable(null);}
        bytes-=bitmap.getAllocationByteCount();bitmap.recycle();
    }
    private void dropAll(){for(int page:new ArrayList<>(images.keySet()))drop(page);}
    void trim(){cancel();dropAll();post(this::updateWindow);}
    int loadedPages(){return images.size();}long bitmapBytes(){return bytes;}int pendingDecodes(){return active<0?0:1;}
    Set<Integer> loadedIndices(){return new HashSet<>(images.keySet());}
    @Override public void close(){if(closed)return;closed=true;cancel();dropAll();decoder.shutdownNow();}
    private final class Rows extends BaseAdapter {
        public int getCount(){return count;}public Object getItem(int n){return n;}public long getItemId(int n){return n;}
        public View getView(int n,View recycled,ViewGroup parent){
            LinearLayout cell;
            if(recycled instanceof LinearLayout)cell=(LinearLayout)recycled;
            else{cell=Ui.column(getContext());TextView label=Ui.text(getContext(),"",14,Ui.MUTED);label.setGravity(Gravity.CENTER);cell.addView(label,new LinearLayout.LayoutParams(-1,Ui.dp(getContext(),24)));ImageView image=new ImageView(getContext());image.setScaleType(ImageView.ScaleType.FIT_CENTER);image.setOnClickListener(v->click.run());cell.addView(image,new LinearLayout.LayoutParams(-1,1));}
            cell.setTag(n);bind(cell,n);return cell;
        }
    }
}

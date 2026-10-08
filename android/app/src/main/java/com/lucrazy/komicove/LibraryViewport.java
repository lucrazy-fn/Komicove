package com.lucrazy.komicove;

import android.content.Context;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.view.*;
import java.util.*;

/** Existing cards, mounted only for the viewport and one neighboring row. */
final class LibraryViewport extends ViewGroup {
    interface Factory {View create(int index);}
    private final int columns;
    private int count,rowHeight;
    private final Factory factory;
    private final Map<Integer,View> mounted=new HashMap<>();
    private final Rect visible=new Rect();
    private boolean scheduled;
    private ViewTreeObserver observer;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final Runnable refreshTask=()->{scheduled=false;refresh();};
    private final ViewTreeObserver.OnScrollChangedListener scroll=this::schedule;
    private final ViewTreeObserver.OnGlobalLayoutListener layout=this::schedule;
    LibraryViewport(Context context,int columns,int count,Factory factory){super(context);this.columns=columns;this.count=count;this.factory=factory;setClipChildren(false);}
    void setCount(int value){count=value;clear();requestLayout();schedule();}
    private void clear(){removeAllViews();mounted.clear();}
    @Override protected void onAttachedToWindow(){super.onAttachedToWindow();observer=getViewTreeObserver();observer.addOnScrollChangedListener(scroll);observer.addOnGlobalLayoutListener(layout);schedule();}
    @Override protected void onDetachedFromWindow(){if(observer!=null&&observer.isAlive()){observer.removeOnScrollChangedListener(scroll);observer.removeOnGlobalLayoutListener(layout);}observer=null;main.removeCallbacks(refreshTask);scheduled=false;clear();super.onDetachedFromWindow();}
    private void schedule(){if(!scheduled&&isAttachedToWindow()){scheduled=true;main.postDelayed(refreshTask,16);}}
    @Override protected void onMeasure(int widthSpec,int heightSpec){
        int width=MeasureSpec.getSize(widthSpec),cell=Math.max(1,width/columns);
        if(rowHeight==0&&count>0){View sample=factory.create(0);sample.measure(MeasureSpec.makeMeasureSpec(cell,MeasureSpec.EXACTLY),MeasureSpec.makeMeasureSpec(0,MeasureSpec.UNSPECIFIED));rowHeight=Math.max(1,sample.getMeasuredHeight());}
        for(View child:mounted.values())child.measure(MeasureSpec.makeMeasureSpec(cell,MeasureSpec.EXACTLY),MeasureSpec.makeMeasureSpec(rowHeight,MeasureSpec.EXACTLY));
        setMeasuredDimension(width,((count+columns-1)/columns)*Math.max(1,rowHeight));
    }
    @Override protected void onLayout(boolean changed,int l,int t,int r,int b){
        int cell=Math.max(1,(r-l)/columns);
        for(Map.Entry<Integer,View> entry:mounted.entrySet()){int index=entry.getKey(),x=index%columns*cell,y=index/columns*rowHeight;entry.getValue().layout(x,y,x+cell,y+rowHeight);}
        schedule();
    }
    void refresh(){
        if(rowHeight==0||!isAttachedToWindow())return;
        int first=0,last=0;
        boolean changed=false;
        if(getLocalVisibleRect(visible)){first=Math.max(0,visible.top/rowHeight-1)*columns;last=Math.min(count,(visible.bottom/rowHeight+2)*columns);}
        Iterator<Map.Entry<Integer,View>> it=mounted.entrySet().iterator();
        while(it.hasNext()){Map.Entry<Integer,View> e=it.next();if(e.getKey()<first||e.getKey()>=last){removeView(e.getValue());it.remove();changed=true;}}
        for(int index=first;index<last;index++)if(!mounted.containsKey(index)){View card=factory.create(index);mounted.put(index,card);addView(card);changed=true;}
        if(changed)requestLayout();
    }
    int mountedCount(){return mounted.size();}
}

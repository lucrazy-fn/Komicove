package com.lucrazy.komicove;

import android.app.Activity;
import android.graphics.Bitmap;
import android.os.Looper;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35,qualifiers="w360dp-h800dp-xhdpi")
public class LibraryPhase6Test {
    private List<LibraryStore.Book> books(int size){List<LibraryStore.Book> books=new ArrayList<>();for(int i=size-1;i>=0;i--){LibraryStore.Book b=new LibraryStore.Book();b.id="book-"+i;b.file=b.id+".cbz";b.title="Issue "+i;b.series="Series "+i%20;b.author="Author";b.updated=i;b.favorite=i%10==0;b.count=24;b.page=i%3==0?23:i%3==1?4:0;books.add(b);}return books;}
    @Test public void searchSortFiltersAndCollectionsAtAllThreeSizes(){
        for(int size:new int[]{1000,5000,10000}){
            LibraryQuery query=new LibraryQuery(books(size));
            List<LibraryStore.Book> asc=query.select("","title","Todos",false,"","",null);
            assertEquals(size,asc.size());for(int i=0;i<size;i++)assertEquals("Issue "+i,asc.get(i).title);
            List<LibraryStore.Book> desc=query.select("","title_desc","Todos",false,"","",null);assertEquals("Issue "+(size-1),desc.get(0).title);
            List<LibraryStore.Book> recent=query.select("","recent","Todos",false,"","",null);assertEquals("Issue "+(size-1),recent.get(0).title);
            List<LibraryStore.Book> series=query.select("","series","Todos",false,"","",null);NaturalOrder order=new NaturalOrder();
            for(int i=1;i<series.size();i++){LibraryStore.Book a=series.get(i-1),b=series.get(i);int n=order.compare(a.series,b.series);assertTrue(n<0||n==0&&order.compare(a.title,b.title)<=0);}
            for(String search:new String[]{"Issue 9","Issue 99","Issue 999","Author",""}){
                List<LibraryStore.Book> matched=query.select(search,"title","Todos",false,"","",null);
                int expected=0;for(LibraryStore.Book b:asc)if((b.title+" "+b.series+" "+b.author).toLowerCase(Locale.ROOT).contains(search.toLowerCase(Locale.ROOT)))expected++;
                assertEquals(expected,matched.size());assertSame(matched,query.select(search,"title","Todos",false,"","",null));
            }
            assertEquals(size/10,query.select("","title","Todos",true,"","",null).size());
            assertEquals(size/20,query.select("","title","Todos",false,"series 7","AUTHOR",null).size());
            Set<String> ids=new HashSet<>(Arrays.asList("book-3","book-4","book-5"));
            assertEquals(3,query.select("","title","Todos",false,"","",ids).size());
            assertEquals("book-3",query.select("","title","Concluídas",false,"","",ids).get(0).id);
            assertEquals("book-4",query.select("","title","Em andamento",false,"","",ids).get(0).id);
            assertEquals("book-5",query.select("","title","Não lidas",false,"","",ids).get(0).id);
            for(int i=0;i<40;i++)query.select(String.valueOf(i),"title","Todos",false,"","",null);
            // Replacing a snapshot reflects mutations without retaining previous results.
            List<LibraryStore.Book> changed=books(size);changed.get(0).title="Edited";
            assertEquals(1,new LibraryQuery(changed).select("edited","title","Todos",false,"","",null).size());
        }
    }
    @Test public void viewportMountsBoundedCardsAndCanReachLastAtAllSizes(){
        for(int size:new int[]{1000,5000,10000}){
            ActivityController<Activity> controller=Robolectric.buildActivity(Activity.class).setup().visible();Activity activity=controller.get();
            ScrollView scroll=new ScrollView(activity);List<Integer> clicked=new ArrayList<>();
            LibraryViewport grid=new LibraryViewport(activity,3,size,index->{TextView card=new TextView(activity);card.setMinHeight(240);card.setText("Issue "+index);card.setOnClickListener(v->clicked.add(index));return card;});
            scroll.addView(grid);activity.setContentView(scroll);
            for(int step:new int[]{0,1,3,4,2,0,4}){
                scroll.measure(View.MeasureSpec.makeMeasureSpec(720,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(1600,View.MeasureSpec.EXACTLY));scroll.layout(0,0,720,1600);
                scroll.scrollTo(0,Math.max(0,grid.getMeasuredHeight()-1600)*step/4);grid.refresh();
                scroll.measure(View.MeasureSpec.makeMeasureSpec(720,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(1600,View.MeasureSpec.EXACTLY));scroll.layout(0,0,720,1600);
                assertTrue(grid.mountedCount()<=30);
            }
            boolean last=false;for(int i=0;i<grid.getChildCount();i++){View child=grid.getChildAt(i);if(((TextView)child).getText().equals("Issue "+(size-1))){child.performClick();last=true;}}
            assertTrue(last);assertEquals(Collections.singletonList(size-1),clicked);
            controller.pause().stop().destroy();assertEquals(0,grid.mountedCount());
        }
    }
    @Test public void offscreenCoverNeverQueuesOrDecodesAndDetachCancels()throws Exception{
        ActivityController<Activity> controller=Robolectric.buildActivity(Activity.class).setup().visible();Activity activity=controller.get();
        LibraryStore store=new LibraryStore(activity);LibraryCovers covers=new LibraryCovers(store);LibraryStore.Book book=books(1).get(0);
        ImageView image=new ImageView(activity);covers.bind(image,book);FrameLayout root=new FrameLayout(activity);FrameLayout.LayoutParams lp=new FrameLayout.LayoutParams(100,150);lp.topMargin=5000;root.addView(image,lp);activity.setContentView(root);
        root.measure(View.MeasureSpec.makeMeasureSpec(720,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(1600,View.MeasureSpec.EXACTLY));root.layout(0,0,720,1600);
        root.getViewTreeObserver().dispatchOnGlobalLayout();
        assertEquals(0,covers.queued());assertEquals(0,covers.cacheItems());
        root.removeAllViews();assertEquals(0,covers.queued());covers.close();controller.pause().stop().destroy();
    }
    @Test public void detachedGridAndCoversReleaseOriginalWindowObservers()throws Exception{
        ActivityController<Activity> controller=Robolectric.buildActivity(Activity.class).setup().visible();Activity activity=controller.get();
        FrameLayout root=new FrameLayout(activity);activity.setContentView(root);ViewTreeObserver observer=root.getViewTreeObserver();
        int scrollBefore=listeners(observer,"mOnScrollChangedListeners"),layoutBefore=listeners(observer,"mOnGlobalLayoutListeners");
        LibraryCovers covers=new LibraryCovers(new LibraryStore(activity));LibraryStore.Book book=books(1).get(0);
        for(int cycle=0;cycle<20;cycle++){
            LibraryViewport grid=new LibraryViewport(activity,3,10000,index->{ImageView image=new ImageView(activity);image.setMinimumHeight(240);covers.bind(image,book);return image;});
            root.addView(grid);root.measure(View.MeasureSpec.makeMeasureSpec(720,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(1600,View.MeasureSpec.EXACTLY));root.layout(0,0,720,1600);grid.refresh();
            assertTrue(listeners(observer,"mOnScrollChangedListeners")>scrollBefore);
            root.removeAllViews();assertEquals(scrollBefore,listeners(observer,"mOnScrollChangedListeners"));assertEquals(layoutBefore,listeners(observer,"mOnGlobalLayoutListeners"));
        }
        covers.close();controller.pause().stop().destroy();
    }
    private int listeners(ViewTreeObserver observer,String name)throws Exception{
        java.lang.reflect.Field field=ViewTreeObserver.class.getDeclaredField(name);field.setAccessible(true);Object array=field.get(observer);if(array==null)return 0;
        java.lang.reflect.Method size=array.getClass().getDeclaredMethod("size");size.setAccessible(true);return (int)size.invoke(array);
    }
}

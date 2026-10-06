package com.lucrazy.komicove;

import android.app.*;
import android.content.*;
import android.content.pm.ActivityInfo;
import android.graphics.*;
import android.os.*;
import android.view.*;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.*;
import java.io.*;
import java.lang.reflect.*;
import java.util.zip.*;

/** Exercises real system bars and reader bounds in the isolated test installation. */
public final class ReaderFullscreenInstrumentation extends Instrumentation {
    private ReaderActivity active;private LibraryStore store;private LibraryStore.Book book;
    private final StringBuilder log=new StringBuilder();
    @Override public void onCreate(Bundle args){super.onCreate(args);start();}
    @Override public void onStart(){Bundle result=new Bundle();int code=Activity.RESULT_OK;
        try{
            require(getTargetContext().getPackageName().equals("com.lucrazy.panel.phase4test"),"Use -Pphase4Test=true -PfullscreenTest=true");
            store=new LibraryStore(getTargetContext());Bitmap image=Bitmap.createBitmap(1080,2100,Bitmap.Config.ARGB_8888);image.eraseColor(Color.LTGRAY);
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(ZipOutputStream zip=new ZipOutputStream(bytes)){for(int i=0;i<3;i++){zip.putNextEntry(new ZipEntry(i+".png"));image.compress(Bitmap.CompressFormat.PNG,100,zip);zip.closeEntry();}}image.recycle();book=store.importStream(new ByteArrayInputStream(bytes.toByteArray()),"Fullscreen-phone.cbz");
            for(String lang:new String[]{"pt","en"})for(String mode:new String[]{"normal","manga","dupla","vertical","webtoon"}){
                I18n.language(getTargetContext(),lang);getTargetContext().getSharedPreferences("reader",0).edit().putBoolean("guided",false).commit();book=store.get(book.id);book.mode=mode;book.page=0;store.save(book);open();ready();
                int page=(int)field("index");runOnMainSync(()->invoke("toggleControls"));waitForIdleSync();Thread.sleep(350);
                require(!(boolean)field("immersiveControls")&&((View)field("top")).getVisibility()==View.VISIBLE,"Minimize became fullscreen");
                runOnMainSync(()->invoke("toggleControls"));waitForIdleSync();Thread.sleep(350);
                runOnMainSync(()->click(root(),lang.equals("pt")?"Tela cheia":"Full screen"));full();
                require((int)field("index")==page,"Page changed entering fullscreen");if(mode.equals("normal"))shot("fullscreen-phone-"+lang);
                tapReadingArea();restored();require((int)field("index")==page,"Page changed restoring controls");
                runOnMainSync(()->click(root(),lang.equals("pt")?"Tela cheia":"Full screen"));full();sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);restored();require(!active.isFinishing(),"Back closed the reader instead of leaving fullscreen");
                if(mode.equals("normal")&&lang.equals("en")){
                    runOnMainSync(()->invoke("toggleFullscreen"));full();rotate(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE);ready();full();shot("fullscreen-phone-landscape");rotate(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);ready();full();sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);restored();
                }
                close();log.append("PASS ").append(lang).append(" ").append(mode).append(": separate minimize, hidden system bars, full canvas, tap/Back restore, page preserved\n");
            }
            getTargetContext().getSharedPreferences("reader",0).edit().putBoolean("guided",true).commit();book=store.get(book.id);book.mode="normal";book.page=0;book.customPanels.put("0",new org.json.JSONArray("[[0,0,1,0.5],[0,0.5,1,1]]"));store.save(book);open();ready();
            close();for(String lang:new String[]{"pt","en"}){
                I18n.language(getTargetContext(),lang);open();ready();int panel=(int)field("panelIndex");
                require(!(boolean)field("overview")&&((ZoomPage)field("pageView")).zoom>1,"Guided reading opened as a whole page");
                Button locate=(Button)field("guidedOverviewButton");require((lang.equals("pt")?"Se localizar":"Find your place").contentEquals(locate.getText()),"Locate label not translated");
                shot("guided-focused-phone-"+lang);runOnMainSync(locate::performClick);require((boolean)field("overview")&&((ZoomPage)field("pageView")).zoom==1,"Locate did not show the whole page");shot("guided-locate-phone-"+lang);
                require((lang.equals("pt")?"Voltar ao quadro":"Return to panel").contentEquals(locate.getText()),"Return label not translated");runOnMainSync(locate::performClick);require(!(boolean)field("overview")&&(int)field("panelIndex")==panel&&((ZoomPage)field("pageView")).zoom>1,"Return did not restore the same panel");
                View button=findAccessible((View)field("guidedZoom"),lang.equals("pt")?"Tela cheia":"Full screen");require(button!=null&&button.isShown(),"Guided fullscreen button missing");shot("fullscreen-phone-guided-controls-"+lang);
                runOnMainSync(button::performClick);full();require((boolean)field("guided")&&(int)field("panelIndex")==panel,"Fullscreen changed guided reading");runOnMainSync(()->invoke("updateCounter"));full();shot("fullscreen-phone-guided");tapReadingArea();restored();require(((View)field("guidedHeader")).getVisibility()==View.VISIBLE,"Guided controls did not return");
                runOnMainSync(button::performClick);full();sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);restored();require(!active.isFinishing()&&(boolean)field("guided"),"Back exited guided reading");close();log.append("PASS guided ").append(lang).append(": starts focused, locate/return same panel, visible fullscreen button, full canvas, tap/Back restores\n");
            }
            log.append("PASS fullscreen survives landscape/portrait recreation\n");result.putString("stream",log.toString());
        }catch(Throwable e){StringWriter trace=new StringWriter();e.printStackTrace(new PrintWriter(trace));code=Activity.RESULT_CANCELED;result.putString("stream",log+"FAIL "+trace);}
        finally{close();if(book!=null)store.remove(book);}finish(code,result);
    }
    private void open(){active=(ReaderActivity)startActivitySync(new Intent(getTargetContext(),ReaderActivity.class).putExtra("book",book.id).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));runOnMainSync(()->active.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON));waitForIdleSync();}
    private void close(){if(active!=null){ReaderActivity a=active;runOnMainSync(a::finish);waitForIdleSync();active=null;}}
    private View root(){return active.getWindow().getDecorView();}
    private Object field(String name){try{Field f=ReaderActivity.class.getDeclaredField(name);f.setAccessible(true);return f.get(active);}catch(Exception e){throw new RuntimeException(e);}}
    private void invoke(String name){try{Method m=ReaderActivity.class.getDeclaredMethod(name);m.setAccessible(true);m.invoke(active);}catch(Exception e){throw new RuntimeException(e);}}
    private void ready()throws Exception{long end=System.currentTimeMillis()+20000;do{waitForIdleSync();if(field("source")!=null&&!(boolean)field("loading"))return;Thread.sleep(20);}while(System.currentTimeMillis()<end);throw new AssertionError("Reader not ready");}
    private boolean fullBounds(){View root=(View)field("root"),canvas=(View)field("canvas");WindowInsets insets=active.getWindow().getDecorView().getRootWindowInsets();return insets!=null&&!insets.isVisible(WindowInsets.Type.statusBars())&&!insets.isVisible(WindowInsets.Type.navigationBars())&&canvas.getHeight()==root.getHeight()&&canvas.getWidth()==root.getWidth()&&root.getHeight()==active.getWindow().getDecorView().getHeight();}
    private void full()throws Exception{long end=System.currentTimeMillis()+5000;do{waitForIdleSync();if(fullBounds())break;Thread.sleep(30);}while(System.currentTimeMillis()<end);require(fullBounds(),"System bars visible or canvas does not occupy the whole window");require((boolean)field("immersiveControls"),"Fullscreen state missing");for(String n:new String[]{"top","guidedHeader","bottomShell"})require(((View)field(n)).getVisibility()==View.GONE,"Chrome remains: "+n);}
    private void restored()throws Exception{long end=System.currentTimeMillis()+5000;do{waitForIdleSync();if(!(boolean)field("immersiveControls")&&((View)field("bottomShell")).getVisibility()==View.VISIBLE)return;Thread.sleep(30);}while(System.currentTimeMillis()<end);throw new AssertionError("Fullscreen did not restore controls");}
    private void click(View v,String text){if(v instanceof Button&&text.contentEquals(((Button)v).getText())){v.performClick();return;}if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++)click(((ViewGroup)v).getChildAt(i),text);}
    private View findAccessible(View v,String text){if(text.contentEquals(v.getContentDescription()==null?"":v.getContentDescription()))return v;if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++){View found=findAccessible(((ViewGroup)v).getChildAt(i),text);if(found!=null)return found;}return null;}
    private ImageView image(View v){if(v instanceof ImageView)return (ImageView)v;if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++){ImageView found=image(((ViewGroup)v).getChildAt(i));if(found!=null)return found;}return null;}
    private void tapReadingArea(){View view=(View)field("pageView");if(view==null)view=image((View)field("vertical"));require(view!=null,"No tappable reading area");Rect bounds=new Rect();require(view.getGlobalVisibleRect(bounds),"Reading area invisible");long now=SystemClock.uptimeMillis();MotionEvent down=MotionEvent.obtain(now,now,MotionEvent.ACTION_DOWN,bounds.centerX(),bounds.centerY(),0),up=MotionEvent.obtain(now,now+50,MotionEvent.ACTION_UP,bounds.centerX(),bounds.centerY(),0);sendPointerSync(down);sendPointerSync(up);down.recycle();up.recycle();}
    private void rotate(int orientation)throws Exception{ActivityMonitor monitor=addMonitor(ReaderActivity.class.getName(),null,false);try{runOnMainSync(()->active.setRequestedOrientation(orientation));Activity changed=waitForMonitorWithTimeout(monitor,15000);require(changed instanceof ReaderActivity,"Reader did not recreate for rotation");active=(ReaderActivity)changed;}finally{removeMonitor(monitor);}waitForIdleSync();}
    private void clickAccessible(String text)throws Exception{long end=System.currentTimeMillis()+5000;do{AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();if(root!=null)for(AccessibilityNodeInfo node:root.findAccessibilityNodeInfosByText(text)){if(node.getText()==null||!text.equalsIgnoreCase(node.getText().toString()))continue;while(node!=null&&!node.isClickable())node=node.getParent();if(node!=null&&node.performAction(AccessibilityNodeInfo.ACTION_CLICK)){waitForIdleSync();return;}}Thread.sleep(30);}while(System.currentTimeMillis()<end);throw new AssertionError("Missing menu action: "+text);}
    private void shot(String name)throws Exception{final Bitmap[] capture={null};runOnMainSync(()->{View v=root();capture[0]=Bitmap.createBitmap(v.getWidth(),v.getHeight(),Bitmap.Config.ARGB_8888);v.draw(new Canvas(capture[0]));});try(FileOutputStream out=new FileOutputStream(new File(getTargetContext().getCacheDir(),name+".png"))){capture[0].compress(Bitmap.CompressFormat.PNG,100,out);}finally{capture[0].recycle();}}
    private static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
}

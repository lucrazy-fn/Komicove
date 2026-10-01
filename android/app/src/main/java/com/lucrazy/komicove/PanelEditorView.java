package com.lucrazy.komicove;

import android.content.Context;
import android.graphics.*;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;
import java.util.*;

final class PanelEditorView extends View {
    private static final int NONE=0, CREATE=1, MOVE=2, LEFT=3, RIGHT=4, TOP=5, BOTTOM=6,
            TOP_LEFT=7, TOP_RIGHT=8, BOTTOM_LEFT=9, BOTTOM_RIGHT=10;
    private final Bitmap image;
    final ArrayList<RectF> panels=new ArrayList<>();
    int selected=-1;
    private int mode=NONE;
    private float sx,sy;
    private RectF original;
    private final Paint bitmapPaint=new Paint(Paint.FILTER_BITMAP_FLAG);
    private final Paint line=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint label=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint selectedFill=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint handleOuter=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint handleInner=new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF imageBox=new RectF();
    private final float handleRadius,touchRadius;

    PanelEditorView(Context c,Bitmap bitmap,List<RectF> source){
        super(c);image=bitmap;
        for(RectF r:source)panels.add(new RectF(r));
        line.setStyle(Paint.Style.STROKE);line.setStrokeWidth(Ui.dp(c,3));
        label.setTextSize(Ui.dp(c,15));label.setColor(Color.WHITE);label.setFakeBoldText(true);
        selectedFill.setColor(0x22ff2741);handleOuter.setColor(Color.WHITE);handleInner.setColor(Ui.RED);
        handleRadius=Ui.dp(c,10);touchRadius=Ui.dp(c,36);
        setMinimumHeight(Ui.dp(c,440));setFocusable(true);
        setContentDescription("Editor de quadros. Toque em um quadro para selecionar e arraste as alças para redimensionar.");
    }

    @Override protected void onDraw(Canvas c){
        super.onDraw(c);
        if(image==null||image.getWidth()==0||image.getHeight()==0)return;
        float scale=Math.min(getWidth()/(float)image.getWidth(),getHeight()/(float)image.getHeight());
        float w=image.getWidth()*scale,h=image.getHeight()*scale;
        imageBox.set((getWidth()-w)/2f,(getHeight()-h)/2f,(getWidth()+w)/2f,(getHeight()+h)/2f);
        c.drawColor(Color.rgb(8,8,14));c.drawBitmap(image,null,imageBox,bitmapPaint);
        for(int i=0;i<panels.size();i++){
            RectF r=screen(panels.get(i));boolean active=i==selected;
            if(active)c.drawRoundRect(r,Ui.dp(getContext(),3),Ui.dp(getContext(),3),selectedFill);
            line.setColor(active?Ui.RED:0xff52d6ff);line.setStrokeWidth(Ui.dp(getContext(),active?3:2));
            c.drawRoundRect(r,Ui.dp(getContext(),3),Ui.dp(getContext(),3),line);
            c.drawText(String.valueOf(i+1),r.left+Ui.dp(getContext(),8),r.top+Ui.dp(getContext(),20),label);
            if(active)drawHandles(c,r);
        }
    }

    private void drawHandles(Canvas c,RectF r){
        float cx=r.centerX(),cy=r.centerY();
        float[][] points={{r.left,r.top},{cx,r.top},{r.right,r.top},{r.right,cy},
                {r.right,r.bottom},{cx,r.bottom},{r.left,r.bottom},{r.left,cy}};
        for(float[] p:points){c.drawCircle(p[0],p[1],handleRadius+Ui.dp(getContext(),2),handleOuter);c.drawCircle(p[0],p[1],handleRadius,handleInner);}
    }

    private RectF screen(RectF r){return new RectF(imageBox.left+r.left*imageBox.width(),imageBox.top+r.top*imageBox.height(),imageBox.left+r.right*imageBox.width(),imageBox.top+r.bottom*imageBox.height());}
    private float nx(float x){return Math.max(0,Math.min(1,(x-imageBox.left)/Math.max(1,imageBox.width())));}
    private float ny(float y){return Math.max(0,Math.min(1,(y-imageBox.top)/Math.max(1,imageBox.height())));}
    private boolean near(float x,float y,float px,float py){float dx=x-px,dy=y-py;return dx*dx+dy*dy<=touchRadius*touchRadius;}
    private int hitHandle(RectF r,float x,float y){
        float cx=r.centerX(),cy=r.centerY();
        if(near(x,y,r.left,r.top))return TOP_LEFT;if(near(x,y,r.right,r.top))return TOP_RIGHT;
        if(near(x,y,r.left,r.bottom))return BOTTOM_LEFT;if(near(x,y,r.right,r.bottom))return BOTTOM_RIGHT;
        if(near(x,y,cx,r.top))return TOP;if(near(x,y,cx,r.bottom))return BOTTOM;
        if(near(x,y,r.left,cy))return LEFT;if(near(x,y,r.right,cy))return RIGHT;return NONE;
    }

    @Override public boolean onTouchEvent(MotionEvent e){
        if(imageBox.isEmpty())return true;
        float px=e.getX(),py=e.getY(),x=nx(px),y=ny(py);
        if(e.getAction()==MotionEvent.ACTION_DOWN){
            sx=x;sy=y;mode=NONE;int prior=selected;
            if(selected>=0){int handle=hitHandle(screen(panels.get(selected)),px,py);if(handle!=NONE){mode=handle;original=new RectF(panels.get(selected));}}
            if(mode==NONE){selected=-1;for(int i=panels.size()-1;i>=0;i--){RectF r=panels.get(i);int handle=hitHandle(screen(r),px,py);if(handle!=NONE||r.contains(x,y)){selected=i;original=new RectF(r);mode=handle==NONE?MOVE:handle;break;}}}
            if(mode==NONE&&imageBox.contains(px,py)){mode=CREATE;panels.add(new RectF(x,y,x,y));selected=panels.size()-1;original=new RectF(x,y,x,y);}
            if(selected!=prior&&selected>=0)performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
            invalidate();return true;
        }
        if(e.getAction()==MotionEvent.ACTION_MOVE&&selected>=0){
            RectF r=new RectF(original);
            float minX=Ui.dp(getContext(),28)/Math.max(1,imageBox.width()),minY=Ui.dp(getContext(),28)/Math.max(1,imageBox.height());
            if(mode==CREATE)r.set(Math.min(sx,x),Math.min(sy,y),Math.max(sx,x),Math.max(sy,y));
            else if(mode==MOVE){float dx=x-sx,dy=y-sy;dx=Math.max(-r.left,Math.min(1-r.right,dx));dy=Math.max(-r.top,Math.min(1-r.bottom,dy));r.offset(dx,dy);}
            else{
                if(mode==LEFT||mode==TOP_LEFT||mode==BOTTOM_LEFT)r.left=Math.min(x,r.right-minX);
                if(mode==RIGHT||mode==TOP_RIGHT||mode==BOTTOM_RIGHT)r.right=Math.max(x,r.left+minX);
                if(mode==TOP||mode==TOP_LEFT||mode==TOP_RIGHT)r.top=Math.min(y,r.bottom-minY);
                if(mode==BOTTOM||mode==BOTTOM_LEFT||mode==BOTTOM_RIGHT)r.bottom=Math.max(y,r.top+minY);
                r.left=Math.max(0,r.left);r.top=Math.max(0,r.top);r.right=Math.min(1,r.right);r.bottom=Math.min(1,r.bottom);
            }
            panels.set(selected,r);invalidate();return true;
        }
        if(e.getAction()==MotionEvent.ACTION_UP||e.getAction()==MotionEvent.ACTION_CANCEL){
            if(selected>=0){RectF r=panels.get(selected);float minX=Ui.dp(getContext(),20)/Math.max(1,imageBox.width()),minY=Ui.dp(getContext(),20)/Math.max(1,imageBox.height());if(r.width()<minX||r.height()<minY){panels.remove(selected);selected=-1;}}
            mode=NONE;invalidate();return true;
        }
        return true;
    }

    void deleteSelected(){if(selected>=0){panels.remove(selected);selected=-1;invalidate();}}
    void reorder(int d){if(selected<0)return;int n=Math.max(0,Math.min(panels.size()-1,selected+d));Collections.swap(panels,selected,n);selected=n;invalidate();}
    void nudge(float dx,float dy){if(selected<0)return;RectF r=panels.get(selected);dx=Math.max(-r.left,Math.min(1-r.right,dx));dy=Math.max(-r.top,Math.min(1-r.bottom,dy));r.offset(dx,dy);invalidate();}
    void resize(float amount){if(selected<0)return;RectF r=panels.get(selected);float a=Math.min(amount,Math.min((1-r.width())/2f,(1-r.height())/2f));if(amount<0)a=Math.max(amount,-Math.min(r.width(),r.height())/2f+.015f);r.inset(-a,-a);if(r.left<0)r.offset(-r.left,0);if(r.top<0)r.offset(0,-r.top);if(r.right>1)r.offset(1-r.right,0);if(r.bottom>1)r.offset(0,1-r.bottom);invalidate();}
}

package com.lucrazy.panel;

import android.content.Context;
import android.graphics.*;
import android.view.*;
import android.view.ViewConfiguration;

final class ZoomPage extends View {
    interface Actions {void next();void previous();void toggle();}
    Bitmap image;float zoom=1,panX,panY;private float downX,downY,lastX,lastY;private boolean pinching,moved;private final float touchSlop;
    private final ScaleGestureDetector scale;private final GestureDetector gestures;private final Actions actions;
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
    ZoomPage(Context c,Actions a){super(c);actions=a;touchSlop=ViewConfiguration.get(c).getScaledTouchSlop();setContentDescription("Página do quadrinho. Use dois dedos para ampliar; deslize para trocar de página.");setFocusable(true);
        scale=new ScaleGestureDetector(c,new ScaleGestureDetector.SimpleOnScaleGestureListener(){
            public boolean onScale(ScaleGestureDetector d){float old=zoom;zoom=Math.max(1,Math.min(6,zoom*d.getScaleFactor()));panX=(panX-(d.getFocusX()-getWidth()/2f))*zoom/old+(d.getFocusX()-getWidth()/2f);panY=(panY-(d.getFocusY()-getHeight()/2f))*zoom/old+(d.getFocusY()-getHeight()/2f);clamp();invalidate();return true;}
        });
        gestures=new GestureDetector(c,new GestureDetector.SimpleOnGestureListener(){public boolean onDown(android.view.MotionEvent e){return true;}
            public boolean onDoubleTap(MotionEvent e){zoom=zoom>1?1:2.5f;panX=panY=0;clamp();invalidate();return true;}
            public boolean onSingleTapConfirmed(MotionEvent e){if(moved||pinching)return true;if(e.getX()<getWidth()*.22)actions.previous();else if(e.getX()>getWidth()*.78)actions.next();else actions.toggle();performClick();return true;}});
    }
    void focus(RectF region){
        if(image==null||getWidth()==0||getHeight()==0)return;
        float s=Math.min(getWidth()/(region.width()*image.getWidth()),getHeight()/(region.height()*image.getHeight()))*.96f;
        zoom=Math.max(1,Math.min(6,s/fit()));s=fit()*zoom;
        panX=(.5f-region.centerX())*image.getWidth()*s;panY=(.5f-region.centerY())*image.getHeight()*s;
        clamp();invalidate();
    }
    void setImage(Bitmap b){image=b;clamp();invalidate();}
    void restore(float z,float x,float y){zoom=Math.max(1,Math.min(6,z));panX=x*getWidth();panY=y*getHeight();clamp();invalidate();}
    void fitToScreen(){zoom=1;panX=panY=0;clamp();invalidate();}
    float normalizedX(){return getWidth()==0?0:panX/getWidth();}float normalizedY(){return getHeight()==0?0:panY/getHeight();}
    private float fit(){return image==null?1:Math.min((float)getWidth()/image.getWidth(),(float)getHeight()/image.getHeight());}
    private void clamp(){if(image==null)return;float s=fit()*zoom;float mx=Math.max(0,(image.getWidth()*s-getWidth())/2),my=Math.max(0,(image.getHeight()*s-getHeight())/2);panX=Math.max(-mx,Math.min(mx,panX));panY=Math.max(-my,Math.min(my,panY));}
    @Override protected void onSizeChanged(int w,int h,int oldw,int oldh){if(oldw>0)panX*=w/(float)oldw;if(oldh>0)panY*=h/(float)oldh;clamp();}
    @Override protected void onDraw(Canvas c){super.onDraw(c);if(image==null)return;c.save();c.translate(getWidth()/2f+panX,getHeight()/2f+panY);float s=fit()*zoom;c.scale(s,s);c.drawBitmap(image,-image.getWidth()/2f,-image.getHeight()/2f,paint);c.restore();}
    @Override public boolean performClick(){super.performClick();return true;}
    @Override public boolean onTouchEvent(MotionEvent e){scale.onTouchEvent(e);gestures.onTouchEvent(e);
        if(e.getActionMasked()==MotionEvent.ACTION_DOWN){downX=lastX=e.getX();downY=lastY=e.getY();pinching=false;moved=false;}
        if(e.getPointerCount()>1)pinching=true;
        if(e.getActionMasked()==MotionEvent.ACTION_MOVE&&e.getPointerCount()==1&&!scale.isInProgress()){float dx=e.getX()-downX,dy=e.getY()-downY;if(Math.hypot(dx,dy)>=touchSlop)moved=true;if(zoom>1){panX+=e.getX()-lastX;panY+=e.getY()-lastY;clamp();invalidate();}lastX=e.getX();lastY=e.getY();}
        if(e.getActionMasked()==MotionEvent.ACTION_UP&&!pinching&&zoom<=1.01&&moved){float dx=e.getX()-downX,dy=e.getY()-downY;if(Math.abs(dx)>Ui.dp(getContext(),65)&&Math.abs(dx)>Math.abs(dy)*1.5){if(dx<0)actions.next();else actions.previous();}}
        if(e.getActionMasked()==MotionEvent.ACTION_CANCEL){pinching=false;moved=true;}
        return true;
    }
}

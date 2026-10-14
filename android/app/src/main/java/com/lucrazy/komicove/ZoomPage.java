package com.lucrazy.komicove;

import android.content.Context;
import android.graphics.*;
import android.text.Layout;
import android.text.StaticLayout;
import android.text.TextPaint;
import android.text.TextUtils;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.RelativeSizeSpan;
import android.os.Handler;
import android.os.Looper;
import android.view.*;
import android.view.ViewConfiguration;

final class ZoomPage extends View {
    interface Actions {void next();void previous();void toggle();}
    private android.animation.ValueAnimator animator;
    private void stopAnimation(){if(animator!=null){animator.cancel();animator=null;}}
    @Override protected void onDetachedFromWindow(){stopAnimation();tileGeneration++;clearTiles();super.onDetachedFromWindow();}
    private RectF overviewRegion;
    private RectF focusedRegion;
    private java.util.List<ComicTranslation.Region> translationRegions=java.util.Collections.emptyList();
    private boolean translationOverlay;
    private boolean translationCompare;
    private static final java.util.concurrent.ExecutorService tileWorker=java.util.concurrent.Executors.newSingleThreadExecutor();
    private final Handler tileHandler=new Handler(Looper.getMainLooper());
    private int tileGeneration;
    private java.util.List<TranslationTile> translationTiles=java.util.Collections.emptyList();
    private static final class TranslationTile {
        final int index,left,top;final ComicTextReconstruction.Result result;
        TranslationTile(int index,int left,int top,ComicTextReconstruction.Result result){this.index=index;this.left=left;this.top=top;this.result=result;}
    }
    static CharSequence styledTranslation(String value,float[] scales){
        if(scales==null||scales.length==0)return value;
        java.util.regex.Matcher countMatcher=java.util.regex.Pattern.compile("\\S+").matcher(value);int count=0;
        while(countMatcher.find())count++;
        if(count==0)return value;
        SpannableString styled=new SpannableString(value);java.util.regex.Matcher words=java.util.regex.Pattern.compile("\\S+").matcher(value);
        float peak=1;for(float scale:scales)peak=Math.max(peak,scale);
        for(int index=0;words.find();index++){
            int source=Math.max(0,Math.min(scales.length-1,Math.round((index+.5f)*scales.length/count-.5f)));
            float ratio=(float)Math.pow(Math.max(.3f,Math.min(1f,scales[source]/peak)),1.15);
            if(Math.abs(ratio-1)>.08f)styled.setSpan(new RelativeSizeSpan(ratio),words.start(),words.end(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        }
        return styled;
    }
    Bitmap image;float zoom=1,panX,panY;private float downX,downY,lastX,lastY,controlsProgress,controlsFreed,controlsBaseFit;private boolean pinching,moved;private final float touchSlop;
    private final ScaleGestureDetector scale;private final GestureDetector gestures;private final Actions actions;
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.FILTER_BITMAP_FLAG);
    private final Typeface comicFont;
    ZoomPage(Context c,Actions a){super(c);actions=a;touchSlop=ViewConfiguration.get(c).getScaledTouchSlop();Typeface face;try{face=Typeface.createFromAsset(c.getAssets(),"fonts/ComicNeue-Regular.ttf");}catch(RuntimeException e){face=Typeface.DEFAULT;}comicFont=face;setContentDescription(I18n.t(c,"Página do quadrinho. Use dois dedos para ampliar; deslize para trocar de página."));setFocusable(true);
        scale=new ScaleGestureDetector(c,new ScaleGestureDetector.SimpleOnScaleGestureListener(){
            public boolean onScale(ScaleGestureDetector d){float old=zoom;zoom=Math.max(minimumZoom(),Math.min(6,zoom*d.getScaleFactor()));panX=(panX-(d.getFocusX()-getWidth()/2f))*zoom/old+(d.getFocusX()-getWidth()/2f);panY=(panY-(d.getFocusY()-getHeight()/2f))*zoom/old+(d.getFocusY()-getHeight()/2f);clamp();invalidate();return true;}
        });
        gestures=new GestureDetector(c,new GestureDetector.SimpleOnGestureListener(){public boolean onDown(android.view.MotionEvent e){return true;}
            public boolean onDoubleTap(MotionEvent e){if(overviewRegion!=null)return true;if(focusedRegion!=null){RectF selected=new RectF(focusedRegion);if(zoom>1)focus(selected);else zoomBy(2.5f);return true;}zoom=zoom>1?1:2.5f;panX=panY=0;clamp();invalidate();return true;}
            public boolean onSingleTapConfirmed(MotionEvent e){if(moved||pinching)return true;if(e.getX()<getWidth()*.22)actions.previous();else if(e.getX()>getWidth()*.78)actions.next();else actions.toggle();performClick();return true;}});
    }
    void focus(RectF region){focus(region,false);}
    void focus(RectF region,boolean animate){
        if(region==null||!Float.isFinite(region.left)||!Float.isFinite(region.top)||!Float.isFinite(region.right)||!Float.isFinite(region.bottom))return;
        RectF target=new RectF(region);if(!target.intersect(0,0,1,1)||target.width()<=0||target.height()<=0)return;
        stopAnimation();float oldZoom=zoom,oldX=panX,oldY=panY;
        if(image==null||getWidth()==0||getHeight()==0)return;
        RectF previous=focusedRegion==null?new RectF(0,0,1,1):new RectF(focusedRegion);focusedRegion=new RectF(target);
        float s=Math.min(getWidth()/(target.width()*image.getWidth()),getHeight()/(target.height()*image.getHeight()))*.96f;
        zoom=Math.max(minimumZoom(),Math.min(6,s/fit()));s=fit()*zoom;
        panX=(.5f-target.centerX())*image.getWidth()*s;panY=(.5f-target.centerY())*image.getHeight()*s;
        clamp();float endZoom=zoom,endX=panX,endY=panY;
        if(animate&&android.animation.ValueAnimator.areAnimatorsEnabled()){focusedRegion=previous;zoom=oldZoom;panX=oldX;panY=oldY;animator=android.animation.ValueAnimator.ofFloat(0,1);animator.setDuration(240);animator.setInterpolator(new android.view.animation.AccelerateDecelerateInterpolator());animator.addUpdateListener(a->{float f=(float)a.getAnimatedValue();zoom=oldZoom+(endZoom-oldZoom)*f;panX=oldX+(endX-oldX)*f;panY=oldY+(endY-oldY)*f;focusedRegion.set(previous.left+(target.left-previous.left)*f,previous.top+(target.top-previous.top)*f,previous.right+(target.right-previous.right)*f,previous.bottom+(target.bottom-previous.bottom)*f);invalidate();});animator.start();}else invalidate();
    }
    void overview(RectF region){overviewRegion=new RectF(region);fitToScreen();}
    void clearOverview(){overviewRegion=null;invalidate();}
    void setImage(Bitmap b){stopAnimation();overviewRegion=null;focusedRegion=null;tileGeneration++;clearTiles();translationRegions=java.util.Collections.emptyList();image=b;controlsBaseFit=0;clamp();invalidate();}
    void setTranslations(java.util.List<ComicTranslation.Region> rows,boolean overlay){translationRegions=rows==null?java.util.Collections.emptyList():rows;translationCompare=getContext().getSharedPreferences("comic_translation_prefs",0).getInt("view",0)==2;translationOverlay=overlay||translationCompare;prepareTiles();invalidate();}
    private void clearTiles(){for(TranslationTile tile:translationTiles)tile.result.bitmap.recycle();translationTiles=java.util.Collections.emptyList();}
    private void prepareTiles(){
        final int ticket=++tileGeneration;clearTiles();
        if(image==null||!translationOverlay||translationRegions.isEmpty())return;
        final java.util.List<Bitmap> crops=new java.util.ArrayList<>();
        final java.util.List<Rect> cropBounds=new java.util.ArrayList<>(),textBounds=new java.util.ArrayList<>();
        final java.util.List<Integer> indices=new java.util.ArrayList<>();
        final int imageHeight=image.getHeight();
        int remainingPixels=1000000;
        for(int i=0;i<translationRegions.size()&&indices.size()<24;i++){
            ComicTranslation.Region row=translationRegions.get(i);if(row.translated==null||row.translated.isEmpty())continue;
            int l=Math.max(0,(int)(row.box.left*image.getWidth())),t=Math.max(0,(int)(row.box.top*image.getHeight()));
            int r=Math.min(image.getWidth(),(int)Math.ceil(row.box.right*image.getWidth())),b=Math.min(image.getHeight(),(int)Math.ceil(row.box.bottom*image.getHeight()));
            Rect crop=new Rect(Math.max(0,l-10),Math.max(0,t-10),Math.min(image.getWidth(),r+10),Math.min(image.getHeight(),b+10));
            int pixels=crop.width()*crop.height();
            if(crop.width()<12||crop.height()<8||pixels>250000||pixels>remainingPixels)continue;
            remainingPixels-=pixels;
            crops.add(crop.width()==image.getWidth()&&crop.height()==image.getHeight()
                    ?image.copy(Bitmap.Config.ARGB_8888,false)
                    :Bitmap.createBitmap(image,crop.left,crop.top,crop.width(),crop.height()));
            cropBounds.add(crop);textBounds.add(new Rect(l-crop.left,t-crop.top,r-crop.left,b-crop.top));indices.add(i);
        }
        tileWorker.execute(()->{
            java.util.List<TranslationTile> finished=new java.util.ArrayList<>();
            java.util.Map<Integer,Float> glyphs=new java.util.HashMap<>();
            for(int i=0;i<crops.size();i++){
                Bitmap crop=crops.get(i);try{glyphs.put(indices.get(i),ComicTextReconstruction.glyphHeight(crop,textBounds.get(i))/imageHeight);ComicTextReconstruction.Result result=ComicTextReconstruction.rebuild(crop,textBounds.get(i));if(result!=null)finished.add(new TranslationTile(indices.get(i),cropBounds.get(i).left,cropBounds.get(i).top,result));}
                finally{crop.recycle();}
            }
            tileHandler.post(()->{if(ticket!=tileGeneration){for(TranslationTile tile:finished)tile.result.bitmap.recycle();return;}for(java.util.Map.Entry<Integer,Float> entry:glyphs.entrySet())if(entry.getKey()<translationRegions.size())translationRegions.get(entry.getKey()).inkHeightRatio=entry.getValue();translationTiles=finished;invalidate();});
        });
    }
    void setTheme(String theme){
        ColorMatrix matrix=new ColorMatrix();
        if("sepia".equals(theme))matrix.set(new float[]{.393f,.769f,.189f,0,0,.349f,.686f,.168f,0,0,.272f,.534f,.131f,0,0,0,0,0,1,0});
        else if("mono".equals(theme))matrix.setSaturation(0);
        else if("dark".equals(theme))matrix.setScale(.78f,.78f,.82f,1);
        else {paint.setColorFilter(null);invalidate();return;}
        paint.setColorFilter(new ColorMatrixColorFilter(matrix));invalidate();
    }
    void restore(float z,float x,float y){zoom=Math.max(1,Math.min(6,z));panX=x*getWidth();panY=y*getHeight();clamp();invalidate();}
    void changePage(float z,float x,float y,boolean keepZoom,boolean keepPosition,boolean autoFit,String mode){
        stopAnimation();focusedRegion=null;
        zoom=keepZoom?Math.max(1,Math.min(6,z)):(autoFit?1:Math.max(1,Math.min(6,1/fit())));
        if(keepPosition){float ratio=z>0?zoom/z:1;panX=x*getWidth()*ratio;panY=y*getHeight()*ratio;}
        else {float s=fit()*zoom;panX=("manga".equals(mode)?-1:1)*Math.max(0,(image.getWidth()*s-getWidth())/2);panY=Math.max(0,(image.getHeight()*s-getHeight())/2);}
        clamp();invalidate();
    }
    void fitToScreen(){stopAnimation();focusedRegion=null;zoom=1;panX=panY=0;clamp();invalidate();}
    void zoomBy(float factor){stopAnimation();overviewRegion=null;float old=zoom;zoom=Math.max(minimumZoom(),Math.min(6,zoom*factor));panX*=zoom/old;panY*=zoom/old;clamp();invalidate();}
    float guidedFitZoom(RectF region){
        if(image==null||getWidth()==0||getHeight()==0||region==null||region.width()<=0||region.height()<=0)return 1;
        float scale=Math.min(getWidth()/(region.width()*image.getWidth()),getHeight()/(region.height()*image.getHeight()))*.96f;
        return Math.max(minimumZoom(),Math.min(6,scale/fit()));
    }
    float centerPageX(){return image==null||getWidth()==0?.5f:.5f-panX/(image.getWidth()*renderScale());}
    float centerPageY(){return image==null||getHeight()==0?.5f:.5f-panY/(image.getHeight()*renderScale());}
    void restoreGuidedView(float relativeZoom,float centerX,float centerY){
        if(image==null||!Float.isFinite(relativeZoom)||!Float.isFinite(centerX)||!Float.isFinite(centerY))return;
        zoom=Math.max(minimumZoom(),Math.min(6,zoom*Math.max(.1f,relativeZoom)));
        panX=(.5f-centerX)*image.getWidth()*renderScale();
        panY=(.5f-centerY)*image.getHeight()*renderScale();
        clamp();invalidate();
    }
    private float minimumZoom(){return focusedRegion==null?1:.1f;}
    float normalizedX(){return getWidth()==0?0:panX/getWidth();}float normalizedY(){return getHeight()==0?0:panY/getHeight();}
    void setControlsPresentation(float progress,float freed){controlsProgress=Math.max(0,Math.min(1,progress));controlsFreed=Math.max(0,freed);if(controlsProgress<=.001f&&image!=null&&getWidth()>0&&getHeight()>0)controlsBaseFit=fit();invalidate();}
    private float fit(){return image==null?1:Math.min((float)getWidth()/image.getWidth(),(float)getHeight()/image.getHeight());}
    float renderScale(){return fit()*zoom;}
    private void clamp(){if(image==null)return;float s=fit()*zoom;RectF area=focusedRegion==null?new RectF(0,0,1,1):focusedRegion;float x=(.5f-area.centerX())*image.getWidth()*s,y=(.5f-area.centerY())*image.getHeight()*s;float mx=Math.max(0,(area.width()*image.getWidth()*s-getWidth())/2),my=Math.max(0,(area.height()*image.getHeight()*s-getHeight())/2);panX=Math.max(x-mx,Math.min(x+mx,panX));panY=Math.max(y-my,Math.min(y+my,panY));}
    @Override protected void onSizeChanged(int w,int h,int oldw,int oldh){if(oldw>0)panX*=w/(float)oldw;if(oldh>0)panY*=h/(float)oldh;clamp();}
    @Override protected void onDraw(Canvas c){
        super.onDraw(c);if(image==null)return;
        c.save();
        float liveFit=fit();
        if(controlsProgress<=.001f||controlsBaseFit<=0)controlsBaseFit=liveFit;
        boolean panelFocused=focusedRegion!=null;
        float base=(!panelFocused&&controlsProgress>.001f?controlsBaseFit:liveFit)*zoom;
        float targetPresentation=!panelFocused&&zoom<=1.001f?1f+.14f*controlsProgress:1f;
        float s=base*targetPresentation;
        if(!panelFocused&&zoom<=1.001f&&controlsProgress>0)s=Math.min(s,getWidth()*.98f/image.getWidth());
        float actualPresentation=base==0?1:s/base,contentHeight=image.getHeight()*base;
        float controlsOffset=panelFocused?0:-controlsFreed/2f+contentHeight*(actualPresentation-1f)/2f;
        float centerY=getHeight()/2f+panY+controlsOffset;
        c.translate(getWidth()/2f+panX,centerY);c.scale(s,s);
        if(panelFocused)c.clipRect((focusedRegion.left-.5f)*image.getWidth(),(focusedRegion.top-.5f)*image.getHeight(),
                                  (focusedRegion.right-.5f)*image.getWidth(),(focusedRegion.bottom-.5f)*image.getHeight());
        c.drawBitmap(image,-image.getWidth()/2f,-image.getHeight()/2f,paint);
        if(translationOverlay)drawTranslations(c,s);
        c.restore();
        if(overviewRegion!=null){
            float left=getWidth()/2f+panX-image.getWidth()*s/2,top=centerY-image.getHeight()*s/2;
            Paint border=new Paint(Paint.ANTI_ALIAS_FLAG);border.setColor(Ui.RED);border.setStyle(Paint.Style.STROKE);
            RectF selected=new RectF(left+overviewRegion.left*image.getWidth()*s,top+overviewRegion.top*image.getHeight()*s,
                                    left+overviewRegion.right*image.getWidth()*s,top+overviewRegion.bottom*image.getHeight()*s);
            for(int glow=3;glow>=1;glow--){border.setStrokeWidth(Ui.dp(getContext(),3+glow*3));border.setAlpha(18+(3-glow)*12);c.drawRect(selected,border);}
            border.setAlpha(255);border.setStrokeWidth(Ui.dp(getContext(),2));c.drawRect(selected,border);
        }
    }
    private void drawTranslations(Canvas c,float scale){
        float imageLeft=-image.getWidth()/2f,imageTop=-image.getHeight()/2f;
        Paint bitmapPaint=new Paint(Paint.FILTER_BITMAP_FLAG);
        for(int index=0;index<translationRegions.size();index++){
            ComicTranslation.Region region=translationRegions.get(index);
            if(region.translated==null||region.translated.isEmpty())continue;
            TranslationTile tile=null;
            for(TranslationTile candidate:translationTiles)if(candidate.index==index){tile=candidate;break;}
            boolean label=translationCompare||tile==null;
            String shown=translationCompare?region.original+" / "+region.translated:region.translated;
            TextPaint text=new TextPaint(Paint.ANTI_ALIAS_FLAG);text.setColor(label?Color.WHITE:tile.result.lightBackground?0xff201c20:Color.WHITE);
            boolean latin=true;for(int i=0;i<shown.length();i++)if(shown.charAt(i)>0x024f){latin=false;break;}text.setTypeface(latin?comicFont:Typeface.DEFAULT);
            float left=imageLeft+region.box.left*image.getWidth(),top=imageTop+region.box.top*image.getHeight();
            float boxWidth=Math.max(1,region.box.width()*image.getWidth()),boxHeight=Math.max(1,region.box.height()*image.getHeight());
            float textAngle=label?0:Math.abs(region.angle)>8?region.angle:boxHeight>boxWidth*1.3f?-90:0;
            boolean vertical=Math.abs(textAngle)>60;
            float widthStart=vertical?top:left,widthEnd=widthStart+(vertical?boxHeight:boxWidth);
            float widthPageStart=vertical?imageTop:imageLeft;
            float widthPageEnd=widthPageStart+(vertical?image.getHeight():image.getWidth());
            float widthCenter=(widthStart+widthEnd)/2;
            float availableWidth=Math.min((widthEnd-widthStart)*1.65f,2*Math.min(widthCenter-widthPageStart,widthPageEnd-widthCenter));
            for(int otherIndex=0;otherIndex<translationRegions.size();otherIndex++){
                if(otherIndex==index)continue;
                RectF other=translationRegions.get(otherIndex).box;
                float otherStart=(vertical?other.top*image.getHeight():other.left*image.getWidth())+widthPageStart;
                float otherEnd=(vertical?other.bottom*image.getHeight():other.right*image.getWidth())+widthPageStart;
                float otherCrossStart=(vertical?other.left*image.getWidth():other.top*image.getHeight())+(vertical?imageLeft:imageTop);
                float otherCrossEnd=(vertical?other.right*image.getWidth():other.bottom*image.getHeight())+(vertical?imageLeft:imageTop);
                float cross0=vertical?left:top,cross1=cross0+(vertical?boxWidth:boxHeight);
                if(otherCrossEnd<=cross0||otherCrossStart>=cross1)continue;
                if(otherEnd<=widthStart)availableWidth=Math.min(availableWidth,widthEnd-widthStart+2*(widthStart-otherEnd));
                else if(otherStart>=widthEnd)availableWidth=Math.min(availableWidth,widthEnd-widthStart+2*(otherStart-widthEnd));
            }
            int textWidth=Math.max(1,Math.round(availableWidth));
            float axisStart=vertical?left:top,axisEnd=axisStart+(vertical?boxWidth:boxHeight);
            float crossStart=vertical?top:left,crossEnd=crossStart+(vertical?boxHeight:boxWidth);
            float pageStart=vertical?imageLeft:imageTop,pageEnd=pageStart+(vertical?image.getWidth():image.getHeight());
            float available=Math.min((axisEnd-axisStart)*2.4f,2*Math.min((axisStart+axisEnd)/2-pageStart,pageEnd-(axisStart+axisEnd)/2));
            for(int otherIndex=0;otherIndex<translationRegions.size();otherIndex++){
                if(otherIndex==index)continue;
                RectF other=translationRegions.get(otherIndex).box;
                float otherStart=(vertical?other.left*image.getWidth():other.top*image.getHeight())+pageStart;
                float otherEnd=(vertical?other.right*image.getWidth():other.bottom*image.getHeight())+pageStart;
                float otherCrossStart=(vertical?other.top*image.getHeight():other.left*image.getWidth())+(vertical?imageTop:imageLeft);
                float otherCrossEnd=(vertical?other.bottom*image.getHeight():other.right*image.getWidth())+(vertical?imageTop:imageLeft);
                if(otherCrossEnd<=crossStart||otherCrossStart>=crossEnd)continue;
                if(otherEnd<=axisStart)available=Math.min(available,axisEnd-axisStart+2*(axisStart-otherEnd));
                else if(otherStart>=axisEnd)available=Math.min(available,axisEnd-axisStart+2*(otherStart-axisEnd));
            }
            int availableHeight=Math.max(1,Math.round(available));
            if(label){textWidth=Math.max(textWidth,(int)(Ui.dp(getContext(),180)/scale));availableHeight=Math.max(availableHeight,(int)(Ui.dp(getContext(),90)/scale));}
            StaticLayout layout=null;boolean fits=false;
            float inkHeight=region.inkHeightRatio>0?region.inkHeightRatio*image.getHeight():0;
            float originalInk=Math.max(inkHeight,boxHeight*1.08f);
            text.setTextSize(40);Rect reference=new Rect();text.getTextBounds(shown,0,shown.length(),reference);
            int originalSize=Math.max(8,Math.min(150,Math.round(40*originalInk/Math.max(1,reference.height()))));
            int smallest=label?Math.max(8,(int)(Ui.dp(getContext(),12)/scale)):8;
            int largest=label?Math.max(smallest,(int)(Ui.dp(getContext(),16)/scale)):Math.max(smallest,originalSize);
            CharSequence content=label?shown:styledTranslation(shown,region.wordScales);
            for(int size=largest;size>=smallest;size--){
                text.setTextSize(size);
                for(float spacing:new float[]{0f,-.02f,-.04f}){
                    text.setLetterSpacing(spacing);
                    layout=StaticLayout.Builder.obtain(content,0,content.length(),text,textWidth)
                            .setAlignment(Layout.Alignment.ALIGN_CENTER).setIncludePad(false).setLineSpacing(0,1.02f).build();
                    if(layout.getHeight()<=availableHeight){fits=true;break;}
                }
                if(fits)break;
            }
            if(!fits){label=true;text.setColor(Color.WHITE);textWidth=Math.min(image.getWidth()-8,Math.max(textWidth,(int)(Ui.dp(getContext(),180)/scale)));text.setTextSize(Math.max(8,(int)(Ui.dp(getContext(),14)/scale)));text.setLetterSpacing(0);layout=StaticLayout.Builder.obtain(shown,0,shown.length(),text,textWidth).setAlignment(Layout.Alignment.ALIGN_CENTER).setIncludePad(false).build();
                if(layout.getHeight()>image.getHeight()-8){shown=I18n.t(getContext(),"Ver tradução completa em Revisar");layout=StaticLayout.Builder.obtain(shown,0,shown.length(),text,textWidth).setAlignment(Layout.Alignment.ALIGN_CENTER).setIncludePad(false).build();}
            }
            if(!label)c.drawBitmap(tile.result.bitmap,imageLeft+tile.left,imageTop+tile.top,bitmapPaint);
            c.save();
            if(label){float labelLeft=Math.max(imageLeft+4,Math.min(left,imageLeft+image.getWidth()-textWidth-4));float labelTop=Math.max(imageTop+4,Math.min(top+boxHeight,imageTop+image.getHeight()-layout.getHeight()-6));Paint background=new Paint(Paint.ANTI_ALIAS_FLAG);background.setColor(0xdd201c20);c.drawRoundRect(new RectF(labelLeft,labelTop,labelLeft+textWidth,labelTop+layout.getHeight()+4),4,4,background);c.translate(labelLeft,labelTop+2);}
            else if(textAngle!=0){c.translate(left+boxWidth/2,top+boxHeight/2);c.rotate(textAngle);c.translate(-textWidth/2f,-layout.getHeight()/2f);}
            else c.translate(left+(boxWidth-textWidth)/2,top+(boxHeight-layout.getHeight())/2);
            layout.draw(c);c.restore();
        }
    }
    @Override public boolean performClick(){super.performClick();return true;}
    @Override public boolean onTouchEvent(MotionEvent e){if(overviewRegion==null)scale.onTouchEvent(e);gestures.onTouchEvent(e);
        if(e.getActionMasked()==MotionEvent.ACTION_DOWN){stopAnimation();downX=lastX=e.getX();downY=lastY=e.getY();pinching=false;moved=false;}
        if(e.getPointerCount()>1)pinching=true;
        if(e.getActionMasked()==MotionEvent.ACTION_MOVE&&e.getPointerCount()==1&&!scale.isInProgress()){float dx=e.getX()-downX,dy=e.getY()-downY;if(Math.hypot(dx,dy)>=touchSlop)moved=true;if(zoom>1){panX+=e.getX()-lastX;panY+=e.getY()-lastY;clamp();invalidate();}lastX=e.getX();lastY=e.getY();}
        if(e.getActionMasked()==MotionEvent.ACTION_UP&&!pinching&&zoom<=1.01&&moved){float dx=e.getX()-downX,dy=e.getY()-downY;if(Math.abs(dx)>Ui.dp(getContext(),65)&&Math.abs(dx)>Math.abs(dy)*1.5){if(dx<0)actions.next();else actions.previous();}}
        if(e.getActionMasked()==MotionEvent.ACTION_CANCEL){pinching=false;moved=true;}
        return true;
    }
}

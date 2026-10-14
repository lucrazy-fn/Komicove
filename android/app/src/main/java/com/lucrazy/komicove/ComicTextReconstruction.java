package com.lucrazy.komicove;

import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Rect;
import java.util.ArrayDeque;
import java.util.Arrays;

final class ComicTextReconstruction {
    static final class Result {
        final Bitmap bitmap;
        final boolean lightBackground;
        Result(Bitmap bitmap, boolean lightBackground) { this.bitmap=bitmap; this.lightBackground=lightBackground; }
    }

    private static float light(int color) {
        return (Color.red(color)+Color.green(color)+Color.blue(color))/3f;
    }

    static float glyphHeight(Bitmap image, Rect bounds) {
        Rect area=new Rect(Math.max(0,bounds.left),Math.max(0,bounds.top),
                Math.min(image.getWidth(),bounds.right),Math.min(image.getHeight(),bounds.bottom));
        int step=Math.max(1,Math.max(area.width(),area.height())/450);
        int width=area.width()/step,height=area.height()/step;
        if(width<3||height<3||width*height>250000)return Math.max(6,area.height()*.75f);
        int[] lightness=new int[width*height],histogram=new int[256];
        for(int y=0;y<height;y++)for(int x=0;x<width;x++){
            int value=Math.round(light(image.getPixel(area.left+x*step,area.top+y*step)));
            lightness[y*width+x]=value;histogram[value]++;
        }
        int half=lightness.length/2,background=0;
        for(int n=0;n<histogram.length;n++){half-=histogram[n];if(half<=0){background=n;break;}}
        boolean[] ink=new boolean[lightness.length],seen=new boolean[lightness.length];
        for(int n=0;n<ink.length;n++)ink[n]=background>=128?lightness[n]<background-42:lightness[n]>background+42;
        float[] heights=new float[lightness.length/3+1];int count=0;
        for(int start=0;start<ink.length;start++){
            if(!ink[start]||seen[start])continue;
            ArrayDeque<Integer> queue=new ArrayDeque<>();queue.add(start);seen[start]=true;
            int left=start%width,right=left,top=start/width,bottom=top,pixels=0;
            while(!queue.isEmpty()){
                int index=queue.removeFirst(),x=index%width,y=index/width;pixels++;
                left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
                int[] neighbors={x>0?index-1:-1,x+1<width?index+1:-1,y>0?index-width:-1,y+1<height?index+width:-1};
                for(int neighbor:neighbors)if(neighbor>=0&&ink[neighbor]&&!seen[neighbor]){seen[neighbor]=true;queue.add(neighbor);}
            }
            int componentHeight=bottom-top+1;
            if(componentHeight>=3&&componentHeight<=height*.9f&&right-left+1<=width*.42f&&pixels>=4&&count<heights.length)
                heights[count++]=componentHeight*step;
        }
        if(count==0)return Math.max(6,area.height()*.75f);
        Arrays.sort(heights,0,count);
        return heights[Math.round((count-1)*.9f)];
    }

    static Result rebuild(Bitmap crop, Rect text) {
        int width=crop.getWidth(), height=crop.getHeight();
        if(width*height>250000||text.width()<12||text.height()<8)return null;
        Rect area=new Rect(Math.max(1,text.left-5),Math.max(1,text.top-5),
                Math.min(width-1,text.right+5),Math.min(height-1,text.bottom+5));
        int[] source=new int[width*height];crop.getPixels(source,0,width,0,0,width,height);
        float[] edge=new float[width*height/4+1];int edgeCount=0;
        for(int y=0;y<height;y+=2)for(int x=0;x<width;x+=2)
            if(!area.contains(x,y))edge[edgeCount++]=light(source[y*width+x]);
        if(edgeCount<8)return null;
        Arrays.sort(edge,0,edgeCount);float background=edge[edgeCount/2];
        float[] deviation=new float[edgeCount];for(int i=0;i<edgeCount;i++)deviation[i]=Math.abs(edge[i]-background);
        Arrays.sort(deviation);if(deviation[edgeCount/2]>22)return null;
        boolean smooth=deviation[edgeCount/2]<8;
        long red=0,green=0,blue=0;int colorCount=0;
        if(smooth)for(int y=0;y<height;y+=2)for(int x=0;x<width;x+=2){
            if(area.contains(x,y))continue;
            int color=source[y*width+x];if(Math.abs(light(color)-background)>10)continue;
            red+=Color.red(color);green+=Color.green(color);blue+=Color.blue(color);colorCount++;
        }
        int backgroundColor=colorCount==0?Color.rgb(Math.round(background),Math.round(background),Math.round(background))
                :Color.rgb((int)(red/colorCount),(int)(green/colorCount),(int)(blue/colorCount));
        boolean darkText=background>=120;
        boolean[] mask=new boolean[source.length];int count=0;
        for(int y=area.top;y<area.bottom;y++)for(int x=area.left;x<area.right;x++){
            float difference=light(source[y*width+x])-background;
            float threshold=smooth?12:24;
            if(darkText?difference< -threshold:difference>threshold){mask[y*width+x]=true;count++;}
        }
        if(count<2||count>area.width()*area.height()*.45f)return null;
        boolean[] grown=mask.clone();
        for(int y=Math.max(4,area.top);y<Math.min(height-4,area.bottom);y++)
            for(int x=Math.max(4,area.left);x<Math.min(width-4,area.right);x++)
                if(mask[y*width+x])for(int dy=-4;dy<=4;dy++)for(int dx=-4;dx<=4;dx++)grown[(y+dy)*width+x+dx]=true;
        int[] output=source.clone();
        for(int y=0;y<height;y++)for(int x=0;x<width;x++){
            if(!grown[y*width+x])continue;
            if(smooth){output[y*width+x]=backgroundColor;continue;}
            float best=darkText?-1:256;int chosen=source[y*width+x];
            for(int dy=-4;dy<=4;dy++)for(int dx=-4;dx<=4;dx++){
                int xx=x+dx,yy=y+dy;if(xx<0||yy<0||xx>=width||yy>=height)continue;
                int candidate=source[yy*width+xx];float value=light(candidate);
                if(darkText?value>best:value<best){best=value;chosen=candidate;}
            }
            output[y*width+x]=chosen;
        }
        Bitmap result=Bitmap.createBitmap(output,width,height,Bitmap.Config.ARGB_8888);
        return new Result(result,darkText);
    }
}

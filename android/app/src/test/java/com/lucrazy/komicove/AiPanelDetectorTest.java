package com.lucrazy.komicove;

import android.graphics.RectF;
import java.util.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35)
public class AiPanelDetectorTest {
    private static PanelDetector.Result baseline(){return new PanelDetector.Result(Collections.singletonList(new RectF(0,0,1,1)),true,.3f,"whole_page");}
    @Test public void decodeDeduplicatesAndRejectsInvalid()throws Exception{
        float[][] rows={{160,160,Float.NaN},{160,160,160},{300,300,50},{300,300,50},{.9f,.8f,.95f}};
        List<AiPanelDetector.Detection> kept=AiPanelDetector.decode(rows,0,0,640,640);
        assertEquals(1,kept.size());assertEquals(.9f,kept.get(0).score,.001f);
    }
    @Test public void letterboxAndTinyNoise()throws Exception{
        float[][] rows={{320,320},{320,320},{200,1},{200,1},{.8f,.8f}};
        List<AiPanelDetector.Detection> kept=AiPanelDetector.decode(rows,160,0,320,640);
        assertEquals(1,kept.size());assertEquals(.1875f,kept.get(0).rect.left,.001f);assertEquals(.65625f,kept.get(0).rect.bottom,.001f);
    }
    @Test public void partialHeaderIsExplicitlyApproximate(){
        List<AiPanelDetector.Detection> boxes=Collections.singletonList(new AiPanelDetector.Detection(.9f,new RectF(.02f,0,.98f,.16f)));
        PanelDetector.Result result=AiPanelDetector.combine(boxes,baseline(),false,false);
        assertTrue(result.fallback);assertEquals("ai_partial",result.method);assertEquals(2,result.regions().size());assertTrue(result.confidence<.5f);
    }
    @Test public void noBoxesAndIsolatedSmallBoxUseWholePage(){
        PanelDetector.Result empty=AiPanelDetector.combine(Collections.emptyList(),baseline(),false,false);
        assertTrue(empty.fallback);assertEquals(new RectF(0,0,1,1),empty.regions().get(0));
        assertTrue(AiPanelDetector.combine(Collections.singletonList(new AiPanelDetector.Detection(.9f,new RectF(.1f,.2f,.4f,.5f))),baseline(),false,false).fallback);
    }
    @Test public void coherentMangaOrderAndStrongHeuristic(){
        RectF left=new RectF(0,0,.5f,.5f),right=new RectF(.5f,0,1,.5f);
        List<AiPanelDetector.Detection> boxes=Arrays.asList(new AiPanelDetector.Detection(.8f,left),new AiPanelDetector.Detection(.9f,right));
        assertEquals(right,AiPanelDetector.combine(boxes,baseline(),true,false).regions().get(0));
        assertEquals(left,AiPanelDetector.combine(boxes,baseline(),false,false).regions().get(0));
        PanelDetector.Result strong=new PanelDetector.Result(Arrays.asList(left,right),false,.94f,"gutters");
        assertSame(strong,AiPanelDetector.combine(Collections.emptyList(),strong,false,false));
    }
    @Test public void malformedRowsAreRejected()throws Exception{
        try{AiPanelDetector.decode(new float[][]{{1}},0,0,640,640);fail();}catch(java.io.IOException expected){}
    }
}

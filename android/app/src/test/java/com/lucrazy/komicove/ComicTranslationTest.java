package com.lucrazy.komicove;

import android.content.Context;
import android.app.Activity;
import android.app.Dialog;
import android.view.View;
import android.view.ViewGroup;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.RectF;
import android.text.Spanned;
import android.text.style.RelativeSizeSpan;
import java.util.ArrayList;
import java.util.List;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.Robolectric;
import org.robolectric.annotation.Config;
import org.json.JSONObject;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Protocol;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.ResponseBody;
import java.net.SocketTimeoutException;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class ComicTranslationTest {
    @Test public void readableDialogueIsTranslatedButShortNoiseIsNot(){
        ComicTranslation.Region dialogue=new ComicTranslation.Region(new RectF(.1f,.1f,.4f,.2f),"RUN! THIS WAY!",.72f);
        ComicTranslation.Region effect=new ComicTranslation.Region(new RectF(.1f,.2f,.4f,.3f),"KRAKOOM",.80f);
        ComicTranslation.Region noise=new ComicTranslation.Region(new RectF(.1f,.3f,.2f,.4f),"AX",.89f);
        assertTrue(ComicTranslation.autoTranslationCandidate(dialogue));
        assertTrue(ComicTranslation.autoTranslationCandidate(effect));
        assertFalse(ComicTranslation.autoTranslationCandidate(noise));
    }
    private View named(View root,String name){
        if(name.equals(root.getContentDescription()))return root;
        if(root instanceof ViewGroup){ViewGroup group=(ViewGroup)root;for(int i=0;i<group.getChildCount();i++){View found=named(group.getChildAt(i),name);if(found!=null)return found;}}
        return null;
    }

    @Test public void translationOpensDedicatedScreenAndBackKeepsReader() throws Exception {
        Activity activity=Robolectric.buildActivity(Activity.class).setup().get();
        activity.getSharedPreferences("comic_translation_prefs",0).edit().putString("provider","local").putString("source","auto").apply();
        ComicTranslationDialog screen=new ComicTranslationDialog(activity,new ComicTranslationDialog.Host(){
            public int page(){return 0;}public int count(){return 1;}public boolean manga(){return false;}
            public String bookKey(){return "authorial-ui-fixture";}public RectF panel(){return null;}
            public Bitmap bitmap(int page){return Bitmap.createBitmap(100,100,Bitmap.Config.ARGB_8888);}
            public void show(int page,List<ComicTranslation.Region> rows,String mode){}
        });
        screen.show();
        java.lang.reflect.Field field=ComicTranslationDialog.class.getDeclaredField("dialog");field.setAccessible(true);
        Dialog window=(Dialog)field.get(screen);
        assertTrue(window.isShowing());
        ViewGroup content=window.findViewById(android.R.id.content);
        ViewGroup layout=(ViewGroup)content.getChildAt(0);
        assertEquals(ViewGroup.LayoutParams.WRAP_CONTENT,layout.getChildAt(0).getLayoutParams().height);
        assertEquals(ViewGroup.LayoutParams.WRAP_CONTENT,layout.getChildAt(2).getLayoutParams().height);
        java.lang.reflect.Field local=ComicTranslationDialog.class.getDeclaredField("remoteAdvanced");local.setAccessible(true);
        assertEquals(View.GONE,((View)local.get(screen)).getVisibility());
        java.lang.reflect.Field source=ComicTranslationDialog.class.getDeclaredField("source");source.setAccessible(true);
        assertEquals("auto",((android.widget.EditText)source.get(screen)).getText().toString());
        View back=named(window.getWindow().getDecorView(),"Voltar à leitura");
        assertNotNull(back);
        back.performClick();
        assertFalse(window.isShowing());
        assertFalse(activity.isFinishing());
    }
    @Test public void originalGlyphSizeAndWordEmphasisArePreserved() {
        Bitmap small=Bitmap.createBitmap(360,110,Bitmap.Config.ARGB_8888);
        Bitmap large=Bitmap.createBitmap(360,110,Bitmap.Config.ARGB_8888);
        for(Bitmap page:new Bitmap[]{small,large})page.eraseColor(Color.WHITE);
        for(int letter=0;letter<5;letter++)for(int x=0;x<6;x++){
            for(int y=0;y<20;y++)small.setPixel(15+letter*22+x,35+y,Color.BLACK);
            for(int y=0;y<60;y++)large.setPixel(15+letter*22+x,25+y,Color.BLACK);
        }
        float smallHeight=ComicTextReconstruction.glyphHeight(small,new Rect(0,0,360,105));
        float largeHeight=ComicTextReconstruction.glyphHeight(large,new Rect(0,0,360,105));
        assertTrue("small="+smallHeight+" large="+largeHeight,largeHeight>smallHeight*1.5f);
        CharSequence styled=ZoomPage.styledTranslation("vá AGORA!",new float[]{.65f,1.55f});
        RelativeSizeSpan[] spans=((Spanned)styled).getSpans(0,styled.length(),RelativeSizeSpan.class);
        assertEquals(1,spans.length);
        assertTrue(spans[0].getSizeChange()<.5f);
    }
    private OkHttpClient response(int code,String body,AtomicReference<Request> request){
        return new OkHttpClient.Builder().addInterceptor(chain->{request.set(chain.request());return new Response.Builder()
                .request(chain.request()).protocol(Protocol.HTTP_1_1).code(code).message("mock")
                .body(ResponseBody.create(body,MediaType.get("application/json"))).build();}).build();
    }

    @Test public void providersUseDocumentedPathsAndHeadersWithoutNetwork() throws Exception {
        AtomicReference<Request> sent=new AtomicReference<>();JSONObject payload=new JSONObject().put("model","chosen");
        assertEquals("ok",ComicTranslation.request("openai","chosen","dummy","",payload,
                response(200,"{\"choices\":[{\"message\":{\"content\":\"ok\"}}]}",sent)));
        assertEquals("https://api.openai.com/v1/chat/completions",sent.get().url().toString());
        assertEquals("Bearer dummy",sent.get().header("Authorization"));
        assertEquals("ok",ComicTranslation.request("xai","chosen","dummy","https://example.invalid/v2",payload,
                response(200,"{\"choices\":[{\"message\":{\"content\":\"ok\"}}]}",sent)));
        assertEquals("https://example.invalid/v2/chat/completions",sent.get().url().toString());
        assertEquals("ok",ComicTranslation.request("anthropic","chosen","dummy","",payload,
                response(200,"{\"content\":[{\"type\":\"text\",\"text\":\"ok\"}]}",sent)));
        assertEquals("https://api.anthropic.com/v1/messages",sent.get().url().toString());
        assertEquals("dummy",sent.get().header("x-api-key"));
        assertEquals("2023-06-01",sent.get().header("anthropic-version"));
        assertEquals("ok",ComicTranslation.request("groq","openai/gpt-oss-20b","dummy","",payload,
                response(200,"{\"choices\":[{\"message\":{\"content\":\"ok\"}}]}",sent)));
        assertEquals("https://api.groq.com/openai/v1/chat/completions",sent.get().url().toString());
        assertEquals("ok",ComicTranslation.request("openrouter","openrouter/auto","dummy","",payload,
                response(200,"{\"choices\":[{\"message\":{\"content\":\"ok\"}}]}",sent)));
        assertEquals("https://openrouter.ai/api/v1/chat/completions",sent.get().url().toString());
        assertEquals("ok",ComicTranslation.request("gemini","gemini-3.8-flash","dummy","",payload,
                response(200,"{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"ok\"}]}}]}",sent)));
        assertEquals("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",sent.get().url().toString());
        assertEquals("dummy",sent.get().header("x-goog-api-key"));
        assertNull(sent.get().header("Authorization"));
    }

    @Test public void providerErrorsAreClassifiedWithoutNetwork() throws Exception {
        AtomicReference<Request> sent=new AtomicReference<>();
        for(int[] item:new int[][]{{401,1},{429,2},{400,3}}){
            try{ComicTranslation.request("openai","chosen","dummy","",new JSONObject(),response(item[0],"{}",sent));fail("Expected provider error");}
            catch(ComicTranslation.Failure error){assertEquals(item[1]==1?"authentication":item[1]==2?"quota_or_rate_limit":"model_or_request_incompatible",error.code);}
        }
        OkHttpClient timeout=new OkHttpClient.Builder().addInterceptor(chain->{throw new SocketTimeoutException("mock");}).build();
        try{ComicTranslation.request("xai","chosen","dummy","",new JSONObject(),timeout);fail("Expected timeout");}
        catch(ComicTranslation.Failure error){assertEquals("timeout",error.code);}
    }

    @Test public void uncertainOcrDoesNotStartRemoteRequest() throws Exception {
        ComicTranslation.Region row=new ComicTranslation.Region(new RectF(.1f,.1f,.4f,.2f),"P@R?",.3f);
        List<ComicTranslation.Region> rows=new ArrayList<>();rows.add(row);
        ComicTranslation.translateRemote(rows,rows,"en","pt","openai","chosen","unused","","{}");
        assertFalse(row.translationAttempted);
        assertEquals("",row.translated);
    }

    @Test public void visionPayloadRequiresImageAndSupportedModel() throws Exception {
        JSONObject input=new JSONObject().put("balloons",new org.json.JSONArray().put("Hello"));
        for(String provider:new String[]{"openai","anthropic","xai","gemini"}){
            String model=provider.equals("openai")?"gpt-5.4-mini":provider.equals("anthropic")?"claude-sonnet-5-5":provider.equals("xai")?"grok-4.7":"gemini-3.8-flash";
            assertTrue(ComicTranslation.supportsVision(provider,model));
            assertFalse(ComicTranslation.translationBody(provider,model,"Translate",input,null).toString().contains("base64"));
            assertTrue(ComicTranslation.translationBody(provider,model,"Translate",input,"fixture-image").toString().contains("fixture-image"));
        }
        assertFalse(ComicTranslation.supportsVision("groq","openai/gpt-oss-20b"));
    }

    @Test public void providerRejectsMissingCredentialsAndUnsafeEndpoint() throws Exception {
        try {
            ComicTranslation.request("openai","", "", "",new JSONObject());
            fail("Missing model and key must be rejected");
        } catch (ComicTranslation.Failure expected) {
            assertEquals("key_or_model_missing",expected.code);
        }
        try {
            ComicTranslation.request("openai","chosen","test-key","http://example.invalid/v1",new JSONObject());
            fail("Remote endpoint must use HTTPS");
        } catch (ComicTranslation.Failure expected) {
            assertEquals("invalid_endpoint",expected.code);
        }
    }

    @Test public void cacheInvalidatesOnlyChangedConfigAndCorrectionsSurvive() throws Exception {
        Context context=RuntimeEnvironment.getApplication();
        Bitmap image=Bitmap.createBitmap(100,100,Bitmap.Config.ARGB_8888);
        List<ComicTranslation.Region> rows=new ArrayList<>();
        ComicTranslation.Region region=new ComicTranslation.Region(new RectF(.1f,.1f,.4f,.2f),"unclear",.4f);
        region.translated="wrong";rows.add(region);
        region.translationAttempted=true;
        region.inkHeightRatio=.025f;region.wordScales=new float[]{.6f,1.4f};
        ComicTranslation.writeOcr(context,"fixture",1,image,"latin",false,rows);
        assertEquals("unclear",ComicTranslation.readOcr(context,"fixture",1,image,"latin",false).get(0).original);
        assertEquals(.025f,ComicTranslation.readOcr(context,"fixture",1,image,"latin",false).get(0).inkHeightRatio,.0001f);
        assertEquals(1.4f,ComicTranslation.readOcr(context,"fixture",1,image,"latin",false).get(0).wordScales[1],.0001f);
        assertNull(ComicTranslation.readOcr(context,"fixture",1,image,"ja",false));
        assertNull(ComicTranslation.readOcr(context,"fixture",1,image,"latin",true));
        ComicTranslation.write(context,"fixture",1,image,"auto","pt","openai","model-a","","{}","latin",false,rows);
        assertEquals("wrong",ComicTranslation.read(context,"fixture",1,image,"auto","pt","openai","model-a","","{}","latin",false).get(0).translated);
        assertTrue(ComicTranslation.read(context,"fixture",1,image,"auto","pt","openai","model-a","","{}","latin",false).get(0).translationAttempted);
        assertNull(ComicTranslation.read(context,"fixture",1,image,"auto","en","openai","model-a","","{}","latin",false));
        assertNull(ComicTranslation.read(context,"fixture",1,image,"auto","pt","openai","model-b","","{}","latin",false));
        assertNull(ComicTranslation.read(context,"fixture",1,image,"auto","pt","openai","model-a","","{}","ja",false));
        region.original="clear";region.manualOriginal=true;region.translated="certo";region.manualTranslation=true;
        ComicTranslation.saveCorrection(context,"fixture",1,region);
        ComicTranslation.Region corrected=ComicTranslation.read(context,"fixture",1,image,"auto","pt","openai","model-a","","{}","latin",false).get(0);
        assertEquals("clear",corrected.original);
        assertEquals("certo",corrected.translated);
        ComicTranslation.clearCache(context);
        assertNull(ComicTranslation.read(context,"fixture",1,image,"auto","pt","openai","model-a","","{}","latin",false));
        List<ComicTranslation.Region> rerun=new ArrayList<>();
        rerun.add(new ComicTranslation.Region(new RectF(.1f,.1f,.4f,.2f),"unclear",.4f));
        ComicTranslation.correct(context,"fixture",1,rerun);
        assertEquals("clear",rerun.get(0).original);
        assertEquals("certo",rerun.get(0).translated);
        image.recycle();
    }

    @Test public void emptyAndRepeatedCorrectionsDoNotInvalidateCache() throws Exception {
        Context context=RuntimeEnvironment.getApplication();
        String book="empty-correction-fixture";
        Bitmap image=Bitmap.createBitmap(40,40,Bitmap.Config.ARGB_8888);
        ComicTranslation.Region row=new ComicTranslation.Region(new RectF(.1f,.1f,.4f,.2f),"STOP!",.8f);
        row.translated="Pare!";
        List<ComicTranslation.Region> rows=new ArrayList<>();rows.add(row);
        ComicTranslation.write(context,book,0,image,"en","pt","openai","chosen","","{}","latin",false,rows);
        ComicTranslation.saveCorrection(context,book,0,row);
        assertNotNull(ComicTranslation.read(context,book,0,image,"en","pt","openai","chosen","","{}","latin",false));
        java.lang.reflect.Method path=ComicTranslation.class.getDeclaredMethod("corrections",Context.class,String.class,int.class);
        path.setAccessible(true);
        java.io.File legacy=(java.io.File)path.invoke(null,context,book,0);
        java.nio.file.Files.write(legacy.toPath(),new JSONObject().put(row.id(),new JSONObject()).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        assertNotNull(ComicTranslation.read(context,book,0,image,"en","pt","openai","chosen","","{}","latin",false));
        row.manualTranslation=true;
        ComicTranslation.saveCorrection(context,book,0,row);
        ComicTranslation.write(context,book,0,image,"en","pt","openai","chosen","","{}","latin",false,rows);
        ComicTranslation.saveCorrection(context,book,0,row);
        assertNotNull(ComicTranslation.read(context,book,0,image,"en","pt","openai","chosen","","{}","latin",false));
        image.recycle();
    }

    @Test public void previousPageCorrectionsInvalidateRemoteCacheOnly() throws Exception {
        Context context=RuntimeEnvironment.getApplication();
        String book="authorial-context-fixture";
        Bitmap image=Bitmap.createBitmap(32,32,Bitmap.Config.ARGB_8888);
        image.eraseColor(Color.WHITE);
        List<ComicTranslation.Region> current=new ArrayList<>();
        current.add(new ComicTranslation.Region(new RectF(.1f,.1f,.5f,.2f),"He returned",.9f));
        ComicTranslation.write(context,book,1,image,"en","pt","openai","chosen","","{}","latin",false,current);
        assertNotNull(ComicTranslation.read(context,book,1,image,"en","pt","openai","chosen","","{}","latin",false));
        List<ComicTranslation.Region> earlier=new ArrayList<>();
        ComicTranslation.Region first=new ComicTranslation.Region(new RectF(.1f,.1f,.4f,.2f),"The captain left",.9f);
        earlier.add(first);
        ComicTranslation.writeOcr(context,book,0,image,"latin",false,earlier);
        assertEquals("The captain left",ComicTranslation.previousPageContext(context,book,1).get(0));
        assertNull(ComicTranslation.read(context,book,1,image,"en","pt","openai","chosen","","{}","latin",false));
        ComicTranslation.write(context,book,1,image,"en","pt","openai","chosen","","{}","latin",false,current);
        first.original="The captain returned";first.manualOriginal=true;
        ComicTranslation.saveCorrection(context,book,0,first);
        assertEquals("The captain returned",ComicTranslation.previousPageContext(context,book,1).get(0));
        assertNull(ComicTranslation.read(context,book,1,image,"en","pt","openai","chosen","","{}","latin",false));
        ComicTranslation.write(context,book,1,image,"en","pt","local","","","{}","latin",false,current);
        assertNotNull(ComicTranslation.read(context,book,1,image,"en","pt","local","","","{}","latin",false));
        image.recycle();
    }

    @Test public void localGlossaryMatchesOnlyCompleteExpression() throws Exception {
        JSONObject glossary=new JSONObject().put("Captain Nova","Capitã Nova");
        assertEquals("Capitã Nova",ComicTranslation.exactGlossary(" captain   NOVA ",glossary));
        assertNull(ComicTranslation.exactGlossary("Captain Nova returned",glossary));
    }

    @Test public void reconstructionChangesLetterPixelsButKeepsOriginalAndArtwork() {
        Bitmap source=Bitmap.createBitmap(80,50,Bitmap.Config.ARGB_8888);
        source.eraseColor(Color.WHITE);
        for(int y=18;y<31;y++)for(int x=25;x<29;x++)source.setPixel(x,y,Color.BLACK);
        for(int y=0;y<50;y++)source.setPixel(70,y,Color.BLACK);
        ComicTextReconstruction.Result result=ComicTextReconstruction.rebuild(source,new Rect(12,12,55,38));
        assertNotNull(result);
        assertEquals(Color.BLACK,source.getPixel(26,20));
        assertEquals(Color.WHITE,result.bitmap.getPixel(26,20));
        assertEquals(Color.BLACK,result.bitmap.getPixel(70,20));
        result.bitmap.recycle();source.recycle();
    }
}

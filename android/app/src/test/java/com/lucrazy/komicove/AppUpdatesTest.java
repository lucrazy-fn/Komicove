package com.lucrazy.komicove;

import android.app.Dialog;
import android.content.*;
import android.widget.*;
import org.json.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import java.util.*;
import okhttp3.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35)
public class AppUpdatesTest {
    private void field(Object object,String name,Object value)throws Exception {java.lang.reflect.Field field=object.getClass().getDeclaredField(name);field.setAccessible(true);field.set(object,value);}
    private void http(PanelApi api,Interceptor interceptor)throws Exception {field(api,"client",new OkHttpClient.Builder().addInterceptor(interceptor).build());}
    private Response response(Request request,int code,String json){return new Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(code).message("Fixture").body(ResponseBody.create(json,MediaType.get("application/json"))).build();}
    private JSONObject release(String version,String repository)throws Exception{return new JSONObject().put("tag_name",version).put("name","Fixture release").put("body","Fixture notes").put("html_url","https://github.com/"+repository+"/releases/tag/"+version);}
    @Test public void sharedVersionContractAndLegacySeries()throws Exception{
        String text=new String(getClass().getResourceAsStream("/update_versions.json").readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);JSONObject contract=new JSONObject(text);
        JSONArray pairs=contract.getJSONArray("ordered_pairs");for(int i=0;i<pairs.length();i++)assertTrue(AppUpdates.newer(pairs.getJSONArray(i).getString(1),pairs.getJSONArray(i).getString(0)));
        pairs=contract.getJSONArray("equal_versions");for(int i=0;i<pairs.length();i++){assertFalse(AppUpdates.newer(pairs.getJSONArray(i).getString(1),pairs.getJSONArray(i).getString(0)));assertFalse(AppUpdates.newer(pairs.getJSONArray(i).getString(0),pairs.getJSONArray(i).getString(1)));}
        assertEquals("0.2.4",AppUpdates.androidVersion("0.2.3",contract.getString("notes")));
        assertNull(AppUpdates.release(release("1.4.99",AppUpdates.REPOSITORIES[0]),AppUpdates.REPOSITORIES[0],"0.2.1"));
        assertEquals("0.2.2",AppUpdates.release(release("0.2.2",AppUpdates.REPOSITORIES[0]).put("name",""),AppUpdates.REPOSITORIES[0],"0.2.1").getString("title"));
    }
    @Test public void repositoriesAreMergedAndPanelDownloadOverridesMatchingRelease()throws Exception{
        JSONObject panel=AppUpdates.announcement(new JSONObject().put("id","notice").put("title","Fixture message").put("version","0.2.2").put("notes","Fixture changelog").put("download_url",AppUpdates.SITE));
        JSONArray rows=AppUpdates.merge(Arrays.asList(AppUpdates.release(release("v0.2.2",AppUpdates.REPOSITORIES[0]),AppUpdates.REPOSITORIES[0],"0.2.1"),AppUpdates.release(release("0.2.2",AppUpdates.REPOSITORIES[1]),AppUpdates.REPOSITORIES[1],"0.2.1"),panel),"0.2.1");
        assertEquals(1,rows.length());assertEquals(AppUpdates.SITE,rows.getJSONObject(0).getString("url"));
        assertEquals("Fixture message",AppUpdates.automatic(rows,"0.2.1",Collections.emptySet()).getString("title"));
        assertNull(AppUpdates.automatic(rows,"0.2.2",Collections.singleton("notice")));
        assertNotNull(AppUpdates.automatic(rows,"0.2.2",Collections.emptySet()));
    }
    @Test public void linksStayOnOfficialDestinationsAndMessagesAreTranslated(){
        assertEquals("",AppUpdates.safeUrl("javascript:alert(1)"));assertEquals("",AppUpdates.safeUrl("https://github.com/attacker/releases"));
        assertEquals("",AppUpdates.safeUrl("https://github.com/lucrazy-fn/Komicove/releases/../issues"));
        assertEquals("",AppUpdates.safeUrl("https://github.com/lucrazy-fn/Komicove/releases/%2e%2e/issues"));
        assertEquals(AppUpdates.SITE,AppUpdates.safeUrl(AppUpdates.SITE));
        Context context=RuntimeEnvironment.getApplication();I18n.language(context,"en");assertEquals("Contributor",I18n.t(context,"Contribuidor"));assertEquals("Redeem Contributor token",I18n.t(context,"Resgatar token de Contribuidor"));assertEquals("Update message",I18n.t(context,"Mensagem de atualização"));
    }
    @Test public void dialogShowsOriginalChangelogAndDownloadOpensConfiguredSite()throws Exception{
        Context context=RuntimeEnvironment.getApplication();context.getSharedPreferences("auth_state",0).edit().putString("mode","guest").commit();I18n.language(context,"en");
        try(ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class).setup().visible()){
            MainActivity activity=controller.get();JSONObject item=new JSONObject().put("id","fixture").put("source","panel").put("title","Original title").put("version","0.2.2").put("notes_html","<h2>Conteúdo original</h2><p>Notas do autor</p>").put("created_at","2026-10-06T10:00:00Z").put("url",AppUpdates.SITE);
            java.lang.reflect.Method method=MainActivity.class.getDeclaredMethod("showUpdate",JSONObject.class);method.setAccessible(true);method.invoke(activity,item);
            android.app.AlertDialog dialog=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();
            assertTrue(dialog.isShowing());assertEquals("Download",dialog.getButton(Dialog.BUTTON_POSITIVE).getText().toString());
            dialog.getButton(Dialog.BUTTON_POSITIVE).performClick();org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle();assertEquals(AppUpdates.SITE,org.robolectric.Shadows.shadowOf(activity).getNextStartedActivity().getDataString());
            assertTrue(context.getSharedPreferences("updates",0).getStringSet("seen_messages",Collections.emptySet()).contains("fixture"));
        }
    }
    @Test public void apiReadsBothRepositoriesWithoutSendingSessionToGithub()throws Exception{
        PanelApi api=new PanelApi(RuntimeEnvironment.getApplication());field(api,"token","fixture-session");List<String> paths=new ArrayList<>();
        http(api,chain->{Request request=chain.request();paths.add(request.url().encodedPath());
            if(request.url().host().equals("api.github.com")){assertNull(request.header("Authorization"));return response(request,200,"{\"tag_name\":\"v0.2.2\",\"name\":\"Fixture\",\"body\":\"Notes\"}");}
            assertEquals("Bearer fixture-session",request.header("Authorization"));return response(request,200,"[{\"id\":\"fixture\",\"version\":\"0.2.2\",\"title\":\"Panel message\",\"notes\":\"Panel notes\",\"download_url\":\""+AppUpdates.SITE+"\"}]");
        });
        JSONArray rows=api.updates();assertEquals(1,rows.length());assertEquals("Panel message",rows.getJSONObject(0).getString("title"));
        assertEquals(Arrays.asList("/repos/lucrazy-fn/PANEL-ComicBookReader/releases/latest","/repos/lucrazy-fn/Komicove/releases/latest","/updates"),paths);
        http(api,chain->{Request request=chain.request();if(request.url().encodedPath().contains("/Komicove/"))return response(request,200,"{\"tag_name\":\"0.2.3\"}");return response(request,503,"{}");});
        assertEquals("0.2.3",api.updates().getJSONObject(0).getString("version"));assertTrue(api.signedIn());
    }
    @Test public void redeemControlPostsTokenAndPersistsContributorWithoutLosingSession()throws Exception{
        Context context=RuntimeEnvironment.getApplication();context.getSharedPreferences("auth_state",0).edit().putString("mode","guest").commit();I18n.language(context,"en");
        try(ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class).setup().visible()){
            MainActivity activity=controller.get();PanelApi api=new PanelApi(activity);field(api,"token","fixture-session");api.user=new JSONObject().put("username","fixture").put("role","user");
            java.util.concurrent.CountDownLatch posted=new java.util.concurrent.CountDownLatch(1);
            http(api,chain->{Request request=chain.request();assertEquals("/account/contributor-token",request.url().encodedPath());assertEquals("POST",request.method());okio.Buffer buffer=new okio.Buffer();request.body().writeTo(buffer);assertTrue(buffer.readUtf8().contains("fixture-contributor-token"));posted.countDown();return response(request,200,"{\"username\":\"fixture\",\"display_name\":\"Fixture\",\"role\":\"contributor\",\"is_moderator\":false}");});field(activity,"api",api);
            java.lang.reflect.Method method=MainActivity.class.getDeclaredMethod("redeemContributor");method.setAccessible(true);method.invoke(activity);
            android.app.AlertDialog dialog=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();EditText input=findInput(dialog.getWindow().getDecorView());assertNotNull(input);input.setText("fixture-contributor-token");dialog.getButton(Dialog.BUTTON_POSITIVE).performClick();Shadows.shadowOf(android.os.Looper.getMainLooper()).idle();assertTrue(posted.await(3,java.util.concurrent.TimeUnit.SECONDS));
            long end=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(3);while(!api.user.optString("role").equals("contributor")&&System.nanoTime()<end){Shadows.shadowOf(android.os.Looper.getMainLooper()).idle();Thread.sleep(10);}Shadows.shadowOf(android.os.Looper.getMainLooper()).idle();
            assertEquals("contributor",api.user.optString("role"));assertTrue(api.signedIn());assertFalse(api.moderator());assertEquals("contributor",new JSONObject(context.getSharedPreferences("api",0).getString("user","{}")).getString("role"));
        }
    }
    private EditText findInput(android.view.View view){if(view instanceof EditText)return (EditText)view;if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++){EditText found=findInput(group.getChildAt(i));if(found!=null)return found;}}return null;}
}

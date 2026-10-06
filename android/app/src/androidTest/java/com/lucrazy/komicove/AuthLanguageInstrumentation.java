package com.lucrazy.komicove;

import android.app.*;
import android.content.*;
import android.graphics.*;
import android.os.Bundle;
import android.view.*;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.*;
import java.io.*;
import java.lang.reflect.Method;

/** Tests production views with isolated preferences, never the personal installation. */
public final class AuthLanguageInstrumentation extends Instrumentation {
    private Activity active;
    private boolean reopenOnly;
    private final StringBuilder log=new StringBuilder();
    @Override public void onCreate(Bundle args){super.onCreate(args);reopenOnly=args!=null&&"true".equals(args.getString("reopenOnly"));start();}
    @Override public void onStart(){Bundle result=new Bundle();int code=Activity.RESULT_OK;
        try{
            require(getTargetContext().getPackageName().equals("com.lucrazy.panel.phase4test"),"Use the isolated -Pphase4Test=true build");
            if(reopenOnly){open(AuthActivity.class);require(hasText(root(),"EN")&&hasText(root(),"Sign in"),"English preference did not survive process restart");shot("auth-phone-restarted-en");close();log.append("PASS English language after force-stop/process restart\n");}
            else for(boolean light:new boolean[]{false,true}){
                getTargetContext().getSharedPreferences("ui",0).edit().putBoolean("light",light).commit();
                I18n.language(getTargetContext(),"pt");open(AuthActivity.class);View root=root();
                require(hasText(root,"Entrar")&&hasText(root,"Entrar como convidado"),"Portuguese login missing");
                shot("auth-phone-pt-"+(light?"light":"dark"));
                EditText user=input(root,"Usuário ou e-mail"),password=input(root,"Senha"),factor=input(root,"Código 2FA ou de recuperação");
                runOnMainSync(()->{user.setText("fixture_reader");password.setText("fixture123");password.setSelection(4);factor.setText("123456");factor.setVisibility(View.VISIBLE);});
                choose("en");require(hasText(root,"Sign in")&&hasText(root,"Continue as guest")&&hasText(root,"Don't have an account? "),"English login incomplete");
                require(user==input(root,"Username or email")&&password==input(root,"Password")&&factor==input(root,"2FA or recovery code"),"Language change rebuilt fields");
                require(user.getText().toString().equals("fixture_reader")&&password.getText().toString().equals("fixture123")&&password.getSelectionEnd()==4,"Typed values/selection lost");
                require(factor.getVisibility()==View.VISIBLE&&factor.getText().toString().equals("123456"),"2FA state lost");
                close();open(AuthActivity.class);root=root();require(hasText(root,"EN")&&hasText(root,"Sign in"),"English preference did not survive reopening");
                shot("auth-phone-en-"+(light?"light":"dark"));
                click("Create account");root=root();require(hasText(root,"Already have an account? "),"Registration prefix untranslated");
                EditText confirm=input(root,"Confirm password");runOnMainSync(()->confirm.setText("fixture123"));
                choose("pt");require(confirm==input(root,"Confirmar senha")&&confirm.getText().toString().equals("fixture123"),"Registration input lost");
                require(hasText(root,"Já tenho uma conta? "),"Portuguese registration missing");choose("en");
                require(input(root,"Username")!=null&&input(root,"Display name")!=null&&input(root,"Email")!=null,"English registration hints missing");
                shot("register-phone-en-"+(light?"light":"dark"));click("Sign in");
                click("Forgot my password");expectAccessible("Recover password");expectAccessible("Send code");clickAccessible("Cancel");waitForIdleSync();
                runOnMainSync(()->invoke("confirmRecovery"));waitForIdleSync();expectAccessible("Create a new password");expectAccessible("Save");clickAccessible("Cancel");waitForIdleSync();
                click("Continue as guest");waitForIdleSync();require(getTargetContext().getSharedPreferences("auth_state",0).getString("mode","").equals("guest"),"Guest action failed");close();
                open(MainActivity.class);root=root();require(hasText(root,"Library")&&hasText(root,"Favorites"),"English library incomplete");
                runOnMainSync(()->invoke("settings"));waitForIdleSync();root=root();require(hasText(root,"Settings")&&hasText(root,"App language")&&hasText(root,"Restore"),"English settings incomplete");
                final Dialog[] preferences={null};runOnMainSync(()->preferences[0]=ReaderPreferences.show(active,null));waitForIdleSync();
                View reader=preferences[0].getWindow().getDecorView();require(hasText(reader,"Reading theme")&&hasText(reader,"Default")&&hasText(reader,"Sepia")&&hasText(reader,"B&W")&&hasText(reader,"Keep position"),"English reader preferences incomplete");
                runOnMainSync(preferences[0]::dismiss);close();log.append("PASS ").append(light?"light":"dark").append(": login PT/EN, fields/2FA, reopen, registration, recovery, guest, library/settings/reader preferences\n");
            }
            result.putString("stream",log.toString());
        }catch(Throwable e){StringWriter trace=new StringWriter();e.printStackTrace(new PrintWriter(trace));code=Activity.RESULT_CANCELED;result.putString("stream",log+"FAIL "+trace);}
        finally{close();}finish(code,result);
    }
    private void open(Class<? extends Activity> type){active=startActivitySync(new Intent(getTargetContext(),type).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));waitForIdleSync();}
    private View root(){return active.getWindow().getDecorView();}
    private void close(){if(active!=null){Activity previous=active;runOnMainSync(previous::finish);waitForIdleSync();active=null;}}
    private TextView find(View v,String value,boolean hint){if(v instanceof TextView){TextView t=(TextView)v;CharSequence text=hint?t.getHint():t.getText();if(text!=null&&value.contentEquals(text))return t;}if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++){TextView t=find(((ViewGroup)v).getChildAt(i),value,hint);if(t!=null)return t;}return null;}
    private boolean hasText(View v,String value){return find(v,value,false)!=null;}
    private EditText input(View v,String value){TextView t=find(v,value,true);require(t instanceof EditText,"Missing input: "+value);return (EditText)t;}
    private void click(String text){runOnMainSync(()->{TextView v=find(root(),text,false);require(v!=null,"Missing action: "+text);v.performClick();});waitForIdleSync();}
    private void choose(String lang)throws Exception{click(I18n.language(active).equals("en")?"EN":"PT");clickAccessible(lang.equals("en")?"English":I18n.language(active).equals("en")?"Portuguese (Brazil)":"Português (Brasil)");waitForIdleSync();require(I18n.language(active).equals(lang),"Language picker failed");}
    private AccessibilityNodeInfo accessible(String text){AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();if(root==null)return null;java.util.List<AccessibilityNodeInfo> found=root.findAccessibilityNodeInfosByText(text);for(AccessibilityNodeInfo node:found)if(node.getText()!=null&&text.equalsIgnoreCase(node.getText().toString()))return node;return null;}
    private void expectAccessible(String text)throws Exception{long end=System.currentTimeMillis()+5000;do{if(accessible(text)!=null)return;Thread.sleep(50);}while(System.currentTimeMillis()<end);throw new AssertionError("Missing visible dialog text: "+text+". Keep phone unlocked.");}
    private void clickAccessible(String text)throws Exception{expectAccessible(text);AccessibilityNodeInfo node=accessible(text);while(node!=null&&!node.isClickable())node=node.getParent();require(node!=null&&node.performAction(AccessibilityNodeInfo.ACTION_CLICK),"Could not tap: "+text);waitForIdleSync();}
    private void invoke(String method){try{Method m=active.getClass().getDeclaredMethod(method);m.setAccessible(true);m.invoke(active);}catch(Exception e){throw new RuntimeException(e);}}
    private void shot(String name)throws Exception{final Bitmap[] image={null};runOnMainSync(()->{View v=root();require(v.getWidth()>0&&v.getHeight()>0,"No phone layout");image[0]=Bitmap.createBitmap(v.getWidth(),v.getHeight(),Bitmap.Config.ARGB_8888);v.draw(new Canvas(image[0]));});try(FileOutputStream out=new FileOutputStream(new File(getTargetContext().getCacheDir(),name+".png"))){image[0].compress(Bitmap.CompressFormat.PNG,100,out);}finally{image[0].recycle();}}
    private static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
}

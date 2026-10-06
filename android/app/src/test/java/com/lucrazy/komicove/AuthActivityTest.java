package com.lucrazy.komicove;

import android.app.AlertDialog;
import android.view.*;
import android.widget.*;
import java.lang.reflect.Method;
import java.util.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.shadows.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35,qualifiers="w360dp-h800dp-xhdpi")
@org.robolectric.annotation.GraphicsMode(org.robolectric.annotation.GraphicsMode.Mode.NATIVE)
public class AuthActivityTest {
    private ActivityController<AuthActivity> controller;
    private AuthActivity activity;
    @Before public void open(){I18n.language(RuntimeEnvironment.getApplication(),"pt");reopen();}
    @After public void close(){if(controller!=null)controller.pause().stop().destroy();}
    private void reopen(){controller=Robolectric.buildActivity(AuthActivity.class).setup().visible();activity=controller.get();}
    private View root(){return activity.getWindow().getDecorView();}
    private List<TextView> texts(View view){List<TextView> found=new ArrayList<>();if(view instanceof TextView)found.add((TextView)view);if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++)found.addAll(texts(((ViewGroup)view).getChildAt(i)));return found;}
    private TextView text(String value){for(TextView view:texts(root()))if(value.equals(view.getText().toString()))return view;throw new AssertionError("Missing label: "+value);}
    private EditText input(String value){for(TextView view:texts(root()))if(view instanceof EditText&&value.contentEquals(view.getHint()))return (EditText)view;throw new AssertionError("Missing field: "+value);}
    private void choose(String language){
        text("en".equals(I18n.language(activity))?"EN":"PT").performClick();
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();int which=language.equals("en")?1:0;
        dialog.getListView().performItemClick(null,which,which);
        assertEquals(language,I18n.language(activity));assertFalse(dialog.isShowing());
    }
    private void call(String name)throws Exception{Method m=AuthActivity.class.getDeclaredMethod(name);m.setAccessible(true);m.invoke(activity);}
    private void toast(String message)throws Exception{Method m=AuthActivity.class.getDeclaredMethod("toast",String.class);m.setAccessible(true);m.invoke(activity,message);}
    @Test public void languageSwitchPreservesFieldsFocusAndSecondFactorAndPersists(){
        EditText user=input("Usuário ou e-mail"),password=input("Senha"),code=input("Código 2FA ou de recuperação");
        user.setText("comic_reader");password.setText("secret123");password.requestFocus();password.setSelection(4);code.setVisibility(View.VISIBLE);code.setText("123456");
        choose("en");assertSame(user,input("Username or email"));assertEquals("comic_reader",user.getText().toString());
        assertSame(password,input("Password"));assertEquals("secret123",password.getText().toString());assertEquals(4,password.getSelectionEnd());
        assertTrue(password.hasFocus());
        assertSame(code,input("2FA or recovery code"));assertEquals(View.VISIBLE,code.getVisibility());assertEquals("123456",code.getText().toString());
        text("Sign in");text("Continue as guest");text("Don't have an account? ");text("Sign in to your account and keep exploring amazing stories.");
        choose("pt");text("Entrar");assertSame(password,input("Senha"));choose("en");
        controller.pause().stop().destroy();reopen();text("EN");text("Sign in");input("Username or email");
    }
    @Test public void registrationChangesAllLabelsAndPreservesTypedValues(){
        text("Criar conta").performClick();EditText user=input("Nome de usuário"),name=input("Nome de exibição"),email=input("E-mail"),confirm=input("Confirmar senha");
        user.setText("reader");name.setText("Reader");email.setText("reader@example.com");confirm.setText("secret123");
        choose("en");assertSame(user,input("Username"));assertSame(name,input("Display name"));assertSame(email,input("Email"));assertSame(confirm,input("Confirm password"));
        assertEquals("reader",user.getText().toString());assertEquals("secret123",confirm.getText().toString());
        text("Join the community and discover a universe of amazing stories.");text("Already have an account? ");text("Sign in").performClick();input("Username or email");
    }
    @Test public void recoveryDialogsUseChosenLanguage()throws Exception{
        for(String lang:new String[]{"pt","en"}){
            choose(lang);call("recover");AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();
            assertEquals(lang.equals("pt")?"Recuperar senha":"Recover password",Shadows.shadowOf(dialog).getTitle().toString());
            assertEquals(lang.equals("pt")?"Enviar código":"Send code",dialog.getButton(AlertDialog.BUTTON_POSITIVE).getText().toString());dialog.dismiss();
            call("confirmRecovery");dialog=ShadowAlertDialog.getLatestAlertDialog();
            assertEquals(lang.equals("pt")?"Criar nova senha":"Create a new password",Shadows.shadowOf(dialog).getTitle().toString());
            List<String> hints=new ArrayList<>();for(TextView v:texts(dialog.getWindow().getDecorView()))if(v instanceof EditText)hints.add(v.getHint().toString());
            assertEquals(Arrays.asList(lang.equals("pt")?"Código recebido":"Received code",lang.equals("pt")?"Nova senha":"New password"),hints);dialog.dismiss();
        }
    }
    @Test public void validationAndBilingualServerErrorsAreLocalized()throws Exception{
        choose("en");for(TextView v:texts(root()))if(v instanceof Button&&v.getText().toString().equals("Sign in"))v.performClick();
        assertEquals("Enter your username and password.",ShadowToast.getTextOfLatestToast());
        toast("As senhas não coincidem.");assertEquals("Passwords do not match.",ShadowToast.getTextOfLatestToast());
        toast("Código inválido ou expirado. / Invalid or expired code.");assertEquals("Invalid or expired code.",ShadowToast.getTextOfLatestToast());
        choose("pt");toast("Código inválido ou expirado. / Invalid or expired code.");assertEquals("Código inválido ou expirado.",ShadowToast.getTextOfLatestToast());
    }
    @Test public void guestStillFinishesWithExistingMode(){choose("en");text("Continue as guest").performClick();assertTrue(activity.isFinishing());assertEquals("guest",activity.getSharedPreferences("auth_state",0).getString("mode",""));}
    @Test public void smallLayoutsKeepLanguageButtonUsableInBothThemes()throws Exception{
        for(boolean light:new boolean[]{false,true})for(String lang:new String[]{"pt","en"}){
            activity.getSharedPreferences("ui",0).edit().putBoolean("light",light).commit();Ui.configure(activity);choose(lang);
            for(boolean register:new boolean[]{false,true}){
                if(register)text(lang.equals("en")?"Create account":"Criar conta").performClick();
                View view=root();view.measure(View.MeasureSpec.makeMeasureSpec(720,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(1600,View.MeasureSpec.EXACTLY));view.layout(0,0,720,1600);
                TextView selector=text(lang.equals("en")?"EN":"PT");assertTrue(selector.getHeight()>=Ui.dp(activity,48));assertTrue(selector.getWidth()>0);
                assertEquals(lang.equals("en")?"Choose language":"Escolha o idioma",selector.getContentDescription().toString());
                assertEquals(android.graphics.Color.WHITE,selector.getCurrentTextColor());
                assertEquals(android.graphics.Color.WHITE,text(lang.equals("en")?(register?"Create account":"Sign in"):(register?"Criar conta":"Entrar")).getCurrentTextColor());
                assertEquals(android.graphics.Color.WHITE,text(lang.equals("en")?"Continue as guest":"Entrar como convidado").getCurrentTextColor());
                String path=System.getenv("KOMICOVE_AUTH_QA");if(path!=null){
                    android.graphics.Bitmap image=android.graphics.Bitmap.createBitmap(720,1600,android.graphics.Bitmap.Config.ARGB_8888);view.draw(new android.graphics.Canvas(image));
                    java.io.File file=new java.io.File(path,"auth-"+lang+"-"+(light?"light":"dark")+"-"+(register?"register":"login")+".png");file.getParentFile().mkdirs();
                    try(java.io.FileOutputStream out=new java.io.FileOutputStream(file)){image.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out);}finally{image.recycle();}
                }
                if(register)text(lang.equals("en")?"Sign in":"Entrar").performClick();
            }
        }
    }
}

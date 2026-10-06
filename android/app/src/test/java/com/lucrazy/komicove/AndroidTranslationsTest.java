package com.lucrazy.komicove;

import android.app.Dialog;
import android.view.*;
import android.widget.TextView;
import java.lang.reflect.Method;
import java.util.*;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35,qualifiers="w360dp-h800dp-xhdpi")
public class AndroidTranslationsTest {
    private Set<String> labels(View view){Set<String> found=new HashSet<>();if(view instanceof TextView)found.add(((TextView)view).getText().toString());if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++)found.addAll(labels(((ViewGroup)view).getChildAt(i)));return found;}
    private void screen(MainActivity activity,String method)throws Exception{Method m=MainActivity.class.getDeclaredMethod(method);m.setAccessible(true);m.invoke(activity);}
    @Test public void libraryAndSettingsAndReaderPreferencesAreFullyEnglish()throws Exception{
        android.content.Context context=RuntimeEnvironment.getApplication();I18n.language(context,"en");context.getSharedPreferences("auth_state",0).edit().putString("mode","guest").commit();
        try(ActivityController<MainActivity> c=Robolectric.buildActivity(MainActivity.class).setup().visible()){
            MainActivity a=c.get();Set<String> library=labels(a.getWindow().getDecorView());
            assertTrue(library.contains("Library"));assertTrue(library.contains("Favorites"));assertTrue(library.contains("Your library is empty"));assertFalse(library.contains("Biblioteca"));
            screen(a,"settings");Set<String> settings=labels(a.getWindow().getDecorView());
            for(String text:new String[]{"Settings","Appearance","App language","Restore","Reading mode and preferences","Personal statistics"})assertTrue(text,settings.contains(text));
            Dialog dialog=ReaderPreferences.show(a,null);Set<String> reader=labels(dialog.getWindow().getDecorView());
            for(String text:new String[]{"Reading theme","Default","Dark","Sepia","B&W","Keep zoom level","Keep position"})assertTrue(text,reader.contains(text));
            dialog.dismiss();
        }
    }
    @Test public void newCatalogEntriesTranslateWholeMessagesAndKeepPortuguese(){
        android.content.Context c=RuntimeEnvironment.getApplication();
        String[][] pairs={
            {"Leitura guiada","Guided reading"},{"Restaurar controles","Restore controls"},{"Tela cheia","Full screen"},
            {"Use o modo de página única ou mangá para editar quadros.","Use single-page or manga mode to edit panels."},
            {"Arquivo indisponível. Confira o acesso à pasta.","File unavailable. Check folder access."},
            {"Permissão da pasta perdida. Selecione a pasta novamente.","Folder permission was lost. Select the folder again."},
            {"Use um backup Android compatível com o Komicove.","Use an Android backup compatible with Komicove."},
            {"Sua sessão expirou. Entre novamente.","Your session expired. Sign in again."},
            {"Foto atualizada no Windows e no celular.","Picture updated on Windows and on your phone."},
            {"Não foi possível abrir a imagem.","Could not open the image."},
        };
        for(String[] pair:pairs){I18n.language(c,"en");assertEquals(pair[1],I18n.t(c,pair[0]));I18n.language(c,"pt");assertEquals(pair[0],I18n.t(c,pair[0]));}
    }
    @Test public void legacyLanguagePreferenceStillWorks(){
        android.content.Context c=RuntimeEnvironment.getApplication();c.getSharedPreferences("komicove_ui",0).edit().clear().commit();c.getSharedPreferences("panel_ui",0).edit().putString("language","en").commit();
        assertEquals("Restore",I18n.t(c,"Restaurar"));I18n.language(c,"pt");assertEquals("Restaurar",I18n.t(c,"Restaurar"));
    }
}

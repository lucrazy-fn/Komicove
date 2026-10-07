package com.lucrazy.komicove;

import android.app.Dialog;
import android.content.*;
import android.graphics.Bitmap;
import android.os.Looper;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.zip.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=35,qualifiers="w360dp-h800dp-xhdpi")
public class ReaderBrightnessTest {
    private LibraryStore store;
    private LibraryStore.Book book;
    private SharedPreferences prefs;

    @Before public void setup()throws Exception {
        Context context=RuntimeEnvironment.getApplication();store=new LibraryStore(context);
        prefs=context.getSharedPreferences("reader",0);
        prefs.edit().clear().putInt("brightness",30).putBoolean("persist_zoom",false)
            .putBoolean("persist_position",true).putBoolean("auto_fit",false)
            .putBoolean("animate_guided",false).putString("theme","sepia").putInt("unknown",42).commit();
        Bitmap image=Bitmap.createBitmap(100,160,Bitmap.Config.ARGB_8888);
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        try(ZipOutputStream zip=new ZipOutputStream(bytes)) {
            zip.putNextEntry(new ZipEntry("1.png"));image.compress(Bitmap.CompressFormat.PNG,100,zip);zip.closeEntry();
        } finally { image.recycle(); }
        book=store.importStream(new ByteArrayInputStream(bytes.toByteArray()),"brightness.cbz");
    }

    @After public void cleanup(){if(book!=null)store.remove(book);}
    private ActivityController<ReaderActivity> open(){return Robolectric.buildActivity(ReaderActivity.class,new Intent(store.context,ReaderActivity.class).putExtra("book",book.id)).setup().visible();}
    private <T extends View> T find(View view,Class<T> type,String text) {
        if(type.isInstance(view)&&(text==null||view instanceof TextView&&text.equals(((TextView)view).getText().toString())))return type.cast(view);
        if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){T result=find(((ViewGroup)view).getChildAt(i),type,text);if(result!=null)return result;}
        return null;
    }
    private void brightness(ReaderActivity activity,float expected){assertEquals(expected,activity.getWindow().getAttributes().screenBrightness,0.001f);}

    @Test public void legacyDefaultClampsAndSystemModeRestoresOnRecreation() {
        try(ActivityController<ReaderActivity> controller=open()) {
            ReaderActivity activity=controller.get();brightness(activity,.3f);
            prefs.edit().putInt("brightness",0).commit();ReaderPreferences.applyBrightness(activity,prefs);brightness(activity,.1f);
            prefs.edit().putInt("brightness",150).commit();ReaderPreferences.applyBrightness(activity,prefs);brightness(activity,1f);
            prefs.edit().putString("brightness_mode","system").putInt("brightness",30).commit();
            ReaderPreferences.applyBrightness(activity,prefs);brightness(activity,WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE);
            controller.recreate();brightness(controller.get(),WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE);
            prefs.edit().putString("brightness_mode","preferences").commit();ReaderPreferences.applyBrightness(controller.get(),prefs);brightness(controller.get(),.3f);
        }
    }

    @Test public void preferencesPreviewCancelSaveAndReopenInBothLanguages() {
        for(String language:new String[]{"pt","en"}) {
            I18n.language(store.context,language);
            prefs.edit().remove("brightness_mode").commit();
            try(ActivityController<ReaderActivity> controller=open()) {
                ReaderActivity activity=controller.get();Dialog dialog=ReaderPreferences.show(activity,null);
                View root=dialog.getWindow().getDecorView();
                RadioButton system=find(root,RadioButton.class,I18n.t(activity,"Usar brilho do sistema"));
                RadioButton manual=find(root,RadioButton.class,I18n.t(activity,"Usar brilho das preferências"));
                SeekBar slider=find(root,SeekBar.class,null);
                assertTrue(manual.isChecked());assertTrue(slider.isEnabled());
                system.performClick();assertTrue(system.isChecked());assertFalse(slider.isEnabled());
                brightness(activity,WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE);
                assertEquals(WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE,dialog.getWindow().getAttributes().screenBrightness,0f);
                dialog.cancel();Shadows.shadowOf(Looper.getMainLooper()).idle();brightness(activity,.3f);assertFalse(prefs.contains("brightness_mode"));
                dialog=ReaderPreferences.show(activity,null);root=dialog.getWindow().getDecorView();
                find(root,RadioButton.class,I18n.t(activity,"Usar brilho do sistema")).performClick();
                find(root,Button.class,I18n.t(activity,"Salvar preferências")).performClick();
                Shadows.shadowOf(Looper.getMainLooper()).idle();
                assertEquals("system",prefs.getString("brightness_mode",""));assertEquals(30,prefs.getInt("brightness",0));
                brightness(activity,WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE);
                controller.recreate();activity=controller.get();brightness(activity,WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE);
                dialog=ReaderPreferences.show(activity,null);root=dialog.getWindow().getDecorView();
                assertTrue(find(root,RadioButton.class,I18n.t(activity,"Usar brilho do sistema")).isChecked());
                assertFalse(find(root,SeekBar.class,null).isEnabled());
                find(root,RadioButton.class,I18n.t(activity,"Usar brilho das preferências")).performClick();brightness(activity,.3f);
                find(root,Button.class,I18n.t(activity,"Salvar preferências")).performClick();
                Shadows.shadowOf(Looper.getMainLooper()).idle();
                assertEquals("preferences",prefs.getString("brightness_mode",""));
                assertFalse(prefs.getBoolean("persist_zoom",true));assertTrue(prefs.getBoolean("persist_position",false));
                assertFalse(prefs.getBoolean("auto_fit",true));assertFalse(prefs.getBoolean("animate_guided",true));
                assertEquals("sepia",prefs.getString("theme",""));assertEquals(42,prefs.getInt("unknown",0));
            }
        }
    }
}

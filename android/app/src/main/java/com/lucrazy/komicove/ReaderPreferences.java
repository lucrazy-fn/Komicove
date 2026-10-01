package com.lucrazy.komicove;

import android.app.*;
import android.content.*;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.view.*;
import android.widget.*;

final class ReaderPreferences {
    private static final int[][] SWITCH_STATES={{android.R.attr.state_checked},{-android.R.attr.state_checked}};

    static void show(Activity activity,Runnable changed) {
        SharedPreferences prefs=activity.getSharedPreferences("reader",0);
        int savedBrightness=Math.max(10,prefs.getInt("brightness",100));
        String[] selectedTheme={prefs.getString("theme","default")};
        Dialog dialog=new Dialog(activity);dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout sheet=Ui.column(activity);sheet.setPadding(Ui.dp(activity,18),Ui.dp(activity,10),Ui.dp(activity,18),Ui.dp(activity,18));sheet.setBackground(Ui.bordered(activity,Ui.BG,Ui.BORDER,Ui.RADIUS_LARGE));

        View handle=new View(activity);handle.setBackground(Ui.shape(Ui.BORDER,Ui.dp(activity,4)));
        LinearLayout handleWrap=Ui.row(activity);handleWrap.setGravity(Gravity.CENTER);handleWrap.addView(handle,new LinearLayout.LayoutParams(Ui.dp(activity,82),Ui.dp(activity,5)));sheet.addView(handleWrap,Ui.margin(-1,Ui.dp(activity,18),activity,0,0,0,8));

        LinearLayout header=Ui.row(activity);header.addView(icon(activity,R.drawable.lucide_sliders,Ui.RED_BRIGHT),new LinearLayout.LayoutParams(Ui.dp(activity,52),Ui.dp(activity,52)));
        LinearLayout heading=Ui.column(activity);heading.addView(Ui.title(activity,"Preferências do leitor",24));heading.addView(Ui.text(activity,"Personalize sua experiência de leitura",14,Ui.MUTED));
        header.addView(heading,Ui.margin(0,-2,activity,12,0,8,0));((LinearLayout.LayoutParams)heading.getLayoutParams()).weight=1;
        ImageButton close=Ui.iconButton(activity,R.drawable.lucide_x,false,()->{previewBrightness(activity,savedBrightness);dialog.dismiss();});close.setContentDescription(I18n.t(activity,"Fechar"));header.addView(close,new LinearLayout.LayoutParams(Ui.dp(activity,48),Ui.dp(activity,48)));
        sheet.addView(header,Ui.margin(-1,-2,activity,0,0,0,16));

        sheet.addView(Ui.sectionTitle(activity,"Leitura e navegação",R.drawable.lucide_book_open),Ui.margin(-1,-2,activity,0,0,0,8));
        LinearLayout navigation=Ui.card(activity);navigation.setPadding(0,0,0,0);
        Switch persist=readerSwitch(activity,prefs.getBoolean("persist_zoom",true));navigation.addView(toggleRow(activity,R.drawable.lucide_zoom_in,"Persistir zoom e deslocamento","Mantém o nível de zoom e a posição entre páginas.",persist,false));
        Switch fit=readerSwitch(activity,prefs.getBoolean("auto_fit",true));navigation.addView(toggleRow(activity,R.drawable.lucide_focus,"Ajustar à tela automaticamente","Redimensiona cada página para o melhor enquadramento.",fit,true));
        Switch guided=readerSwitch(activity,prefs.getBoolean("guided",false));navigation.addView(toggleRow(activity,R.drawable.lucide_book_open,"Leitura guiada (experimental)","Destaca os quadros na ordem de leitura.",guided,true));
        Switch animate=readerSwitch(activity,prefs.getBoolean("animate_guided",true));navigation.addView(toggleRow(activity,R.drawable.lucide_columns,"Transições suaves entre quadros","Anima a passagem entre os quadros detectados.",animate,true));
        sheet.addView(navigation,Ui.margin(-1,-2,activity,0,0,0,16));

        sheet.addView(Ui.sectionTitle(activity,"Aparência e exibição",R.drawable.lucide_sun),Ui.margin(-1,-2,activity,0,0,0,8));
        LinearLayout appearance=Ui.card(activity);LinearLayout brightnessTitle=Ui.row(activity);brightnessTitle.addView(icon(activity,R.drawable.lucide_sun,Ui.RED_BRIGHT),new LinearLayout.LayoutParams(Ui.dp(activity,46),Ui.dp(activity,46)));
        LinearLayout brightnessText=Ui.column(activity);brightnessText.addView(Ui.title(activity,"Brilho do leitor",16));brightnessText.addView(Ui.text(activity,"Ajusta o brilho somente durante a leitura.",13,Ui.MUTED));brightnessTitle.addView(brightnessText,Ui.margin(0,-2,activity,12,0,0,0));((LinearLayout.LayoutParams)brightnessText.getLayoutParams()).weight=1;
        TextView amount=Ui.title(activity,"",14);brightnessTitle.addView(amount);appearance.addView(brightnessTitle);
        SeekBar brightness=new SeekBar(activity);brightness.setMax(100);brightness.setMin(10);brightness.setProgress(savedBrightness);amount.setText(savedBrightness+"%");brightness.setProgressTintList(ColorStateList.valueOf(Ui.RED_BRIGHT));brightness.setThumbTintList(ColorStateList.valueOf(Ui.RED_BRIGHT));brightness.setProgressBackgroundTintList(ColorStateList.valueOf(Ui.BORDER));
        brightness.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar bar){}public void onStopTrackingTouch(SeekBar bar){}public void onProgressChanged(SeekBar bar,int value,boolean fromUser){amount.setText(value+"%");if(fromUser)previewBrightness(activity,value);}});
        appearance.addView(brightness,new LinearLayout.LayoutParams(-1,Ui.dp(activity,48)));sheet.addView(appearance,Ui.margin(-1,-2,activity,0,0,0,16));

        sheet.addView(Ui.sectionTitle(activity,"Tema de leitura",R.drawable.lucide_sun),Ui.margin(-1,-2,activity,0,0,0,8));
        LinearLayout themes=Ui.row(activity);String[] themeNames={"Padrão","Escuro","Sépia","P&B"};String[] themeValues={"default","dark","sepia","mono"};Button[] themeButtons=new Button[themeNames.length];
        Runnable refreshThemes=()->{for(int i=0;i<themeButtons.length;i++){boolean active=themeValues[i].equals(selectedTheme[0]);themeButtons[i].setTextColor(active?Color.WHITE:Ui.MUTED);themeButtons[i].setBackground(active?Ui.glow(activity,Ui.SURFACE_ALT,Ui.RADIUS_MEDIUM):Ui.bordered(activity,Ui.SURFACE,Ui.BORDER,Ui.RADIUS_MEDIUM));}};
        for(int i=0;i<themeNames.length;i++){int position=i;Button theme=Ui.button(activity,themeNames[i],()->{selectedTheme[0]=themeValues[position];refreshThemes.run();});theme.setTextSize(12);themeButtons[i]=theme;themes.addView(theme,i==0?new LinearLayout.LayoutParams(0,Ui.dp(activity,48),1):Ui.margin(0,Ui.dp(activity,48),activity,7,0,0,0));if(i>0)((LinearLayout.LayoutParams)theme.getLayoutParams()).weight=1;}
        refreshThemes.run();sheet.addView(themes,Ui.margin(-1,-2,activity,0,0,0,14));

        TextView note=Ui.text(activity,"A leitura guiada funciona nos modos Página única e Mangá. Use o editor manual quando a detecção automática não reconhecer os quadros corretamente.",13,Ui.MUTED);note.setPadding(Ui.dp(activity,12),Ui.dp(activity,8),Ui.dp(activity,12),Ui.dp(activity,14));sheet.addView(note);
        Button save=Ui.primaryButton(activity,"Salvar preferências",()->{prefs.edit().putBoolean("persist_zoom",persist.isChecked()).putBoolean("auto_fit",fit.isChecked()).putBoolean("guided",guided.isChecked()).putBoolean("animate_guided",animate.isChecked()).putInt("brightness",Math.max(10,brightness.getProgress())).putString("theme",selectedTheme[0]).apply();if(changed!=null)changed.run();dialog.dismiss();});
        save.setCompoundDrawablesWithIntrinsicBounds(R.drawable.lucide_save,0,0,0);save.setCompoundDrawableTintList(ColorStateList.valueOf(Color.WHITE));save.setCompoundDrawablePadding(Ui.dp(activity,9));sheet.addView(save,new LinearLayout.LayoutParams(-1,Ui.dp(activity,54)));

        ScrollView scroll=new ScrollView(activity);scroll.setFillViewport(true);scroll.addView(sheet);dialog.setContentView(scroll);dialog.show();
        Window window=dialog.getWindow();if(window!=null){window.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);WindowManager.LayoutParams lp=window.getAttributes();lp.width=WindowManager.LayoutParams.MATCH_PARENT;lp.height=WindowManager.LayoutParams.WRAP_CONTENT;lp.gravity=Gravity.BOTTOM;lp.dimAmount=.62f;window.setAttributes(lp);}
    }

    private static ImageView icon(Context context,int resource,int tint){ImageView icon=new ImageView(context);icon.setImageResource(resource);icon.setColorFilter(tint);icon.setPadding(Ui.dp(context,11),Ui.dp(context,11),Ui.dp(context,11),Ui.dp(context,11));icon.setBackground(Ui.bordered(context,Ui.SURFACE_ALT,Ui.BORDER,Ui.RADIUS_MEDIUM));icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE);return icon;}
    private static void previewBrightness(Activity activity,int value){if(!(activity instanceof ReaderActivity))return;WindowManager.LayoutParams params=activity.getWindow().getAttributes();params.screenBrightness=Math.max(.1f,Math.min(1f,value/100f));activity.getWindow().setAttributes(params);}
    private static Switch readerSwitch(Context context,boolean checked){Switch control=new Switch(context);control.setChecked(checked);control.setShowText(false);control.setMinWidth(Ui.dp(context,58));control.setThumbTintList(new ColorStateList(SWITCH_STATES,new int[]{Color.WHITE,0xffd6deeb}));control.setTrackTintList(new ColorStateList(SWITCH_STATES,new int[]{Ui.RED,0xff344152}));return control;}
    private static View toggleRow(Context context,int resource,String title,String description,Switch control,boolean divider){LinearLayout wrapper=Ui.column(context);LinearLayout row=Ui.row(context);row.setPadding(Ui.dp(context,14),Ui.dp(context,12),Ui.dp(context,12),Ui.dp(context,12));row.addView(icon(context,resource,Ui.RED_BRIGHT),new LinearLayout.LayoutParams(Ui.dp(context,46),Ui.dp(context,46)));LinearLayout copy=Ui.column(context);copy.addView(Ui.title(context,title,15));TextView secondary=Ui.text(context,description,12,Ui.MUTED);secondary.setMaxLines(2);copy.addView(secondary);row.addView(copy,Ui.margin(0,-2,context,12,0,8,0));((LinearLayout.LayoutParams)copy.getLayoutParams()).weight=1;row.addView(control);wrapper.addView(row);if(divider){View line=new View(context);line.setBackgroundColor(Ui.BORDER);wrapper.addView(line,Ui.margin(-1,Ui.dp(context,1),context,74,0,12,0));}return wrapper;}
}

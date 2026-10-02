package com.lucrazy.komicove;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.text.DateFormat;
import java.util.*;
import java.util.concurrent.Executor;

/** Reuses the app header/bottom navigation; matches Phase 02 mobile cards. */
final class MonitoredFoldersView {
    interface Actions {void add();void refresh(String uri);void menu(JSONObject row);void enabled(String uri,boolean enabled);void dismiss();}
    static String t(Context c,String pt,String en){return "en".equals(I18n.language(c))?en:pt;}
    static void render(Context c,LinearLayout content,JSONArray folders,LibraryStore store,Executor images,Actions actions){
        content.addView(Ui.text(c,t(c,"Novas HQs adicionadas a estas pastas aparecem automaticamente na biblioteca.","New comics added to these folders automatically appear in your library."),15,Ui.MUTED),Ui.margin(-1,-2,c,0,-6,0,10));
        Button add=Ui.primaryButton(c,"Adicionar pasta",actions::add);add.setCompoundDrawablesWithIntrinsicBounds(R.drawable.lucide_plus,0,0,0);add.setCompoundDrawableTintList(android.content.res.ColorStateList.valueOf(android.graphics.Color.WHITE));add.setCompoundDrawablePadding(Ui.dp(c,8));
        content.addView(add,Ui.margin(Ui.dp(c,174),Ui.dp(c,44),c,0,0,0,14));
        List<LibraryStore.Book> books=store.all();
        for(int i=0;i<folders.length();i++){
            JSONObject folder=folders.optJSONObject(i);if(folder==null)continue;
            String uri=folder.optString("uri");LinearLayout card=Ui.row(c);Ui.pad(card,12);card.setBackground(Ui.bordered(c,Ui.SURFACE,Ui.BORDER,16));
            ImageView cover=new ImageView(c);cover.setImageResource(R.drawable.comic_cover_placeholder);cover.setScaleType(ImageView.ScaleType.CENTER_CROP);cover.setBackground(Ui.bordered(c,Ui.SURFACE_ALT,Ui.BORDER,5));cover.setClipToOutline(true);cover.setContentDescription(t(c,"Capa representativa da pasta","Representative folder cover"));card.addView(cover,new LinearLayout.LayoutParams(Ui.dp(c,60),Ui.dp(c,82)));
            for(LibraryStore.Book book:books){boolean belongs=false;for(int j=0;j<book.sources.length();j++){JSONObject source=book.sources.optJSONObject(j);if(source!=null&&uri.equals(source.optString("folder"))){belongs=true;break;}}if(belongs&&store.cover(book).isFile()){String path=store.cover(book).getAbsolutePath();images.execute(()->{BitmapFactory.Options options=new BitmapFactory.Options();options.inSampleSize=2;Bitmap bitmap=BitmapFactory.decodeFile(path,options);cover.post(()->{if(cover.isAttachedToWindow()&&bitmap!=null)cover.setImageBitmap(bitmap);else if(bitmap!=null)bitmap.recycle();});});break;}}
            LinearLayout labels=Ui.column(c);card.addView(labels,Ui.margin(0,-2,c,12,0,6,0));((LinearLayout.LayoutParams)labels.getLayoutParams()).weight=1;
            TextView name=Ui.title(c,folder.optString("name",t(c,"Pasta","Folder")),16);name.setMaxLines(2);name.setIncludeFontPadding(false);labels.addView(name);
            TextView count=Ui.text(c,folder.optInt("count")+t(c," HQs"," comics"),13,Ui.MUTED);count.setIncludeFontPadding(false);labels.addView(count,Ui.margin(-2,-2,c,0,4,0,1));
            TextView date=Ui.text(c,checkedDate(c,folder.optLong("checked")),12,Ui.MUTED);date.setIncludeFontPadding(false);labels.addView(date);
            String state=folder.optBoolean("enabled",true)?folder.optString("status","checking"):"paused";String label;int color;
            switch(state){case "unavailable":label=t(c,"Permissão necessária","Access required");color=Ui.ERROR;break;case "checking":label=t(c,"Verificando...","Checking...");color=Ui.WARNING;break;case "paused":label=t(c,"Pausada","Paused");color=Ui.MUTED;break;default:label=t(c,"Atualizada","Up to date");color=Ui.SUCCESS;}
            if(folder.optInt("new")>0&&state.equals("updated")){label=folder.optInt("new")+t(c," novas HQs"," new comics");color=0xff249dff;}
            TextView badge=Ui.text(c,label,11,color);badge.setIncludeFontPadding(false);badge.setPadding(Ui.dp(c,7),Ui.dp(c,4),Ui.dp(c,8),Ui.dp(c,4));badge.setBackground(Ui.bordered(c,(color&0xffffff)|0x14000000,(color&0xffffff)|0x55000000,Ui.RADIUS_PILL));
            android.graphics.drawable.GradientDrawable ring=new android.graphics.drawable.GradientDrawable();ring.setShape(android.graphics.drawable.GradientDrawable.OVAL);ring.setColor((color&0xffffff)|0x18000000);ring.setStroke(Ui.dp(c,1),(color&0xffffff)|0x44000000);
            android.graphics.drawable.GradientDrawable dot=new android.graphics.drawable.GradientDrawable();dot.setShape(android.graphics.drawable.GradientDrawable.OVAL);dot.setColor(color);
            android.graphics.drawable.LayerDrawable indicator=new android.graphics.drawable.LayerDrawable(new android.graphics.drawable.Drawable[]{ring,dot});int inset=Ui.dp(c,4);indicator.setLayerInset(1,inset,inset,inset,inset);indicator.setBounds(0,0,Ui.dp(c,18),Ui.dp(c,18));badge.setCompoundDrawables(indicator,null,null,null);badge.setCompoundDrawablePadding(Ui.dp(c,6));labels.addView(badge,Ui.margin(-2,-2,c,0,4,0,0));
            LinearLayout buttons=Ui.row(c);ImageButton refresh=Ui.iconButton(c,R.drawable.lucide_refresh,false,()->actions.refresh(uri));refresh.setContentDescription(t(c,"Atualizar pasta","Refresh folder"));buttons.addView(refresh,new LinearLayout.LayoutParams(Ui.dp(c,40),Ui.dp(c,42)));
            ImageButton menu=Ui.iconButton(c,R.drawable.lucide_more_horizontal,false,()->actions.menu(folder));menu.setContentDescription(t(c,"Ações da pasta","Folder actions"));buttons.addView(menu,Ui.margin(Ui.dp(c,40),Ui.dp(c,42),c,6,0,0,0));
            LinearLayout controls=Ui.column(c);controls.addView(buttons);
            Switch enabled=new Switch(c);enabled.setText(t(c,"Ativa","Active"));enabled.setTextSize(11);enabled.setTextColor(Ui.MUTED);enabled.setShowText(false);enabled.setSwitchPadding(Ui.dp(c,5));enabled.setChecked(folder.optBoolean("enabled",true));
            int[][] states={new int[]{android.R.attr.state_checked},new int[]{}};enabled.setThumbTintList(new android.content.res.ColorStateList(states,new int[]{android.graphics.Color.WHITE,0xffd6deeb}));enabled.setTrackTintList(new android.content.res.ColorStateList(states,new int[]{Ui.RED,0xff344152}));
            enabled.setContentDescription(t(c,"Ativar monitoramento: ","Enable monitoring: ")+folder.optString("name"));enabled.setOnCheckedChangeListener((button,checked)->actions.enabled(uri,checked));controls.addView(enabled,Ui.margin(-1,Ui.dp(c,40),c,0,4,0,0));card.addView(controls);
            content.addView(card,Ui.margin(-1,-2,c,0,0,0,9));
        }
        if(folders.length()==0)content.addView(Ui.text(c,t(c,"Adicione uma pasta para monitorar suas HQs. Seus arquivos não serão movidos.","Add a folder to monitor your comics. Your files will not be moved."),14,Ui.MUTED));
    }
    static String checkedDate(Context c,long checked){
        if(checked==0)return t(c,"Ainda não verificada","Not checked yet");
        Locale locale="en".equals(I18n.language(c))?Locale.US:new Locale("pt","BR");Calendar today=Calendar.getInstance(),day=Calendar.getInstance();day.setTimeInMillis(checked);
        String prefix=null;if(today.get(Calendar.ERA)==day.get(Calendar.ERA)&&today.get(Calendar.YEAR)==day.get(Calendar.YEAR)&&today.get(Calendar.DAY_OF_YEAR)==day.get(Calendar.DAY_OF_YEAR))prefix=t(c,"Hoje às ","Today at ");
        today.add(Calendar.DATE,-1);if(prefix==null&&today.get(Calendar.ERA)==day.get(Calendar.ERA)&&today.get(Calendar.YEAR)==day.get(Calendar.YEAR)&&today.get(Calendar.DAY_OF_YEAR)==day.get(Calendar.DAY_OF_YEAR))prefix=t(c,"Ontem às ","Yesterday at ");
        return prefix==null?DateFormat.getDateTimeInstance(DateFormat.SHORT,DateFormat.SHORT,locale).format(new Date(checked)):prefix+DateFormat.getTimeInstance(DateFormat.SHORT,locale).format(new Date(checked));
    }
}

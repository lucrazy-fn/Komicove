package com.lucrazy.panel;

import android.app.*;
import android.content.*;
import android.widget.*;

final class ReaderPreferences {
    static void show(Activity activity, Runnable changed) {
        SharedPreferences prefs=activity.getSharedPreferences("reader",0);
        LinearLayout box=Ui.column(activity); Ui.pad(box,20);
        String[] keys={"persist_zoom","auto_fit","guided","animate_guided"};
        String[] labels={"Manter zoom e posição entre páginas","Encaixar a página ao abrir","Leitura guiada — experimental","Transições suaves entre quadros"};
        CheckBox[] checks=new CheckBox[keys.length];
        for(int i=0;i<keys.length;i++) {
            checks[i]=new CheckBox(activity); checks[i].setText(labels[i]);
            checks[i].setChecked(prefs.getBoolean(keys[i],i!=2));box.addView(checks[i]);
        }
        box.addView(Ui.text(activity,"A leitura guiada aproxima quadros separados por espaços claros. Quando não reconhece o layout, percorre trechos sobrepostos, indicados como Trecho no contador. Os trechos podem cortar quadros e balões; você pode arrastar, ajustar o zoom ou usar Encaixar. Use as setas ou toque nas bordas para avançar. Disponível em página única e modo mangá.",14,Ui.MUTED));
        new AlertDialog.Builder(activity).setTitle("Preferências do leitor").setView(box)
            .setPositiveButton("Salvar",(d,w)->{
                SharedPreferences.Editor edit=prefs.edit();
                for(int i=0;i<keys.length;i++)edit.putBoolean(keys[i],checks[i].isChecked());
                edit.apply();if(changed!=null)changed.run();
            }).setNegativeButton("Cancelar",null).show();
    }
}

package com.lucrazy.komicove;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.widget.*;

final class Ui {
    static final int BG=0xff111113, SURFACE=0xff202026, TEXT=0xfff5f3ef, MUTED=0xffb4b3bd, RED=0xfff23941;
    static int dp(Context c, float n) { return Math.round(n*c.getResources().getDisplayMetrics().density); }
    static GradientDrawable shape(int color, float radius) {
        GradientDrawable d=new GradientDrawable(); d.setColor(color); d.setCornerRadius(radius); return d;
    }
    static LinearLayout column(Context c) { LinearLayout v=new LinearLayout(c); v.setOrientation(LinearLayout.VERTICAL); return v; }
    static LinearLayout row(Context c) { LinearLayout v=new LinearLayout(c); v.setOrientation(LinearLayout.HORIZONTAL); v.setGravity(android.view.Gravity.CENTER_VERTICAL); return v; }
    static void pad(View v,int n) { int p=dp(v.getContext(),n); v.setPadding(p,p,p,p); }
    static TextView text(Context c,String s,int size,int color) {
        TextView t=new TextView(c); t.setText(I18n.t(c,s)); t.setTextSize(size); t.setTextColor(color); t.setPadding(0,dp(c,5),0,dp(c,5)); return t;
    }
    static TextView title(Context c,String s,int size) { TextView t=text(c,s,size,TEXT); t.setTypeface(null, Typeface.BOLD); return t; }
    static Button button(Context c,String s,Runnable action) {
        Button b=new Button(c); b.setText(I18n.t(c,s)); b.setAllCaps(false); b.setTextColor(TEXT); b.setTextSize(14);
        b.setMinHeight(dp(c,48)); b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(SURFACE));
        b.setOnClickListener(v->action.run()); return b;
    }
    static EditText input(Context c,String hint,boolean password) {
        EditText e=new EditText(c); e.setHint(I18n.t(c,hint)); e.setTextColor(TEXT); e.setHintTextColor(MUTED); e.setSingleLine(true);
        e.setInputType(password?129:1); return e;
    }
    static void insets(Activity a,View root) {
        root.setOnApplyWindowInsetsListener((v,in)-> {v.setPadding(in.getSystemWindowInsetLeft(),in.getSystemWindowInsetTop(),in.getSystemWindowInsetRight(),in.getSystemWindowInsetBottom()); return in;});
        root.requestApplyInsets();
    }
    static void enter(View v) {
        if (android.provider.Settings.Global.getFloat(v.getContext().getContentResolver(),android.provider.Settings.Global.ANIMATOR_DURATION_SCALE,1)==0) return;
        v.setAlpha(0); v.setTranslationY(dp(v.getContext(),8)); v.animate().alpha(1).translationY(0).setDuration(180).start();
    }
}

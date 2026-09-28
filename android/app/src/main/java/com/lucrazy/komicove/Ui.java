package com.lucrazy.komicove;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.content.res.ColorStateList;
import android.graphics.drawable.Drawable;
import android.view.View;
import android.widget.*;

final class Ui {
    static final int BG=0xff090b0f, SURFACE=0xff10141b, SURFACE_ALT=0xff171d26,
            SURFACE_HOVER=0xff222b36, BORDER=0xff28313c, TEXT=0xfff5f6f8,
            MUTED=0xffa1adba, RED=0xffe12835, RED_BRIGHT=0xffff4b55;
    static final int RADIUS_SMALL=9, RADIUS_MEDIUM=13, RADIUS_LARGE=18;
    static int dp(Context c, float n) { return Math.round(n*c.getResources().getDisplayMetrics().density); }
    static GradientDrawable shape(int color, float radius) {
        GradientDrawable d=new GradientDrawable(); d.setColor(color); d.setCornerRadius(radius); return d;
    }
    static GradientDrawable bordered(Context c,int color,int stroke,float radius) {
        GradientDrawable d=shape(color,dp(c,radius));d.setStroke(dp(c,1),stroke);return d;
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
        b.setTypeface(null,Typeface.BOLD);b.setMinHeight(dp(c,46));b.setMinimumHeight(0);b.setMinimumWidth(0);
        b.setPadding(dp(c,16),0,dp(c,16),0);
        StateListDrawable states=new StateListDrawable();
        states.addState(new int[]{android.R.attr.state_pressed},bordered(c,SURFACE_HOVER,RED_BRIGHT,RADIUS_MEDIUM));
        states.addState(new int[]{},bordered(c,SURFACE_ALT,BORDER,RADIUS_MEDIUM));
        b.setBackground(states);b.setStateListAnimator(null);
        b.setOnClickListener(v->action.run()); return b;
    }
    static Button primaryButton(Context c,String s,Runnable action) {
        Button b=button(c,s,action);StateListDrawable states=new StateListDrawable();
        states.addState(new int[]{android.R.attr.state_pressed},bordered(c,0xffb91e2b,RED_BRIGHT,RADIUS_MEDIUM));
        states.addState(new int[]{},bordered(c,RED,RED_BRIGHT,RADIUS_MEDIUM));
        b.setBackground(states);return b;
    }
    static EditText input(Context c,String hint,boolean password) {
        EditText e=new EditText(c); e.setHint(I18n.t(c,hint)); e.setTextColor(TEXT); e.setHintTextColor(MUTED); e.setSingleLine(true);
        e.setTextSize(15);e.setInputType(password?129:1);e.setPadding(dp(c,16),0,dp(c,16),0);
        e.setMinimumHeight(dp(c,50));e.setBackground(bordered(c,SURFACE_ALT,BORDER,RADIUS_MEDIUM));return e;
    }
    static Button navButton(Context c,String label,int icon,boolean active,Runnable action) {
        Button b=button(c,label,action);b.setTextSize(11);b.setTypeface(null,active?Typeface.BOLD:Typeface.NORMAL);
        b.setTextColor(active?RED_BRIGHT:MUTED);b.setGravity(android.view.Gravity.CENTER);
        b.setCompoundDrawablesWithIntrinsicBounds(0,icon,0,0);b.setCompoundDrawablePadding(dp(c,3));
        b.setCompoundDrawableTintList(ColorStateList.valueOf(active?RED_BRIGHT:MUTED));
        b.setPadding(0,dp(c,5),0,dp(c,5));b.setBackground(active?bordered(c,SURFACE_ALT,0xff98262d,RADIUS_MEDIUM):shape(BG,dp(c,RADIUS_MEDIUM)));
        return b;
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

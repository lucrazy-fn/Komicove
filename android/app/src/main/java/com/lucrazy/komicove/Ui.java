package com.lucrazy.komicove;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.InsetDrawable;
import android.graphics.drawable.LayerDrawable;
import android.graphics.drawable.StateListDrawable;
import android.content.res.ColorStateList;
import android.graphics.drawable.Drawable;
import android.view.Gravity;
import android.view.View;
import android.widget.*;

final class Ui {
    static int BG=0xff080b10, SURFACE=0xff0f151d, SURFACE_ALT=0xff151d27,
            SURFACE_HOVER=0xff202b38, BORDER=0xff344152, TEXT=0xfff8f9fb,
            MUTED=0xffaebbd0, RED=0xffef2638, RED_BRIGHT=0xffff4050;
    static final int SUCCESS=0xff35d58b, WARNING=0xfff6c453, ERROR=0xffff5665;
    static final int RADIUS_SMALL=10, RADIUS_MEDIUM=14, RADIUS_LARGE=20, RADIUS_PILL=28;
    static final int SPACE_XS=4, SPACE_SM=8, SPACE_MD=12, SPACE_LG=16, SPACE_XL=24;

    static void configure(Context c) {
        boolean light=c.getSharedPreferences("ui",0).getBoolean("light",false);
        if(light){BG=0xfff3f4f7;SURFACE=0xffffffff;SURFACE_ALT=0xffe9edf3;SURFACE_HOVER=0xffdde3eb;BORDER=0xffc8d0dc;TEXT=0xff11151b;MUTED=0xff5e6978;}
        else {BG=0xff080b10;SURFACE=0xff0f151d;SURFACE_ALT=0xff151d27;SURFACE_HOVER=0xff202b38;BORDER=0xff344152;TEXT=0xfff8f9fb;MUTED=0xffaebbd0;}
    }
    static int dp(Context c, float n) { return Math.round(n*c.getResources().getDisplayMetrics().density); }
    static GradientDrawable shape(int color, float radius) {
        GradientDrawable d=new GradientDrawable(); d.setColor(color); d.setCornerRadius(radius); return d;
    }
    static GradientDrawable bordered(Context c,int color,int stroke,float radius) {
        GradientDrawable d=shape(color,dp(c,radius));d.setStroke(dp(c,1),stroke);return d;
    }
    static Drawable glow(Context c,int color,float radius) {
        GradientDrawable halo=bordered(c,0x22ff2638,0x66ff2638,radius+2);
        GradientDrawable core=bordered(c,color,RED_BRIGHT,radius);
        return new LayerDrawable(new Drawable[]{halo,core});
    }
    static LinearLayout column(Context c) { LinearLayout v=new LinearLayout(c); v.setOrientation(LinearLayout.VERTICAL); return v; }
    static LinearLayout row(Context c) { LinearLayout v=new LinearLayout(c); v.setOrientation(LinearLayout.HORIZONTAL); v.setGravity(android.view.Gravity.CENTER_VERTICAL); return v; }
    static void pad(View v,int n) { int p=dp(v.getContext(),n); v.setPadding(p,p,p,p); }
    static TextView text(Context c,String s,int size,int color) {
        TextView t=new TextView(c); t.setText(I18n.t(c,s)); t.setTextSize(size); t.setTextColor(color); t.setIncludeFontPadding(false);t.setLineSpacing(0,1.08f);t.setPadding(0,dp(c,4),0,dp(c,4)); return t;
    }
    static TextView title(Context c,String s,int size) { TextView t=text(c,s,size,TEXT); t.setTypeface(null, Typeface.BOLD); return t; }
    static TextView sectionTitle(Context c,String s,int icon) {TextView t=title(c,s,20);t.setCompoundDrawablesWithIntrinsicBounds(icon,0,0,0);t.setCompoundDrawablePadding(dp(c,10));t.setCompoundDrawableTintList(ColorStateList.valueOf(RED_BRIGHT));return t;}
    static Button button(Context c,String s,Runnable action) {
        Button b=new Button(c); b.setText(I18n.t(c,s)); b.setAllCaps(false); b.setTextColor(TEXT); b.setTextSize(14);
        b.setTypeface(null,Typeface.BOLD);b.setMinHeight(dp(c,48));b.setMinimumHeight(0);b.setMinimumWidth(0);b.setIncludeFontPadding(false);
        b.setPadding(dp(c,16),0,dp(c,16),0);
        StateListDrawable states=new StateListDrawable();
        states.addState(new int[]{android.R.attr.state_pressed},bordered(c,SURFACE_HOVER,RED_BRIGHT,RADIUS_MEDIUM));
        states.addState(new int[]{},bordered(c,SURFACE_ALT,BORDER,RADIUS_MEDIUM));
        b.setBackground(states);b.setStateListAnimator(null);
        b.setOnClickListener(v->action.run()); return b;
    }
    static Button primaryButton(Context c,String s,Runnable action) {
        Button b=button(c,s,action);StateListDrawable states=new StateListDrawable();
        states.addState(new int[]{android.R.attr.state_pressed},glow(c,0xffc91f30,RADIUS_MEDIUM));
        states.addState(new int[]{},glow(c,RED,RADIUS_MEDIUM));
        b.setBackground(states);b.setTextColor(Color.WHITE);return b;
    }
    static Button chip(Context c,String s,int icon,boolean active,Runnable action) {
        Button b=active?primaryButton(c,s,action):button(c,s,action);b.setTextSize(12);b.setTypeface(null,active?Typeface.BOLD:Typeface.NORMAL);
        b.setMinHeight(dp(c,44));b.setPadding(dp(c,12),0,dp(c,12),0);if(icon!=0){b.setCompoundDrawablesWithIntrinsicBounds(icon,0,0,0);b.setCompoundDrawablePadding(dp(c,7));b.setCompoundDrawableTintList(ColorStateList.valueOf(active?0xffffffff:MUTED));}return b;
    }
    static ImageButton iconButton(Context c,int icon,boolean active,Runnable action) {
        ImageButton b=new ImageButton(c);b.setImageResource(icon);b.setColorFilter(active?RED_BRIGHT:MUTED);b.setPadding(dp(c,12),dp(c,12),dp(c,12),dp(c,12));b.setBackground(active?glow(c,SURFACE_ALT,RADIUS_MEDIUM):bordered(c,SURFACE_ALT,BORDER,RADIUS_MEDIUM));b.setOnClickListener(v->action.run());b.setContentDescription("");return b;
    }
    static EditText input(Context c,String hint,boolean password) {
        EditText e=new EditText(c); e.setHint(I18n.t(c,hint)); e.setTextColor(TEXT); e.setHintTextColor(MUTED); e.setSingleLine(true);
        e.setTextSize(15);e.setInputType(password?129:1);e.setPadding(dp(c,16),0,dp(c,16),0);
        e.setMinimumHeight(dp(c,54));e.setBackground(bordered(c,SURFACE_ALT,BORDER,RADIUS_MEDIUM));return e;
    }
    static EditText search(Context c,String hint) {EditText e=input(c,hint,false);e.setCompoundDrawablesWithIntrinsicBounds(R.drawable.lucide_search,0,R.drawable.lucide_sliders,0);e.setCompoundDrawablePadding(dp(c,12));e.setCompoundDrawableTintList(ColorStateList.valueOf(MUTED));return e;}
    static Button navButton(Context c,String label,int icon,boolean active,Runnable action) {
        Button b=button(c,label,action);b.setTextSize(11);b.setTypeface(null,active?Typeface.BOLD:Typeface.NORMAL);
        b.setTextColor(active?RED_BRIGHT:MUTED);b.setGravity(Gravity.CENTER);
        b.setCompoundDrawablesWithIntrinsicBounds(0,icon,0,0);b.setCompoundDrawablePadding(dp(c,3));
        b.setCompoundDrawableTintList(ColorStateList.valueOf(active?RED_BRIGHT:MUTED));
        b.setPadding(0,dp(c,7),0,dp(c,6));b.setBackground(active?glow(c,0xff24151a,RADIUS_LARGE):shape(BG,dp(c,RADIUS_LARGE)));
        return b;
    }
    static LinearLayout card(Context c) {LinearLayout card=column(c);pad(card,SPACE_LG);card.setBackground(bordered(c,SURFACE,BORDER,RADIUS_LARGE));return card;}
    static Space space(Context c,int dp){Space v=new Space(c);v.setLayoutParams(new LinearLayout.LayoutParams(1,dp(c,dp)));return v;}
    static LinearLayout.LayoutParams margin(int width,int height,Context c,int left,int top,int right,int bottom){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(width,height);p.setMargins(dp(c,left),dp(c,top),dp(c,right),dp(c,bottom));return p;}
    static void insets(Activity a,View root) {
        root.setOnApplyWindowInsetsListener((v,in)-> {v.setPadding(in.getSystemWindowInsetLeft(),in.getSystemWindowInsetTop(),in.getSystemWindowInsetRight(),in.getSystemWindowInsetBottom()); return in;});
        root.requestApplyInsets();
    }
    static void enter(View v) {
        if (android.provider.Settings.Global.getFloat(v.getContext().getContentResolver(),android.provider.Settings.Global.ANIMATOR_DURATION_SCALE,1)==0) return;
        v.setAlpha(0); v.setTranslationY(dp(v.getContext(),8)); v.animate().alpha(1).translationY(0).setDuration(180).start();
    }
}

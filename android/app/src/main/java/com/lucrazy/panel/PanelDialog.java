package com.lucrazy.panel;

import android.content.Context;
import android.content.DialogInterface;

class PanelDialog extends android.app.AlertDialog.Builder {
    private final Context context;

    PanelDialog(Context context) {
        super(context);
        this.context = context;
    }

    private CharSequence translated(CharSequence value) {
        return value == null ? null : I18n.t(context, value.toString());
    }

    private CharSequence[] translated(CharSequence[] values) {
        if (values == null) return null;
        CharSequence[] result = new CharSequence[values.length];
        for (int i = 0; i < values.length; i++) result[i] = translated(values[i]);
        return result;
    }

    @Override public PanelDialog setTitle(CharSequence title) {
        super.setTitle(translated(title));
        return this;
    }

    @Override public PanelDialog setMessage(CharSequence message) {
        super.setMessage(translated(message));
        return this;
    }

    @Override public PanelDialog setPositiveButton(CharSequence text, DialogInterface.OnClickListener listener) {
        super.setPositiveButton(translated(text), listener);
        return this;
    }

    @Override public PanelDialog setNegativeButton(CharSequence text, DialogInterface.OnClickListener listener) {
        super.setNegativeButton(translated(text), listener);
        return this;
    }

    @Override public PanelDialog setNeutralButton(CharSequence text, DialogInterface.OnClickListener listener) {
        super.setNeutralButton(translated(text), listener);
        return this;
    }

    @Override public PanelDialog setItems(CharSequence[] items, DialogInterface.OnClickListener listener) {
        super.setItems(translated(items), listener);
        return this;
    }

    @Override public PanelDialog setSingleChoiceItems(CharSequence[] items, int checkedItem, DialogInterface.OnClickListener listener) {
        super.setSingleChoiceItems(translated(items), checkedItem, listener);
        return this;
    }
}

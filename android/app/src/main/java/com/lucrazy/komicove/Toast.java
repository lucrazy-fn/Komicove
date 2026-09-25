package com.lucrazy.komicove;

import android.content.Context;

final class Toast {
    static final int LENGTH_SHORT = android.widget.Toast.LENGTH_SHORT;
    static final int LENGTH_LONG = android.widget.Toast.LENGTH_LONG;

    static android.widget.Toast makeText(Context context, CharSequence text, int duration) {
        return android.widget.Toast.makeText(context, I18n.t(context, text == null ? "" : text.toString()), duration);
    }

    private Toast() {}
}

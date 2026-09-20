package com.lucrazy.panel;

import android.content.Context;

final class AlertDialog {
    static final class Builder extends PanelDialog {
        Builder(Context context) {
            super(context);
        }
    }

    private AlertDialog() {}
}

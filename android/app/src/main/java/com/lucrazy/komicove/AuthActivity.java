package com.lucrazy.komicove;

import android.app.*;
import android.content.*;
import android.graphics.*;
import android.graphics.drawable.*;
import android.os.*;
import android.text.InputType;
import android.text.method.PasswordTransformationMethod;
import android.util.Patterns;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import org.json.*;
import java.util.concurrent.*;

public final class AuthActivity extends Activity {
    private final ExecutorService work=Executors.newSingleThreadExecutor();
    private PanelApi api;
    private FrameLayout root;
    private boolean busy;

    @Override public void onCreate(Bundle state){
        super.onCreate(state);Ui.configure(this);api=new PanelApi(this);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(0xff05070b);
        show(false);
    }

    private void show(boolean register){
        root=new FrameLayout(this);root.setBackgroundColor(0xff05070b);setContentView(root);Ui.insets(this,root);
        ImageView background=new ImageView(this);background.setImageResource(R.drawable.auth_mobile_background);
        background.setScaleType(ImageView.ScaleType.CENTER_CROP);root.addView(background,new FrameLayout.LayoutParams(-1,-1));
        View shade=new View(this);shade.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0x22000000,0x78000000,0xd906080d,0xf207090d}));
        root.addView(shade,new FrameLayout.LayoutParams(-1,-1));
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setVerticalScrollBarEnabled(false);
        root.addView(scroll,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout content=Ui.column(this);content.setGravity(Gravity.CENTER_HORIZONTAL);
        content.setPadding(Ui.dp(this,28),Ui.dp(this,28),Ui.dp(this,28),Ui.dp(this,30));scroll.addView(content);

        ImageView logo=new ImageView(this);logo.setImageResource(R.drawable.komicove_logo);logo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        content.addView(logo,new LinearLayout.LayoutParams(-1,Ui.dp(this,register?160:190)));
        TextView title=Ui.title(this,register?"Criar conta":"Entrar",40);title.setGravity(Gravity.CENTER);content.addView(title);
        TextView subtitle=Ui.text(this,register?"Entre para a comunidade e descubra um universo de histórias incríveis.":"Acesse sua conta e continue explorando histórias incríveis.",17,0xffb5bfd6);
        subtitle.setGravity(Gravity.CENTER);content.addView(subtitle,Ui.margin(-1,-2,this,10,4,10,24));

        EditText username=input(register?"Usuário":"Usuário ou e-mail",R.drawable.lucide_user,false);
        content.addView(username,fieldParams());
        EditText displayName=null,email=null;
        if(register){
            displayName=input("Nome de exibição",R.drawable.lucide_profile,false);content.addView(displayName,fieldParams());
            email=input("E-mail",R.drawable.lucide_mail,false);email.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);content.addView(email,fieldParams());
        }
        EditText password=input("Senha",R.drawable.lucide_lock,true);content.addView(password,fieldParams());
        EditText confirm=null;
        if(register){confirm=input("Confirmar senha",R.drawable.lucide_lock,true);content.addView(confirm,fieldParams());}
        EditText code=null;
        if(!register){
            TextView forgot=Ui.text(this,"Esqueci minha senha",15,0xffb8c2da);forgot.setGravity(Gravity.END);
            forgot.setOnClickListener(v->recover());content.addView(forgot,Ui.margin(-1,-2,this,0,-2,0,12));
            code=input("Código 2FA ou de recuperação",R.drawable.lucide_shield,false);
            code.setVisibility(View.GONE);
            content.addView(code,fieldParams());
        }

        final EditText finalDisplayName=displayName,finalEmail=email,finalConfirm=confirm,finalCode=code;
        Button primary=primary(register?"Criar conta":"Entrar",()->{
            String user=username.getText().toString().trim(),pass=password.getText().toString();
            if(user.isEmpty()||pass.isEmpty()){toast("Preencha usuário e senha.");return;}
            if(register&&user.length()<3){toast("O usuário deve ter pelo menos 3 caracteres.");username.requestFocus();return;}
            if(register&&!user.matches("[A-Za-z0-9_.-]{3,32}")){toast("Use apenas letras, números, ponto, hífen ou sublinhado no usuário.");username.requestFocus();return;}
            if(register&&pass.length()<8){toast("A senha deve ter pelo menos 8 caracteres.");password.requestFocus();return;}
            if(register&&(!pass.equals(finalConfirm.getText().toString()))){toast("As senhas não coincidem.");return;}
            if(register){String mail=finalEmail.getText().toString().trim();if(!mail.isEmpty()&&!Patterns.EMAIL_ADDRESS.matcher(mail).matches()){toast("Informe um e-mail válido.");finalEmail.requestFocus();return;}}
            JSONObject body=new JSONObject();
            try{
                body.put("username",user).put("password",pass);
                if(register){
                    String name=finalDisplayName.getText().toString().trim(),mail=finalEmail.getText().toString().trim();
                    body.put("display_name",name.isEmpty()?user:name).put("email",mail.isEmpty()?JSONObject.NULL:mail);
                }else{
                    String second=finalCode.getText().toString().trim();
                    body.put("totp_code",second.isEmpty()?JSONObject.NULL:second);
                }
            }catch(JSONException ignored){}
            authenticate(register?"/auth/register":"/auth/login",body,finalCode);
        });
        content.addView(primary,new LinearLayout.LayoutParams(-1,Ui.dp(this,60)));
        Button guest=secondary("Entrar como convidado",()->{
            getSharedPreferences("auth_state",0).edit().putString("mode","guest").apply();
            setResult(RESULT_OK);finish();
        });guest.setCompoundDrawablesWithIntrinsicBounds(R.drawable.lucide_user,0,R.drawable.lucide_arrow_right,0);
        guest.setCompoundDrawablePadding(Ui.dp(this,10));content.addView(guest,Ui.margin(-1,Ui.dp(this,58),this,0,12,0,0));

        LinearLayout switchRow=Ui.row(this);switchRow.setGravity(Gravity.CENTER);
        TextView prefix=Ui.text(this,register?"Já tenho uma conta? ":"Ainda não tem uma conta? ",15,0xffadb8cf);
        TextView action=Ui.text(this,register?"Entrar":"Criar conta",15,Ui.RED_BRIGHT);action.setTypeface(null,Typeface.BOLD);
        action.setOnClickListener(v->show(!register));switchRow.addView(prefix);switchRow.addView(action);
        content.addView(switchRow,Ui.margin(-1,-2,this,0,18,0,8));
    }

    private LinearLayout.LayoutParams fieldParams(){return Ui.margin(-1,Ui.dp(this,62),this,0,0,0,12);}
    private EditText input(String hint,int icon,boolean password){
        EditText field=Ui.input(this,hint,password);field.setSingleLine(true);field.setTextColor(Color.WHITE);
        field.setHintTextColor(0xff929db5);field.setTextSize(16);field.setPadding(Ui.dp(this,18),0,Ui.dp(this,18),0);
        field.setCompoundDrawablesWithIntrinsicBounds(icon,0,password?R.drawable.lucide_eye:0,0);field.setCompoundDrawablePadding(Ui.dp(this,12));
        tint(field);field.setBackground(fieldBackground(false));field.setOnFocusChangeListener((v,focus)->field.setBackground(fieldBackground(focus)));
        if(password){field.setTransformationMethod(PasswordTransformationMethod.getInstance());passwordToggle(field,icon);}return field;
    }
    private void passwordToggle(EditText field,int icon){
        final boolean[] visible={false};
        field.setOnTouchListener((v,event)->{
            if(event.getAction()!=MotionEvent.ACTION_UP||field.getCompoundDrawables()[2]==null)return false;
            if(event.getX()<field.getWidth()-Ui.dp(this,58))return false;
            visible[0]=!visible[0];int selection=field.getSelectionEnd();
            field.setTransformationMethod(visible[0]?null:PasswordTransformationMethod.getInstance());
            field.setCompoundDrawablesWithIntrinsicBounds(icon,0,visible[0]?R.drawable.lucide_eye_off:R.drawable.lucide_eye,0);tint(field);
            field.setSelection(Math.max(0,Math.min(selection,field.length())));return true;
        });
    }
    private void tint(EditText field){for(Drawable d:field.getCompoundDrawables())if(d!=null)d.mutate().setColorFilter(0xffc4cce0,android.graphics.PorterDuff.Mode.SRC_IN);}
    private Drawable fieldBackground(boolean focus){GradientDrawable g=new GradientDrawable();g.setColor(0xe8121720);g.setCornerRadius(Ui.dp(this,18));g.setStroke(Ui.dp(this,focus?2:1),focus?Ui.RED_BRIGHT:0xff3a465a);return g;}
    private Button primary(String text,Runnable action){Button b=new Button(this);b.setText(text);b.setAllCaps(false);b.setTextColor(Color.WHITE);b.setTextSize(17);b.setTypeface(null,Typeface.BOLD);b.setGravity(Gravity.CENTER);b.setCompoundDrawablesWithIntrinsicBounds(0,0,R.drawable.lucide_arrow_right,0);b.setCompoundDrawablePadding(Ui.dp(this,10));b.setBackground(Ui.glow(this,Ui.RED,Ui.RADIUS_LARGE));b.setOnClickListener(v->action.run());b.setElevation(Ui.dp(this,8));return b;}
    private Button secondary(String text,Runnable action){Button b=Ui.button(this,text,action);b.setGravity(Gravity.CENTER);b.setTextSize(16);b.setTypeface(null,Typeface.BOLD);b.setBackground(Ui.bordered(this,0xe810141c,Ui.RED,Ui.RADIUS_LARGE));return b;}
    private void authenticate(String path,JSONObject body,EditText secondFactor){
        if(busy)return;busy=true;hideKeyboard();toast(path.endsWith("register")?"Criando conta...":"Entrando...");
        work.execute(()->{try{api.authenticate(path,body);getSharedPreferences("auth_state",0).edit().putString("mode","account").apply();runOnUiThread(()->{busy=false;setResult(RESULT_OK);finish();});}catch(Exception e){runOnUiThread(()->{busy=false;String message=e.getMessage()==null?"Não foi possível entrar.":e.getMessage();String normalized=message.toLowerCase(java.util.Locale.ROOT);if(secondFactor!=null&&(normalized.contains("2fa")||normalized.contains("totp")||normalized.contains("recupera"))){secondFactor.setVisibility(View.VISIBLE);secondFactor.requestFocus();}toast(message);});}});
    }
    private void recover(){
        EditText identifier=input("Usuário ou e-mail",R.drawable.lucide_mail,false);
        new AlertDialog.Builder(this).setTitle("Recuperar senha").setView(identifier).setPositiveButton("Enviar código",(d,w)->{
            JSONObject body=new JSONObject();try{body.put("identifier",identifier.getText().toString().trim());}catch(Exception ignored){}
            work.execute(()->{try{api.json("POST","/auth/password-recovery/request",body);runOnUiThread(this::confirmRecovery);}catch(Exception e){runOnUiThread(()->toast(e.getMessage()));}});
        }).setNegativeButton("Cancelar",null).show();
    }
    private void confirmRecovery(){
        LinearLayout box=Ui.column(this);box.setPadding(Ui.dp(this,18),0,Ui.dp(this,18),0);
        EditText token=input("Código recebido",R.drawable.lucide_mail,false),password=input("Nova senha",R.drawable.lucide_lock,true);
        box.addView(token,fieldParams());box.addView(password,fieldParams());
        new AlertDialog.Builder(this).setTitle("Criar nova senha").setView(box).setPositiveButton("Salvar",(d,w)->work.execute(()->{
            try{api.json("POST","/auth/password-recovery/confirm",new JSONObject().put("token",token.getText().toString().trim()).put("new_password",password.getText().toString()));runOnUiThread(()->toast("Senha alterada. Agora você pode entrar."));}
            catch(Exception e){runOnUiThread(()->toast(e.getMessage()));}
        })).setNegativeButton("Cancelar",null).show();
    }
    private void hideKeyboard(){View current=getCurrentFocus();if(current!=null)((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(current.getWindowToken(),0);}
    private void toast(String message){Toast.makeText(this,message==null?"Não foi possível concluir.":message,Toast.LENGTH_LONG).show();}
    @Override protected void onDestroy(){work.shutdownNow();super.onDestroy();}
}

package com.lucrazy.komicove;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.RectF;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.net.Uri;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.*;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

final class ComicTranslationDialog {
    interface Host {
        int page();int count();boolean manga();String bookKey();RectF panel();Bitmap bitmap(int page)throws Exception;
        void show(int page,List<ComicTranslation.Region> regions,String view);
    }
    private final Activity activity;private final Host host;private final SharedPreferences prefs;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();private final AtomicBoolean cancel=new AtomicBoolean();
    private Future<?> running;private android.app.Dialog dialog;private EditText source,target,script,provider,model,endpoint,key,glossary,original,translation;
    private Spinner scope,view,regionsSpinner,modePicker,servicePicker;private CheckBox consent,vision;private TextView status;private List<ComicTranslation.Region> rows=new ArrayList<>();private int page;
    private LinearLayout remoteOptions,localOptions,advancedOptions,remoteAdvanced,localAdvanced;private EditText termOriginal,termTranslation;private Spinner termPicker;
    private ZoomPage preview;private Button localChoice,remoteChoice,cancelAction;
    private static final String[] SERVICES={"OpenAI","Anthropic","xAI","Groq","OpenRouter","Gemini","Compatível"};
    private static final String[] SERVICE_IDS={"openai","anthropic","xai","groq","openrouter","gemini","compatible"};
    private static final String[] DEFAULT_MODELS={"gpt-5.4-mini","claude-sonnet-5-5","grok-4.7","openai/gpt-oss-20b","openrouter/auto","gemini-3.8-flash",""};
    private static final String[] KEY_URLS={"https://platform.openai.com/api-keys","https://console.anthropic.com/settings/keys","https://console.x.ai/","https://console.groq.com/keys","https://openrouter.ai/settings/keys","https://aistudio.google.com/app/apikey",""};
    private static final String[] LANGUAGE_CODES={"auto","pt","en","es","fr","de","it","ja","zh","ko"};
    private static final String[] LANGUAGE_LABELS={"Detectar automaticamente","Português","Inglês","Espanhol","Francês","Alemão","Italiano","Japonês","Chinês","Coreano"};
    ComicTranslationDialog(Activity activity,Host host){this.activity=activity;this.host=host;this.page=host.page();prefs=activity.getSharedPreferences("comic_translation_prefs",0);}
    private String t(String value){return I18n.t(activity,value);}
    private EditText field(LinearLayout layout,String title,String stored,String fallback){layout.addView(Ui.text(activity,t(title),13,Ui.MUTED));EditText field=new EditText(activity);field.setSingleLine(true);field.setText(prefs.getString(stored,fallback));field.setTextColor(Ui.TEXT);field.setHintTextColor(Ui.MUTED);field.setBackground(Ui.bordered(activity,Ui.SURFACE_ALT,Ui.BORDER,Ui.RADIUS_SMALL));field.setPadding(Ui.dp(activity,10),Ui.dp(activity,5),Ui.dp(activity,10),Ui.dp(activity,5));layout.addView(field,Ui.margin(-1,Ui.dp(activity,44),activity,0,2,0,8));return field;}
    private Button button(LinearLayout row,String label,Runnable action){Button b=Ui.primaryButton(activity,t(label),action);row.addView(b,new LinearLayout.LayoutParams(0,Ui.dp(activity,46),1));return b;}
    private Button secondary(LinearLayout row,String label,Runnable action){Button b=Ui.button(activity,t(label),action);row.addView(b,new LinearLayout.LayoutParams(0,Ui.dp(activity,46),1));return b;}
    private ArrayAdapter<String> readable(String[] values){return new ArrayAdapter<String>(activity,android.R.layout.simple_spinner_item,values){
        @Override public View getView(int position,View convert,android.view.ViewGroup parent){TextView label=(TextView)super.getView(position,convert,parent);label.setTextColor(Ui.TEXT);label.setTextSize(16);label.setPadding(Ui.dp(activity,12),Ui.dp(activity,8),Ui.dp(activity,12),Ui.dp(activity,8));return label;}
        @Override public View getDropDownView(int position,View convert,android.view.ViewGroup parent){TextView label=(TextView)super.getDropDownView(position,convert,parent);label.setTextColor(Ui.TEXT);label.setTextSize(16);label.setBackgroundColor(Ui.SURFACE_ALT);label.setPadding(Ui.dp(activity,16),Ui.dp(activity,12),Ui.dp(activity,16),Ui.dp(activity,12));return label;}
    };}
    private Spinner choices(LinearLayout layout,String label,String[] values,int initial){layout.addView(Ui.text(activity,t(label),14,Ui.MUTED));Spinner spinner=new Spinner(activity);spinner.setPopupBackgroundDrawable(new ColorDrawable(Ui.SURFACE_ALT));spinner.setAdapter(readable(values));spinner.setSelection(initial);layout.addView(spinner,Ui.margin(-1,Ui.dp(activity,50),activity,0,0,0,8));return spinner;}
    private Spinner language(LinearLayout layout,String title,EditText value,boolean automatic){String[] names=new String[LANGUAGE_LABELS.length-(automatic?0:1)];for(int i=0;i<names.length;i++)names[i]=t(LANGUAGE_LABELS[i+(automatic?0:1)]);String current=value.getText().toString();int at=0;for(int i=0;i<names.length;i++)if(LANGUAGE_CODES[i+(automatic?0:1)].equals(current))at=i;Spinner picker=choices(layout,title,names,at);picker.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> parent){}public void onItemSelected(android.widget.AdapterView<?> parent,View v,int position,long id){value.setText(LANGUAGE_CODES[position+(automatic?0:1)]);}});return picker;}
    void show(){
        LinearLayout screen=Ui.column(activity);screen.setBackgroundColor(Ui.BG);
        LinearLayout toolbar=Ui.row(activity);toolbar.setGravity(Gravity.CENTER_VERTICAL);toolbar.setPadding(Ui.dp(activity,16),Ui.dp(activity,12),Ui.dp(activity,16),Ui.dp(activity,10));
        ImageButton back=Ui.iconButton(activity,R.drawable.lucide_arrow_left,false,()->dialog.dismiss());back.setContentDescription(t("Voltar à leitura"));toolbar.addView(back,new LinearLayout.LayoutParams(Ui.dp(activity,48),Ui.dp(activity,48)));
        LinearLayout heading=Ui.column(activity);heading.addView(Ui.title(activity,t("Tradução"),24));heading.addView(Ui.text(activity,t("Traduza esta página e continue de onde parou."),13,Ui.MUTED));LinearLayout.LayoutParams headingParams=new LinearLayout.LayoutParams(0,LinearLayout.LayoutParams.WRAP_CONTENT,1);headingParams.leftMargin=Ui.dp(activity,12);toolbar.addView(heading,headingParams);screen.addView(toolbar,new LinearLayout.LayoutParams(-1,LinearLayout.LayoutParams.WRAP_CONTENT));
        ScrollView scroll=new ScrollView(activity);scroll.setFillViewport(false);screen.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout content=Ui.column(activity);content.setPadding(Ui.dp(activity,16),Ui.dp(activity,6),Ui.dp(activity,16),Ui.dp(activity,24));scroll.addView(content);
        LinearLayout footer=Ui.column(activity);footer.setPadding(Ui.dp(activity,16),Ui.dp(activity,8),Ui.dp(activity,16),Ui.dp(activity,14));footer.setBackground(Ui.bordered(activity,Ui.SURFACE,Ui.BORDER,Ui.RADIUS_LARGE));
        LinearLayout setup=Ui.card(activity);content.addView(setup,Ui.margin(-1,-2,activity,0,0,0,12));
        setup.addView(Ui.title(activity,t("Como traduzir"),18));
        source=new EditText(activity);source.setText(prefs.getString("source","auto"));
        target=new EditText(activity);target.setText(prefs.getString("target","pt"));
        language(setup,"Idioma original",source,true);
        language(setup,"Idioma de destino",target,false);
        modePicker=choices(setup,"Modo",new String[]{t("IA local"),t("Minha IA")},prefs.getString("provider","local").equals("local")?0:1);modePicker.setVisibility(View.GONE);
        LinearLayout modeChoices=Ui.row(activity);localChoice=secondary(modeChoices,"IA local",()->modePicker.setSelection(0));remoteChoice=secondary(modeChoices,"Minha IA",()->modePicker.setSelection(1));setup.addView(modeChoices);
        localOptions=Ui.column(activity);setup.addView(localOptions);
        localOptions.addView(Ui.text(activity,t("A leitura guiada fornece os quadros. O texto e a tradução usam recursos locais do aparelho. Um idioma novo pode precisar de download."),13,Ui.MUTED));
        remoteOptions=Ui.column(activity);setup.addView(remoteOptions);
        String[] services=SERVICES.clone();services[6]=t("Compatível");
        servicePicker=choices(remoteOptions,"1. Escolha o serviço",services,serviceIndex(prefs.getString("provider","openai")));
        Button keyLink=Ui.button(activity,t("2. Obter chave oficial"),this::openKeyPage);remoteOptions.addView(keyLink);
        key=field(remoteOptions,"3. Cole a chave API","unused_key","");key.setText("");key.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
        LinearLayout security=Ui.row(activity);secondary(security,"Guardar chave",this::saveKey);button(security,"4. Testar conexão",this::test);remoteOptions.addView(security);
        remoteOptions.addView(Ui.text(activity,t("A API pode cobrar por uso. Assinatura de chat não inclui acesso à API. Se falhar, confira chave, saldo e modelo."),14,Ui.MUTED));
        remoteOptions.addView(Ui.text(activity,t("Enviamos texto detectado, idiomas, glossário e diálogos próximos. Se marcar imagem, enviamos também a página reduzida; isso pode custar mais."),14,Ui.MUTED));
        vision=new CheckBox(activity);vision.setText(t("Enviar imagem quando o modelo aceitar"));vision.setTextColor(Ui.TEXT);vision.setChecked(prefs.getBoolean("vision",false));remoteOptions.addView(vision);
        consent=new CheckBox(activity);consent.setText(t("Autorizo enviar esses dados"));consent.setTextColor(Ui.TEXT);remoteOptions.addView(consent);
        provider=new EditText(activity);provider.setText(prefs.getString("provider","local"));
        glossary=new EditText(activity);glossary.setText(prefs.getString("glossary","{}"));
        LinearLayout glossaryOptions=Ui.column(activity);
        termOriginal=field(glossaryOptions,"Original","unused_term_original","");termOriginal.setText("");
        termTranslation=field(glossaryOptions,"Tradução","unused_term_translation","");termTranslation.setText("");
        LinearLayout terms=Ui.row(activity);button(terms,"Adicionar / editar",this::addTerm);button(terms,"Remover",this::removeTerm);glossaryOptions.addView(terms);
        termPicker=choices(glossaryOptions,"Termos",new String[]{t("Nenhum termo")},0);refreshTerms();
        termPicker.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> parent){}public void onItemSelected(android.widget.AdapterView<?> parent,View v,int position,long id){selectTerm(position);}});
        advancedOptions=Ui.column(activity);
        remoteAdvanced=Ui.column(activity);advancedOptions.addView(remoteAdvanced);
        localAdvanced=Ui.column(activity);advancedOptions.addView(localAdvanced);
        model=field(remoteAdvanced,"Modelo","model","");
        script=new EditText(activity);script.setText("auto");
        endpoint=field(remoteAdvanced,"Endereço HTTPS personalizado","endpoint","");
        Button advanced=Ui.button(activity,t("Opções avançadas"),()->advancedOptions.setVisibility(advancedOptions.getVisibility()==View.VISIBLE?View.GONE:View.VISIBLE));advancedOptions.setVisibility(View.GONE);
        modePicker.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> parent){}public void onItemSelected(android.widget.AdapterView<?> parent,View v,int position,long id){updateMode();}});
        servicePicker.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> parent){}public void onItemSelected(android.widget.AdapterView<?> parent,View v,int position,long id){String old=provider.getText().toString();if(model.getText().length()==0||java.util.Arrays.asList(DEFAULT_MODELS).contains(model.getText().toString()))model.setText(DEFAULT_MODELS[position]);if(!old.equals(SERVICE_IDS[position])&&!old.equals("local"))endpoint.setText("");provider.setText(SERVICE_IDS[position]);}});
        updateMode();
        Button scopeToggle=Ui.button(activity,t("Página atual · alterar escopo"),()->{});content.addView(scopeToggle,Ui.margin(-1,Ui.dp(activity,48),activity,0,0,0,8));
        LinearLayout scopeOptions=Ui.card(activity);content.addView(scopeOptions,Ui.margin(-1,-2,activity,0,0,0,12));scopeOptions.setVisibility(View.GONE);
        scopeToggle.setOnClickListener(v->scopeOptions.setVisibility(scopeOptions.getVisibility()==View.VISIBLE?View.GONE:View.VISIBLE));
        scope=choices(scopeOptions,"Escopo",new String[]{t("Região selecionada"),t("Quadro atual"),t("Página atual"),t("HQ inteira")},2);
        scope.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> parent){}public void onItemSelected(android.widget.AdapterView<?> parent,View v,int position,long id){scopeToggle.setText(scope.getSelectedItem()+" · "+t("alterar escopo"));}});
        LinearLayout previewCard=Ui.card(activity);content.addView(previewCard,Ui.margin(-1,-2,activity,0,0,0,12));
        previewCard.addView(Ui.title(activity,t("Prévia da página"),18));
        previewCard.addView(Ui.text(activity,t("Use dois dedos para ampliar o resultado."),12,Ui.MUTED));
        view=choices(previewCard,"Visualização",new String[]{t("Original"),t("Traduzido"),t("Comparar")},Math.max(0,Math.min(2,prefs.getInt("view",0))));
        preview=new ZoomPage(activity,new ZoomPage.Actions(){public void next(){}public void previous(){}public void toggle(){}});
        preview.setBackground(Ui.bordered(activity,Ui.SURFACE_ALT,Ui.BORDER,Ui.RADIUS_MEDIUM));previewCard.addView(preview,Ui.margin(-1,Ui.dp(activity,300),activity,0,8,0,0));
        view.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> parent){}public void onItemSelected(android.widget.AdapterView<?> parent,View v,int position,long id){prefs.edit().putInt("view",position).apply();host.show(page,rows,position==1?"overlay":position==2?"compare":"original");preview.setTranslations(rows,position!=0);}});
        LinearLayout reviewOptions=Ui.card(activity);Button reviewToggle=Ui.button(activity,t("Revisar texto e correções"),()->reviewOptions.setVisibility(reviewOptions.getVisibility()==View.VISIBLE?View.GONE:View.VISIBLE));content.addView(reviewToggle,Ui.margin(-1,Ui.dp(activity,48),activity,0,0,0,8));content.addView(reviewOptions,Ui.margin(-1,-2,activity,0,0,0,12));reviewOptions.setVisibility(View.GONE);
        regionsSpinner=choices(reviewOptions,"Trecho da página",new String[]{t("Nenhum texto detectado")},0);
        LinearLayout detect=Ui.row(activity);secondary(detect,"Detectar texto",()->start(false));reviewOptions.addView(detect);
        status=Ui.text(activity,"",15,Ui.MUTED);footer.addView(status);
        LinearLayout actions=Ui.row(activity);Button translateAction=button(actions,"Traduzir",()->start(true));translateAction.setTextSize(17);cancelAction=secondary(actions,"Cancelar",()->cancel.set(true));cancelAction.setEnabled(false);footer.addView(actions);
        Button glossaryButton=Ui.button(activity,t("Glossário"),()->glossaryOptions.setVisibility(glossaryOptions.getVisibility()==View.VISIBLE?View.GONE:View.VISIBLE));content.addView(glossaryButton);content.addView(glossaryOptions);glossaryOptions.setVisibility(View.GONE);
        content.addView(advanced);content.addView(advancedOptions);
        original=field(reviewOptions,"Original / correção","unused_original","");original.setText("");original.setSingleLine(false);original.setMinLines(2);original.getLayoutParams().height=LinearLayout.LayoutParams.WRAP_CONTENT;
        translation=field(reviewOptions,"Tradução completa / correção","unused_translation","");translation.setText("");translation.setSingleLine(false);translation.setMinLines(3);translation.getLayoutParams().height=LinearLayout.LayoutParams.WRAP_CONTENT;
        regionsSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> parent){}public void onItemSelected(android.widget.AdapterView<?> parent,View v,int position,long id){if(position<rows.size()){original.setText(rows.get(position).original);translation.setText(rows.get(position).translated);}}});
        LinearLayout bottom=Ui.row(activity);secondary(bottom,"Salvar correções",this::saveCorrection);secondary(bottom,"Limpar cache",()->{if(running!=null&&!running.isDone())return;running=worker.submit(()->{ComicTranslation.clearCache(activity);activity.runOnUiThread(()->status.setText(t("Cache limpo. Correções preservadas.")));});});reviewOptions.addView(bottom);
        LinearLayout models=Ui.row(activity);secondary(models,"Remover modelo local",this::removeModel);localAdvanced.addView(models);
        screen.addView(footer,new LinearLayout.LayoutParams(-1,LinearLayout.LayoutParams.WRAP_CONTENT));dialog=new android.app.Dialog(activity);dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);dialog.setContentView(screen);dialog.setOnDismissListener(d->close());
        Window window=dialog.getWindow();if(window!=null){window.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));window.setLayout(WindowManager.LayoutParams.MATCH_PARENT,WindowManager.LayoutParams.MATCH_PARENT);}
        dialog.show();if(window!=null)window.setLayout(WindowManager.LayoutParams.MATCH_PARENT,WindowManager.LayoutParams.MATCH_PARENT);
        loadCached();
    }
    private static int serviceIndex(String value){for(int i=0;i<SERVICE_IDS.length;i++)if(SERVICE_IDS[i].equals(value))return i;return 0;}
    private void updateMode(){boolean remote=modePicker.getSelectedItemPosition()==1;localOptions.setVisibility(remote?View.GONE:View.VISIBLE);remoteOptions.setVisibility(remote?View.VISIBLE:View.GONE);if(remoteAdvanced!=null)remoteAdvanced.setVisibility(remote?View.VISIBLE:View.GONE);if(localAdvanced!=null)localAdvanced.setVisibility(remote?View.GONE:View.VISIBLE);provider.setText(remote?SERVICE_IDS[servicePicker.getSelectedItemPosition()]:"local");if(localChoice!=null&&remoteChoice!=null){localChoice.setBackground(Ui.bordered(activity,remote?Ui.SURFACE_ALT:0xff382027,remote?Ui.BORDER:Ui.RED,Ui.RADIUS_MEDIUM));remoteChoice.setBackground(Ui.bordered(activity,remote?0xff382027:Ui.SURFACE_ALT,remote?Ui.RED:Ui.BORDER,Ui.RADIUS_MEDIUM));localChoice.setTextColor(remote?Ui.MUTED:Color.WHITE);remoteChoice.setTextColor(remote?Color.WHITE:Ui.MUTED);}}
    private void openKeyPage(){String url=KEY_URLS[servicePicker.getSelectedItemPosition()];if(url.isEmpty()){advancedOptions.setVisibility(View.VISIBLE);status.setText(t("Informe o endereço e obtenha a chave no site oficial do serviço."));return;}activity.startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));}
    private JSONObject terms(){try{return new JSONObject(glossary.getText().toString());}catch(Exception e){return new JSONObject();}}
    private final List<String> termKeys=new ArrayList<>();
    private void refreshTerms(){JSONObject data=terms();termKeys.clear();java.util.Iterator<String> keys=data.keys();while(keys.hasNext())termKeys.add(keys.next());java.util.Collections.sort(termKeys,String.CASE_INSENSITIVE_ORDER);String[] labels=new String[termKeys.size()+1];labels[0]=t("Novo termo");for(int i=0;i<termKeys.size();i++)labels[i+1]=termKeys.get(i)+"  →  "+data.optString(termKeys.get(i));termPicker.setAdapter(readable(labels));}
    private void selectTerm(int position){if(position<=0||position>termKeys.size()){termOriginal.setText("");termTranslation.setText("");return;}String original=termKeys.get(position-1);termOriginal.setText(original);termTranslation.setText(terms().optString(original));}
    private void addTerm(){String original=termOriginal.getText().toString().trim(),translated=termTranslation.getText().toString().trim();if(original.isEmpty()||translated.isEmpty()){status.setText(t("Preencha os dois campos do glossário."));return;}JSONObject data=terms();int selected=termPicker.getSelectedItemPosition()-1;String previous=selected>=0&&selected<termKeys.size()?termKeys.get(selected):"";for(String key:termKeys)if(key.equalsIgnoreCase(original)&&!key.equals(previous)){status.setText(t("Esse termo já existe."));return;}if(!previous.isEmpty()&&!previous.equals(original))data.remove(previous);try{data.put(original,translated);}catch(Exception ignored){return;}glossary.setText(data.toString());settings();refreshTerms();termOriginal.setText("");termTranslation.setText("");status.setText(t("Termo salvo."));}
    private void removeTerm(){int index=termPicker.getSelectedItemPosition()-1;if(index<0||index>=termKeys.size())return;JSONObject data=terms();data.remove(termKeys.get(index));glossary.setText(data.toString());settings();refreshTerms();termOriginal.setText("");termTranslation.setText("");status.setText(t("Termo removido."));}
    private void close(){cancel.set(true);worker.shutdownNow();}
    private void settings(){updateMode();String p=provider.getText().toString().trim().toLowerCase(),m=model.getText().toString().trim(),from=source.getText().toString().trim().toLowerCase();String writing=from.equals("ja")?"ja":from.equals("zh")?"zh":from.equals("ko")?"ko":"auto";prefs.edit().putString("source",from).putString("target",target.getText().toString().trim()).putString("script",writing).putString("provider",p).putString("model",m).putString("endpoint",endpoint.getText().toString().trim()).putString("glossary",glossary.getText().toString().trim()).putBoolean("vision",vision.isChecked()&&ComicTranslation.supportsVision(p,m)).apply();}
    private String credential(String name)throws Exception{String entered=key.getText().toString().trim();return entered.isEmpty()?ComicTranslation.loadKey(activity,name):entered;}
    private void saveKey(){try{if(key.getText().toString().trim().isEmpty()){status.setText(t("Cole uma chave antes de guardar."));return;}ComicTranslation.saveKey(activity,provider.getText().toString().trim().toLowerCase(),key.getText().toString().trim());key.setText("");status.setText(t("Chave guardada no Android Keystore."));}catch(Exception e){failure(e);}}
    private void test(){if(running!=null&&!running.isDone())return;settings();String p=prefs.getString("provider","local"),m=prefs.getString("model","");if(p.equals("local")){status.setText(t("O modo local não usa chave API."));return;}String k;try{k=credential(p);}catch(Exception e){failure(e);return;}status.setText(t("Testando conexão..."));running=worker.submit(()->{try{ComicTranslation.testConnection(p,m,k,prefs.getString("endpoint",""));activity.runOnUiThread(()->status.setText(t("Conexão confirmada.")));}catch(Exception e){activity.runOnUiThread(()->failure(e));}});}
    private void loadCached(){settings();running=worker.submit(()->{try{Bitmap image=host.bitmap(page);List<ComicTranslation.Region> cached=ComicTranslation.read(activity,host.bookKey(),page,image,prefs.getString("source","auto"),prefs.getString("target","pt"),prefs.getString("provider","local"),prefs.getString("model",""),prefs.getString("endpoint",""),prefs.getString("glossary","{}"),prefs.getString("script","auto"),host.manga(),prefs.getBoolean("vision",false));activity.runOnUiThread(()->{if(dialog==null||!dialog.isShowing())return;preview.setImage(image);if(cached!=null)present(page,cached);});}catch(Exception ignored){}});}
    private void start(boolean translate){if(running!=null&&!running.isDone())return;settings();String p=prefs.getString("provider","local");if(translate&&!p.equals("local")&&!consent.isChecked()){status.setText(t("Autorize o envio antes de traduzir remotamente."));return;}try{new JSONObject(prefs.getString("glossary","{}"));}catch(Exception e){status.setText(t("Glossário JSON inválido."));return;}
        int selectedScope=scope.getSelectedItemPosition();if(selectedScope==1&&host.panel()==null){status.setText(t("Ative a leitura guiada para traduzir o quadro."));return;}if(selectedScope==0&&rows.isEmpty()){status.setText(t("Selecione uma região OCR."));return;}
        Runnable launch=()->{String k="";try{if(translate&&!p.equals("local"))k=credential(p);}catch(Exception e){failure(e);return;}final String finalKey=k;final int selected=regionsSpinner.getSelectedItemPosition();final RectF panel=host.panel();final boolean manga=host.manga();final int current=host.page(),count=host.count();cancel.set(false);cancelAction.setEnabled(true);status.setText(t("Processando..."));running=worker.submit(()->work(current,count,selectedScope,selected,panel,manga,translate,finalKey));};
        if(translate&&selectedScope==3&&!p.equals("local"))new AlertDialog.Builder(activity).setTitle(t("Confirmar custo")).setMessage(t("Traduzir a HQ inteira pode gerar cobranças da API. Continuar?")).setNegativeButton(t("Cancelar"),null).setPositiveButton(t("Continuar"),(d,w)->launch.run()).show();else launch.run();
    }
    private void work(int current,int count,int scope,int selected,RectF panel,boolean manga,boolean translate,String key){
        String from=prefs.getString("source","auto"),to=prefs.getString("target","pt"),p=prefs.getString("provider","local"),m=prefs.getString("model",""),custom=prefs.getString("endpoint",""),words=prefs.getString("glossary","{}");boolean sendImage=prefs.getBoolean("vision",false);
        int uncertainTotal=0;
        for(int n=0;n<(scope==3?count:1);n++){
            if(cancel.get())break;int at=n==0?current:(n<=current?n-1:n);final int step=n+1,totalSteps=scope==3?count:1;activity.runOnUiThread(()->status.setText(t("Lendo texto")+" · "+step+" / "+totalSteps));try{
                Bitmap image=host.bitmap(at);String script=prefs.getString("script","latin");List<ComicTranslation.Region> found=ComicTranslation.read(activity,host.bookKey(),at,image,from,to,p,m,custom,words,script,manga,sendImage);
                if(found==null){found=ComicTranslation.readOcr(activity,host.bookKey(),at,image,script,manga);if(found==null){found=ComicTranslation.ocr(image,script,manga,cancel);ComicTranslation.writeOcr(activity,host.bookKey(),at,image,script,manga,found);}}
                ComicTranslation.correct(activity,host.bookKey(),at,found);
                List<ComicTranslation.Region> chosen=new ArrayList<>();
                for(int i=0;i<found.size();i++){ComicTranslation.Region row=found.get(i);if(scope==0&&at==current&&i!=selected)continue;if(scope==1&&at==current&&panel!=null&&ComicTranslation.overlap(row.box,panel)<=0)continue;chosen.add(row);}
                if(translate&&!chosen.isEmpty()){activity.runOnUiThread(()->status.setText(t("Traduzindo")+" · "+step+" / "+totalSteps));if(p.equals("local"))uncertainTotal+=ComicTranslation.translateLocal(chosen,from,to,cancel,this::confirmLocalDownload);else for(int offset=0;offset<chosen.size();offset+=12){if(cancel.get())throw new InterruptedException("cancelled");ComicTranslation.translateRemote(chosen.subList(offset,Math.min(chosen.size(),offset+12)),found,from,to,p,m,key,custom,words,sendImage?image:null);ComicTranslation.write(activity,host.bookKey(),at,image,from,to,p,m,custom,words,script,manga,sendImage,found);}}
                ComicTranslation.write(activity,host.bookKey(),at,image,from,to,p,m,custom,words,script,manga,sendImage,found);
                final int progress=n+1,total=scope==3?count:1,pageAt=at,uncertain=uncertainTotal;final List<ComicTranslation.Region> output=found;
                activity.runOnUiThread(()->{if(dialog!=null&&dialog.isShowing()){if(pageAt==host.page())present(pageAt,output);status.setText(progress+" / "+total+(uncertain>0?" · "+uncertain+(I18n.language(activity).equals("en")?" source uncertain":" origem incerta"):""));}});
            }catch(Exception e){if(cancel.get())break;android.util.Log.w("KomicoveTranslation", "Page processing failed: "+e.getClass().getName()+(e instanceof ComicTranslation.Failure?"/"+((ComicTranslation.Failure)e).code:""));activity.runOnUiThread(()->failure(e));break;}
        }
        if(cancel.get())activity.runOnUiThread(()->{if(dialog!=null&&dialog.isShowing())status.setText(t("Cancelado. Páginas concluídas preservadas."));});
        activity.runOnUiThread(()->{if(cancelAction!=null)cancelAction.setEnabled(false);});
    }
    private void present(int p,List<ComicTranslation.Region> found){page=p;rows=found;String[] labels=new String[rows.size()==0?1:rows.size()];if(rows.isEmpty())labels[0]=t("Nenhum texto detectado");else for(int i=0;i<rows.size();i++)labels[i]=(rows.get(i).confidence<.65f?"? ":"")+rows.get(i).original;regionsSpinner.setAdapter(readable(labels));host.show(p,rows,view.getSelectedItemPosition()==1?"overlay":view.getSelectedItemPosition()==2?"compare":"original");if(preview!=null)preview.setTranslations(rows,view.getSelectedItemPosition()!=0);}
    private boolean confirmLocalDownload(String from,String to,int missing)throws Exception{
        java.util.concurrent.CountDownLatch answered=new java.util.concurrent.CountDownLatch(1);AtomicBoolean accepted=new AtomicBoolean();
        activity.runOnUiThread(()->{if(dialog==null||!dialog.isShowing()){answered.countDown();return;}new AlertDialog.Builder(activity).setTitle(t("Baixar idiomas para tradução"))
            .setMessage(t(missing==1?"É preciso baixar um idioma de cerca de 30 MB pelo Wi-Fi. Você pode cancelar a espera. Continuar?":"É preciso baixar dois idiomas de cerca de 30 MB cada pelo Wi-Fi. Você pode cancelar a espera. Continuar?"))
            .setNegativeButton(t("Cancelar"),(d,w)->answered.countDown())
            .setPositiveButton(t("Baixar"),(d,w)->{accepted.set(true);status.setText(t("Baixando idiomas pelo Wi-Fi..."));answered.countDown();})
            .setOnCancelListener(d->answered.countDown()).show();});
        while(!answered.await(100,TimeUnit.MILLISECONDS))if(cancel.get())return false;
        if(!accepted.get())cancel.set(true);
        return accepted.get()&&!cancel.get();
    }
    private void saveCorrection(){if(rows.isEmpty())return;int i=Math.max(0,Math.min(rows.size()-1,regionsSpinner.getSelectedItemPosition()));ComicTranslation.Region row=rows.get(i);String o=original.getText().toString(),tr=translation.getText().toString(),old=row.translated;if(!o.equals(row.original)){row.original=o;row.manualOriginal=true;if(!row.manualTranslation){row.translated="";row.translationAttempted=false;}}if(!tr.equals(old)){row.translated=tr;row.manualTranslation=true;row.translationAttempted=true;}try{ComicTranslation.saveCorrection(activity,host.bookKey(),page,row);present(page,rows);status.setText(t("Correção salva."));}catch(Exception e){failure(e);}}
    private void removeModel(){if(running!=null&&!running.isDone())return;EditText language=new EditText(activity);language.setHint(t("Idioma do modelo (en, pt, ja...)"));new AlertDialog.Builder(activity).setTitle(t("Remover modelo local")).setView(language).setNegativeButton(t("Cancelar"),null).setPositiveButton(t("Remover"),(d,w)->{running=worker.submit(()->{try{ComicTranslation.removeModel(language.getText().toString().trim());activity.runOnUiThread(()->status.setText(t("Modelo removido.")));}catch(Exception e){activity.runOnUiThread(()->failure(e));}});}).show();}
    private void failure(Exception error){String code=error instanceof ComicTranslation.Failure?((ComicTranslation.Failure)error).code:error instanceof java.util.concurrent.TimeoutException?"timeout":"processing_failed";String[] pair;
        switch(code){case "authentication":pair=new String[]{"Autenticação recusada.","Authentication failed."};break;case "quota_or_rate_limit":pair=new String[]{"Quota ou limite atingido.","Quota or rate limit reached."};break;case "timeout":pair=new String[]{"Tempo de resposta esgotado.","Request timed out."};break;case "model_or_request_incompatible":pair=new String[]{"Modelo incompatível.","Incompatible model."};break;case "unsupported_language":pair=new String[]{"Idioma não suportado pelo modelo local.","Language unsupported by local model."};break;case "source_unknown":pair=new String[]{"Não foi possível detectar o idioma. Selecione a origem.","Could not detect the language. Select the source."};break;case "local_download_failed":pair=new String[]{"Não foi possível baixar o idioma. Conecte ao Wi-Fi e tente novamente.","Could not download the language. Connect to Wi-Fi and try again."};break;case "invalid_endpoint":pair=new String[]{"Endpoint HTTPS inválido.","Invalid HTTPS endpoint."};break;case "key_or_model_missing":pair=new String[]{"Informe chave API e modelo.","Enter an API key and model."};break;case "network":pair=new String[]{"Falha de rede.","Network failure."};break;case "invalid_provider_response":pair=new String[]{"Resposta inválida do provedor.","Invalid provider response."};break;default:pair=new String[]{"Não foi possível processar.","Could not process."};}
        if(status!=null)status.setText(I18n.language(activity).equals("en")?pair[1]:pair[0]);
    }
}

package com.lucrazy.komicove;

import android.app.*;
import android.os.*;
import android.graphics.*;
import android.view.*;
import android.widget.*;
import android.util.LruCache;
import org.json.*;
import java.util.concurrent.*;

public final class ReaderActivity extends Activity {
    private LibraryStore store;private LibraryStore.Book book;private BookSource source;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();private volatile boolean destroyed;
    private final LruCache<Integer,Bitmap> cache=new LruCache<Integer,Bitmap>(24*1024*1024){protected int sizeOf(Integer key,Bitmap value){return value.getAllocationByteCount();}};
    private LinearLayout root,top,bottom;private FrameLayout canvas;private TextView status;private SeekBar progress;private ZoomPage pageView;private ListView vertical;
    private Button overviewButton;private boolean overview=false,loading=true;private int displayedPage=-1;private int index,generation,step=1;private boolean controls=true,initial=true;private boolean persistZoom=true,autoFit=true;private String mode;private float savedZoom,savedX,savedY;private long readingStarted;
    @Override public void onCreate(Bundle saved){super.onCreate(saved);readingStarted=System.currentTimeMillis();store=new LibraryStore(this);android.content.SharedPreferences prefs=getSharedPreferences("reader",0);persistZoom=prefs.getBoolean("persist_zoom",true);autoFit=prefs.getBoolean("auto_fit",true);book=store.get(getIntent().getStringExtra("book"));if(book==null){finish();return;}index=book.page;mode=book.mode;savedZoom=book.zoom;savedX=book.offsetX;savedY=book.offsetY;
        root=Ui.column(this);root.setBackgroundColor(0xff09090b);setContentView(root);Ui.insets(this,root);
        top=Ui.row(this);Ui.pad(top,2);top.addView(navigationButton("‹",this::finish,"Voltar à biblioteca"));TextView name=Ui.title(this,book.title,14);name.setMaxLines(1);name.setEllipsize(android.text.TextUtils.TruncateAt.END);top.addView(name,new LinearLayout.LayoutParams(0,-2,1));overviewButton=compactButton("Encaixar",this::toggleOverview,"Mostrar página inteira");top.addView(overviewButton);top.addView(compactButton("⋮",this::readerMenu,"Opções do leitor"));root.addView(top);

        canvas=new FrameLayout(this);root.addView(canvas,new LinearLayout.LayoutParams(-1,0,1));
        bottom=Ui.column(this);Ui.pad(bottom,2);LinearLayout nav=Ui.row(this);nav.addView(navigationButton("‹",()->move(-1),"Anterior"));status=Ui.text(this,"Abrindo…",14,Ui.MUTED);status.setGravity(Gravity.CENTER);nav.addView(status,new LinearLayout.LayoutParams(0,-2,1));nav.addView(navigationButton("›",()->move(1),"Próximo"));bottom.addView(nav);progress=new SeekBar(this);progress.setContentDescription(I18n.t(this,"Ir para página"));bottom.addView(progress,new LinearLayout.LayoutParams(-1,Ui.dp(this,32)));root.addView(bottom);
        progress.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar s){}public void onStopTrackingTouch(SeekBar s){jump(s.getProgress());}public void onProgressChanged(SeekBar s,int n,boolean user){if(user)status.setText(I18n.t(ReaderActivity.this,"Página ")+(n+1)+" / "+book.count);}});
        worker.execute(()->{try{BookSource opened=new BookSource(store.file(book),getCacheDir());if(destroyed){opened.close();return;}source=opened;runOnUiThread(()->{if(destroyed)return;book.count=source.pages.size();index=Math.min(index,book.count-1);progress.setMax(book.count-1);setupMode();});}catch(Exception e){runOnUiThread(()->{if(!destroyed)new AlertDialog.Builder(this).setTitle("Não foi possível abrir").setMessage(error(e)).setPositiveButton("Voltar",(d,w)->finish()).setOnCancelListener(d->finish()).show();});}});
    }
    private boolean guidedFallback;private boolean guided; private int panelIndex; private java.util.List<RectF> panels=java.util.Collections.emptyList();
    private Button compactButton(String label,Runnable action,String description){
        Button b=Ui.button(this,label,action);b.setTextSize(12);b.setMinWidth(0);b.setMinimumWidth(0);b.setPadding(Ui.dp(this,8),0,Ui.dp(this,8),0);b.setLayoutParams(new LinearLayout.LayoutParams(-2,Ui.dp(this,48)));b.setContentDescription(I18n.t(this,description));return b;
    }
    private Button navigationButton(String label,Runnable action,String description){
        Button b=compactButton(label,action,description);b.setTextSize(28);b.setLayoutParams(new LinearLayout.LayoutParams(Ui.dp(this,64),Ui.dp(this,56)));return b;
    }
    private void readerMenu(){
        new AlertDialog.Builder(this).setTitle("Leitor").setItems(new String[]{"Modo de leitura","Páginas","Marcadores","Editar quadros","Preferências"},(d,i)->{
            if(i==0)chooseMode();else if(i==1)thumbnails();else if(i==2)bookmarks();else if(i==3)editPanels();else preferences();
        }).show();
    }
    private void preferences(){
        ReaderPreferences.show(this,()->{
            android.content.SharedPreferences p=getSharedPreferences("reader",0);
            persistZoom=p.getBoolean("persist_zoom",true);autoFit=p.getBoolean("auto_fit",true);
            if(source!=null){initial=true;setupMode();}
        });
    }
    private void focusPanel(){focusPanel(false);}
    private void focusPanel(boolean animate){
        if(pageView!=null&&!panels.isEmpty()){if(overview)pageView.overview(panels.get(panelIndex));else {pageView.clearOverview();pageView.focus(panels.get(panelIndex),animate&&getSharedPreferences("reader",0).getBoolean("animate_guided",true));}}
        overviewButton.setText(I18n.t(this,overview?"Voltar ao quadro":guided?"Página inteira":"Encaixar"));
        overviewButton.setContentDescription(I18n.t(this,overview?"Voltar ao quadro selecionado":"Mostrar página inteira"));
        updateCounter();
    }
    private void toggleOverview(){
        if(loading||pageView==null)return;
        if(guided&&!panels.isEmpty()){overview=!overview;focusPanel();}
        else pageView.fitToScreen();
    }
    private String error(Exception e){String msg=e.getMessage();return msg==null?"Arquivo incompatível ou danificado.":msg;}
    private void setupMode(){guided=false;overview=false;panels=java.util.Collections.emptyList();generation++;canvas.removeAllViews();pageView=null;vertical=null;
        if(mode.equals("vertical")){loading=false;overviewButton.setText(I18n.t(this,"Encaixar"));overviewButton.setEnabled(false);vertical=new ListView(this);vertical.setDividerHeight(Ui.dp(this,6));vertical.setAdapter(new PagesAdapter(false));vertical.setOnScrollListener(new AbsListView.OnScrollListener(){public void onScrollStateChanged(AbsListView v,int state){if(state==SCROLL_STATE_IDLE)save();}public void onScroll(AbsListView v,int first,int visible,int total){if(total>0){index=first;updateCounter();}}});canvas.addView(vertical);vertical.setSelection(index);updateCounter();}
        else {pageView=new ZoomPage(this,new ZoomPage.Actions(){public void next(){move(mode.equals("manga")?-1:1);}public void previous(){move(mode.equals("manga")?1:-1);}public void toggle(){toggleControls();}});canvas.addView(pageView);loadPage();}
    }
    private Bitmap bitmap(int n)throws Exception {Bitmap b=cache.get(n);if(b==null){b=source.page(n,1600);cache.put(n,b);}return b;}
    private java.util.List<RectF> customPanels(int page){JSONArray a=book.customPanels.optJSONArray(String.valueOf(page));if(a==null)return null;java.util.List<RectF> out=new java.util.ArrayList<>();for(int i=0;i<a.length();i++){JSONArray r=a.optJSONArray(i);if(r!=null&&r.length()==4)out.add(new RectF((float)r.optDouble(0),(float)r.optDouble(1),(float)r.optDouble(2),(float)r.optDouble(3)));}return out.isEmpty()?null:out;}
    private void saveCustomPanels(int page,java.util.List<RectF> list){try{JSONArray all=new JSONArray();for(RectF r:list)all.put(new JSONArray().put(r.left).put(r.top).put(r.right).put(r.bottom));book.customPanels.put(String.valueOf(page),all);store.save(book);}catch(JSONException e){Toast.makeText(this,"Não foi possível salvar os quadros.",Toast.LENGTH_LONG).show();}}
    private void editPanels(){if(source==null||mode.equals("vertical")||mode.equals("dupla")){Toast.makeText(this,"Use o modo de página única para editar quadros.",Toast.LENGTH_LONG).show();return;}int page=index;worker.execute(()->{try{Bitmap image=bitmap(page);java.util.List<RectF> automatic=PanelDetector.detect(image,mode.equals("manga"));if(automatic.size()==1)automatic=PanelDetector.readingRegions(image.getWidth(),image.getHeight(),mode.equals("manga"));java.util.List<RectF> saved=customPanels(page);java.util.List<RectF> initialPanels=saved==null?automatic:saved;java.util.List<RectF> detected=automatic;runOnUiThread(()->showPanelEditor(page,image,initialPanels,detected));}catch(Exception e){runOnUiThread(()->Toast.makeText(this,error(e),Toast.LENGTH_LONG).show());}});}
    private void showPanelEditor(int page,Bitmap image,java.util.List<RectF> initialPanels,java.util.List<RectF> automatic){LinearLayout box=Ui.column(this);box.addView(Ui.text(this,"Arraste no vazio para criar. Arraste um quadro ou seus cantos para ajustar.",13,Ui.MUTED));PanelEditorView editor=new PanelEditorView(this,image,initialPanels);box.addView(editor,new LinearLayout.LayoutParams(-1,Ui.dp(this,480)));LinearLayout actions=Ui.row(this);actions.addView(Ui.button(this,"Excluir",editor::deleteSelected));actions.addView(Ui.button(this,"◀ Ordem",()->editor.reorder(-1)));actions.addView(Ui.button(this,"Ordem ▶",()->editor.reorder(1)));actions.addView(Ui.button(this,"Redetectar",()->{editor.panels.clear();for(RectF r:automatic)editor.panels.add(new RectF(r));editor.selected=-1;editor.invalidate();}));box.addView(actions);android.app.AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Editor manual de quadros").setView(box).setPositiveButton("Salvar",null).setNegativeButton("Cancelar",null).create();dialog.setOnShowListener(x->dialog.getButton(-1).setOnClickListener(v->{if(editor.panels.isEmpty()){Toast.makeText(this,"Crie pelo menos um quadro.",Toast.LENGTH_SHORT).show();return;}saveCustomPanels(page,editor.panels);dialog.dismiss();generation++;loadPage();}));dialog.show();}
    private void loadPage(){loading=true;overviewButton.setEnabled(false);int ticket=++generation,n=index;status.setText(I18n.t(this,"Carregando página ")+(n+1)+"…");String readMode=mode;guided=getSharedPreferences("reader",0).getBoolean("guided",false)&&!mode.equals("vertical")&&!mode.equals("dupla");boolean guide=guided;
        worker.execute(()->{try{Bitmap image=bitmap(n);int displayedStep=1;
            if(readMode.equals("dupla")&&image.getWidth()<image.getHeight()&&n>0&&n+1<book.count){Bitmap right=bitmap(n+1);if(right.getWidth()<right.getHeight()){int height=Math.min(image.getHeight(),right.getHeight());int leftWidth=image.getWidth()*height/image.getHeight(),rightWidth=right.getWidth()*height/right.getHeight();Bitmap pair=Bitmap.createBitmap(leftWidth+rightWidth,height,Bitmap.Config.RGB_565);Canvas c=new Canvas(pair);c.drawColor(Color.BLACK);Paint p=new Paint(Paint.FILTER_BITMAP_FLAG);c.drawBitmap(image,null,new Rect(0,0,leftWidth,height),p);c.drawBitmap(right,null,new Rect(leftWidth,0,leftWidth+rightWidth,height),p);image=pair;displayedStep=2;}}
            java.util.List<RectF> manual=guide?customPanels(n):null;java.util.List<RectF> detected=guide?(manual!=null?manual:PanelDetector.detect(image,readMode.equals("manga"))):java.util.Collections.emptyList();boolean fallback=guide&&manual==null&&detected.size()==1;if(fallback)detected=PanelDetector.readingRegions(image.getWidth(),image.getHeight(),readMode.equals("manga"));java.util.List<RectF> regions=detected;Bitmap output=image;int span=displayedStep;runOnUiThread(()->{if(destroyed||ticket!=generation||pageView==null)return;step=span;float keepZoom=pageView.zoom,keepX=pageView.normalizedX(),keepY=pageView.normalizedY();pageView.setImage(output);if(initial){if(autoFit)pageView.fitToScreen();else if(persistZoom)pageView.restore(savedZoom,savedX,savedY);initial=false;}else if(persistZoom)pageView.restore(keepZoom,keepX,keepY);else pageView.fitToScreen();panels=regions;guidedFallback=fallback;panelIndex=guide&&book.guidedPage==n?Math.max(0,Math.min(book.guidedPanel,panels.size()-1)):0;displayedPage=n;loading=false;overviewButton.setEnabled(true);overviewButton.setText(I18n.t(this,guide?(overview?"Voltar ao quadro":"Página inteira"):"Encaixar"));if(guide)pageView.post(()->{if(!destroyed&&ticket==generation)focusPanel();});Ui.enter(pageView);updateCounter();save();});
            if(n+1<book.count&&!destroyed&&ticket==generation)bitmap(n+1);
        }catch(Exception e){runOnUiThread(()->{if(!destroyed&&ticket==generation){status.setText(I18n.t(this,"Página indisponível"));Toast.makeText(this,error(e),Toast.LENGTH_LONG).show();}});}});
    }
    private void updateCounter(){status.setText((index+1)+" / "+book.count+" · "+Math.round((index+1)*100f/book.count)+"%");if(guided&&!panels.isEmpty())status.append(I18n.t(this,guidedFallback?" · Trecho ":" · Quadro ")+(panelIndex+1)+"/"+panels.size());progress.setProgress(index);}
    private void move(int direction){if(loading)return;if(guided&&panelIndex+direction>=0&&panelIndex+direction<panels.size()){panelIndex+=direction;focusPanel(true);save();return;}jump(index+direction*(mode.equals("dupla")?step:1));}
    private void offerNextIssue(){save();LibraryStore.Book next=store.nextIssue(book);android.app.AlertDialog.Builder dialog=new AlertDialog.Builder(this).setTitle("HQ concluída!").setMessage(next==null?"Você chegou ao final.":"Continuar com "+next.title+": edição "+next.issue+"?").setNegativeButton("Ficar aqui",null).setNeutralButton("Biblioteca",(d,w)->finish());if(next!=null)dialog.setPositiveButton(I18n.t(this,"Próxima edição"),(d,w)->{startActivity(new android.content.Intent(this,ReaderActivity.class).putExtra("book",next.id));finish();});dialog.show();}
    private void jump(int n){if(source==null)return;if(n<0||n>=book.count){if(n>=book.count)offerNextIssue();else Toast.makeText(this,"Início do quadrinho",Toast.LENGTH_SHORT).show();return;}index=n;initial=false;if(vertical!=null){vertical.setSelection(n);updateCounter();save();}else loadPage();}
    private void chooseMode(){if(source==null)return;String[] names={"Página única","Modo mangá (direita → esquerda)","Página dupla inteligente","Leitura vertical"};String[] values={"normal","manga","dupla","vertical"};new AlertDialog.Builder(this).setTitle("Como você quer ler?").setItems(names,(d,n)->{save();mode=values[n];book.mode=mode;initial=false;setupMode();save();}).show();}
    private void toggleControls(){controls=!controls;top.setVisibility(controls?View.VISIBLE:View.GONE);bottom.setVisibility(controls?View.VISIBLE:View.GONE);getWindow().getDecorView().setSystemUiVisibility(controls?0:View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);}
    private void thumbnails(){if(source==null)return;ListView list=new ListView(this);list.setAdapter(new PagesAdapter(true));android.app.AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Escolher página").setView(list).setNegativeButton("Fechar",null).create();list.setOnItemClickListener((p,v,n,id)->{dialog.dismiss();jump(n);});dialog.show();list.setSelection(index);}
    private void bookmarks(){if(source==null)return;String[] labels=new String[book.marks.length()+1];labels[0]="Marcar / desmarcar página "+(index+1);for(int i=0;i<book.marks.length();i++)labels[i+1]="Página "+(book.marks.optInt(i)+1);new AlertDialog.Builder(this).setTitle("Marcadores").setItems(labels,(d,n)->{if(n>0){jump(book.marks.optInt(n-1));return;}JSONArray next=new JSONArray();boolean found=false;for(int i=0;i<book.marks.length();i++){int p=book.marks.optInt(i);if(p==index)found=true;else next.put(p);}if(!found)next.put(index);book.marks=next;save();Toast.makeText(this,found?"Marcador removido":"Página marcada",Toast.LENGTH_SHORT).show();}).show();}
    private void save(){if(book==null||source==null||loading)return;book.page=index;boolean seen=false;for(int i=0;i<book.readPages.length();i++)if(book.readPages.optInt(i)==index)seen=true;if(!seen)book.readPages.put(index);if(book.count>0&&index>=book.count-1)book.completed=true;if(guided&&displayedPage==index&&!panels.isEmpty()){book.guidedPage=index;book.guidedPanel=panelIndex;}book.mode=mode;if(pageView!=null&&!guided){book.zoom=persistZoom?pageView.zoom:1;book.offsetX=persistZoom?pageView.normalizedX():0;book.offsetY=persistZoom?pageView.normalizedY():0;}book.updated=System.currentTimeMillis()/1000.0;store.save(book);}
    @Override protected void onResume(){super.onResume();readingStarted=System.currentTimeMillis();}
    @Override protected void onPause(){if(book!=null){book.readingSeconds+=Math.max(0,Math.min(21600,(System.currentTimeMillis()-readingStarted)/1000));}save();super.onPause();}
    @Override protected void onDestroy(){destroyed=true;generation++;worker.execute(()->{if(source!=null)source.close();store.release(book);cache.evictAll();});worker.shutdown();super.onDestroy();}
    @Override public boolean onKeyDown(int code,KeyEvent event){if(code==KeyEvent.KEYCODE_V){if(event.getRepeatCount()==0)toggleOverview();return true;}if(code==KeyEvent.KEYCODE_VOLUME_DOWN||code==KeyEvent.KEYCODE_DPAD_RIGHT){move(1);return true;}if(code==KeyEvent.KEYCODE_VOLUME_UP||code==KeyEvent.KEYCODE_DPAD_LEFT){move(-1);return true;}return super.onKeyDown(code,event);}
    private final class PagesAdapter extends BaseAdapter {
        private final boolean thumbs;PagesAdapter(boolean t){thumbs=t;}
        public int getCount(){return book.count;}public Object getItem(int n){return n;}public long getItemId(int n){return n;}
        public View getView(int n,View recycled,android.view.ViewGroup parent){
            LinearLayout cell;
            if(recycled instanceof LinearLayout)cell=(LinearLayout)recycled;
            else {cell=Ui.column(ReaderActivity.this);TextView label=Ui.text(ReaderActivity.this,"",14,Ui.MUTED);label.setGravity(Gravity.CENTER);cell.addView(label);ImageView image=new ImageView(ReaderActivity.this);image.setAdjustViewBounds(true);image.setScaleType(ImageView.ScaleType.FIT_CENTER);cell.addView(image,new LinearLayout.LayoutParams(-1,Ui.dp(ReaderActivity.this,thumbs?160:400)));}
            TextView label=(TextView)cell.getChildAt(0);ImageView image=(ImageView)cell.getChildAt(1);
            label.setText(I18n.t(ReaderActivity.this,"Página ")+(n+1));image.setContentDescription(I18n.t(ReaderActivity.this,"Página ")+(n+1));image.setImageDrawable(null);image.getLayoutParams().height=Ui.dp(ReaderActivity.this,thumbs?160:400);
            Object binding=new Object();image.setTag(binding);int ticket=generation;
            worker.execute(()->{if(destroyed||ticket!=generation||image.getTag()!=binding)return;try{Bitmap b=source.page(n,thumbs?250:1200);runOnUiThread(()->{if(destroyed||ticket!=generation||image.getTag()!=binding)return;image.setImageBitmap(b);if(!thumbs){image.getLayoutParams().height=-2;image.requestLayout();}});}catch(Exception e){runOnUiThread(()->{if(!destroyed&&image.getTag()==binding)label.setText(I18n.t(ReaderActivity.this,"Página ")+(n+1)+I18n.t(ReaderActivity.this," indisponível"));});}});return cell;
        }
    }
}

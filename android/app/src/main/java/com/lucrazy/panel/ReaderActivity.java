package com.lucrazy.panel;

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
    private int index,generation,step=1;private boolean controls=true,initial=true;private String mode;private float savedZoom,savedX,savedY;
    @Override public void onCreate(Bundle saved){super.onCreate(saved);store=new LibraryStore(this);book=store.get(getIntent().getStringExtra("book"));if(book==null){finish();return;}index=book.page;mode=book.mode;savedZoom=book.zoom;savedX=book.offsetX;savedY=book.offsetY;
        root=Ui.column(this);root.setBackgroundColor(0xff09090b);setContentView(root);Ui.insets(this,root);
        top=Ui.column(this);Ui.pad(top,10);LinearLayout title=Ui.row(this);title.addView(Ui.button(this,"‹ Biblioteca",this::finish));TextView name=Ui.title(this,book.title,16);name.setMaxLines(1);name.setEllipsize(android.text.TextUtils.TruncateAt.END);title.addView(name,new LinearLayout.LayoutParams(0,-2,1));top.addView(title);
        LinearLayout actions=Ui.row(this);actions.addView(Ui.button(this,"Modo",this::chooseMode),new LinearLayout.LayoutParams(0,-2,1));actions.addView(Ui.button(this,"Páginas",this::thumbnails),new LinearLayout.LayoutParams(0,-2,1));actions.addView(Ui.button(this,"Marcadores",this::bookmarks),new LinearLayout.LayoutParams(0,-2,1));top.addView(actions);root.addView(top);
        canvas=new FrameLayout(this);root.addView(canvas,new LinearLayout.LayoutParams(-1,0,1));
        bottom=Ui.column(this);Ui.pad(bottom,10);LinearLayout nav=Ui.row(this);nav.addView(Ui.button(this,"‹",()->move(-1)));status=Ui.text(this,"Abrindo…",14,Ui.MUTED);status.setGravity(Gravity.CENTER);nav.addView(status,new LinearLayout.LayoutParams(0,-2,1));nav.addView(Ui.button(this,"›",()->move(1)));bottom.addView(nav);progress=new SeekBar(this);progress.setContentDescription("Ir para página");bottom.addView(progress);root.addView(bottom);
        progress.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar s){}public void onStopTrackingTouch(SeekBar s){jump(s.getProgress());}public void onProgressChanged(SeekBar s,int n,boolean user){if(user)status.setText("Página "+(n+1)+" / "+book.count);}});
        worker.execute(()->{try{BookSource opened=new BookSource(store.file(book),getCacheDir());if(destroyed){opened.close();return;}source=opened;runOnUiThread(()->{if(destroyed)return;book.count=source.pages.size();index=Math.min(index,book.count-1);progress.setMax(book.count-1);setupMode();});}catch(Exception e){runOnUiThread(()->{if(!destroyed)new AlertDialog.Builder(this).setTitle("Não foi possível abrir").setMessage(error(e)).setPositiveButton("Voltar",(d,w)->finish()).setOnCancelListener(d->finish()).show();});}});
    }
    private String error(Exception e){String msg=e.getMessage();return msg==null?"Arquivo incompatível ou danificado.":msg;}
    private void setupMode(){generation++;canvas.removeAllViews();pageView=null;vertical=null;
        if(mode.equals("vertical")){vertical=new ListView(this);vertical.setDividerHeight(Ui.dp(this,6));vertical.setAdapter(new PagesAdapter(false));vertical.setOnScrollListener(new AbsListView.OnScrollListener(){public void onScrollStateChanged(AbsListView v,int state){if(state==SCROLL_STATE_IDLE)save();}public void onScroll(AbsListView v,int first,int visible,int total){if(total>0){index=first;updateCounter();}}});canvas.addView(vertical);vertical.setSelection(index);updateCounter();}
        else {pageView=new ZoomPage(this,new ZoomPage.Actions(){public void next(){move(mode.equals("manga")?-1:1);}public void previous(){move(mode.equals("manga")?1:-1);}public void toggle(){toggleControls();}});canvas.addView(pageView);loadPage();}
    }
    private Bitmap bitmap(int n)throws Exception {Bitmap b=cache.get(n);if(b==null){b=source.page(n,1600);cache.put(n,b);}return b;}
    private void loadPage(){int ticket=++generation,n=index;status.setText("Carregando página "+(n+1)+"…");String readMode=mode;
        worker.execute(()->{try{Bitmap image=bitmap(n);int displayedStep=1;
            if(readMode.equals("dupla")&&image.getWidth()<image.getHeight()&&n>0&&n+1<book.count){Bitmap right=bitmap(n+1);if(right.getWidth()<right.getHeight()){int height=Math.min(image.getHeight(),right.getHeight());int leftWidth=image.getWidth()*height/image.getHeight(),rightWidth=right.getWidth()*height/right.getHeight();Bitmap pair=Bitmap.createBitmap(leftWidth+rightWidth,height,Bitmap.Config.RGB_565);Canvas c=new Canvas(pair);c.drawColor(Color.BLACK);Paint p=new Paint(Paint.FILTER_BITMAP_FLAG);c.drawBitmap(image,null,new Rect(0,0,leftWidth,height),p);c.drawBitmap(right,null,new Rect(leftWidth,0,leftWidth+rightWidth,height),p);image=pair;displayedStep=2;}}
            Bitmap output=image;int span=displayedStep;runOnUiThread(()->{if(destroyed||ticket!=generation||pageView==null)return;step=span;pageView.setImage(output);if(initial){pageView.restore(savedZoom,savedX,savedY);initial=false;}else pageView.restore(1,0,0);Ui.enter(pageView);updateCounter();save();});
            if(n+1<book.count&&!destroyed&&ticket==generation)bitmap(n+1);
        }catch(Exception e){runOnUiThread(()->{if(!destroyed&&ticket==generation){status.setText("Página indisponível");Toast.makeText(this,error(e),Toast.LENGTH_LONG).show();}});}});
    }
    private void updateCounter(){status.setText((index+1)+" / "+book.count+" · "+Math.round((index+1)*100f/book.count)+"%");progress.setProgress(index);}
    private void move(int direction){jump(index+direction*(mode.equals("dupla")?step:1));}
    private void jump(int n){if(source==null)return;if(n<0||n>=book.count){Toast.makeText(this,n<0?"Início do quadrinho":"Você chegou ao final!",Toast.LENGTH_SHORT).show();return;}index=n;initial=false;if(vertical!=null){vertical.setSelection(n);updateCounter();save();}else loadPage();}
    private void chooseMode(){if(source==null)return;String[] names={"Página única","Modo mangá (direita → esquerda)","Página dupla inteligente","Leitura vertical"};String[] values={"normal","manga","dupla","vertical"};new AlertDialog.Builder(this).setTitle("Como você quer ler?").setItems(names,(d,n)->{save();mode=values[n];book.mode=mode;initial=false;setupMode();save();}).show();}
    private void toggleControls(){controls=!controls;top.setVisibility(controls?View.VISIBLE:View.GONE);bottom.setVisibility(controls?View.VISIBLE:View.GONE);getWindow().getDecorView().setSystemUiVisibility(controls?0:View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);}
    private void thumbnails(){if(source==null)return;ListView list=new ListView(this);list.setAdapter(new PagesAdapter(true));AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Escolher página").setView(list).setNegativeButton("Fechar",null).create();list.setOnItemClickListener((p,v,n,id)->{dialog.dismiss();jump(n);});dialog.show();list.setSelection(index);}
    private void bookmarks(){if(source==null)return;String[] labels=new String[book.marks.length()+1];labels[0]="Marcar / desmarcar página "+(index+1);for(int i=0;i<book.marks.length();i++)labels[i+1]="Página "+(book.marks.optInt(i)+1);new AlertDialog.Builder(this).setTitle("Marcadores").setItems(labels,(d,n)->{if(n>0){jump(book.marks.optInt(n-1));return;}JSONArray next=new JSONArray();boolean found=false;for(int i=0;i<book.marks.length();i++){int p=book.marks.optInt(i);if(p==index)found=true;else next.put(p);}if(!found)next.put(index);book.marks=next;save();Toast.makeText(this,found?"Marcador removido":"Página marcada",Toast.LENGTH_SHORT).show();}).show();}
    private void save(){if(book==null||source==null)return;book.page=index;book.mode=mode;if(pageView!=null){book.zoom=pageView.zoom;book.offsetX=pageView.normalizedX();book.offsetY=pageView.normalizedY();}book.updated=System.currentTimeMillis()/1000.0;store.save(book);}
    @Override protected void onPause(){save();super.onPause();}
    @Override protected void onDestroy(){destroyed=true;generation++;worker.execute(()->{if(source!=null)source.close();cache.evictAll();});worker.shutdown();super.onDestroy();}
    @Override public boolean onKeyDown(int code,KeyEvent event){if(code==KeyEvent.KEYCODE_VOLUME_DOWN||code==KeyEvent.KEYCODE_DPAD_RIGHT){move(1);return true;}if(code==KeyEvent.KEYCODE_VOLUME_UP||code==KeyEvent.KEYCODE_DPAD_LEFT){move(-1);return true;}return super.onKeyDown(code,event);}
    private final class PagesAdapter extends BaseAdapter {
        private final boolean thumbs;PagesAdapter(boolean t){thumbs=t;}
        public int getCount(){return book.count;}public Object getItem(int n){return n;}public long getItemId(int n){return n;}
        public View getView(int n,View recycled,android.view.ViewGroup parent){
            LinearLayout cell;
            if(recycled instanceof LinearLayout)cell=(LinearLayout)recycled;
            else {cell=Ui.column(ReaderActivity.this);TextView label=Ui.text(ReaderActivity.this,"",14,Ui.MUTED);label.setGravity(Gravity.CENTER);cell.addView(label);ImageView image=new ImageView(ReaderActivity.this);image.setAdjustViewBounds(true);image.setScaleType(ImageView.ScaleType.FIT_CENTER);cell.addView(image,new LinearLayout.LayoutParams(-1,Ui.dp(ReaderActivity.this,thumbs?160:400)));}
            TextView label=(TextView)cell.getChildAt(0);ImageView image=(ImageView)cell.getChildAt(1);
            label.setText("Página "+(n+1));image.setContentDescription("Página "+(n+1));image.setImageDrawable(null);image.getLayoutParams().height=Ui.dp(ReaderActivity.this,thumbs?160:400);
            Object binding=new Object();image.setTag(binding);int ticket=generation;
            worker.execute(()->{if(destroyed||ticket!=generation||image.getTag()!=binding)return;try{Bitmap b=source.page(n,thumbs?250:1200);runOnUiThread(()->{if(destroyed||ticket!=generation||image.getTag()!=binding)return;image.setImageBitmap(b);if(!thumbs){image.getLayoutParams().height=-2;image.requestLayout();}});}catch(Exception e){runOnUiThread(()->{if(!destroyed&&image.getTag()==binding)label.setText("Página "+(n+1)+" indisponível");});}});return cell;
        }
    }
}

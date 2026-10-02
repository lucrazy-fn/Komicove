package com.lucrazy.komicove;

import android.graphics.*;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;
import java.io.*;
import java.util.*;
import java.util.zip.*;
import java.util.concurrent.locks.*;
import org.apache.commons.compress.archivers.sevenz.*;
import org.apache.commons.compress.archivers.tar.*;
import com.github.junrar.Archive;
import com.github.junrar.rarfile.FileHeader;

final class BookSource implements Closeable {
    static final long MAX_PAGE=48L*1024*1024, MAX_TOTAL=1536L*1024*1024;
    static final int MAX_PAGES=10000, MAX_ENTRIES=20000, MAX_DICTIONARY_KIB=64*1024;
    static final long MAX_DECODE_PIXELS=8L*1024*1024;
    final List<String> pages=new ArrayList<>();
    private ZipFile zip;private PdfRenderer pdf;private ParcelFileDescriptor descriptor;
    private final File file;private ArchivePageCache.Entry prepared;private Index archiveIndex;
    private final ReentrantReadWriteLock lifecycle=new ReentrantReadWriteLock();
    private final Object pdfLock=new Object();private boolean closed;
    private static final class Page {
        final String name;final long size,offset;final int ordinal;final boolean sparse;
        Page(String n,long s,int i,long o,boolean sp){name=n;size=s;ordinal=i;offset=o;sparse=sp;}
    }
    private static final class Index {final String format;final List<Page> pages=new ArrayList<>();Index(String f){format=f;}}
    static boolean image(String name){return name!=null&&name.toLowerCase(Locale.ROOT).matches(".*\\.(png|jpe?g|webp|gif|bmp)$")&&!name.contains("__MACOSX")&&!new File(name).getName().startsWith(".");}
    static boolean supported(String name){return name.toLowerCase(Locale.ROOT).matches(".*\\.(cbz|zip|pdf|cbr|rar|7z|cb7|tar|cbt|epub)$");}
    static void checkCancelled()throws InterruptedIOException{if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();}
    BookSource(File file,File cache)throws Exception {
        this.file=file;
        try {
            checkCancelled();String lower=file.getName().toLowerCase(Locale.ROOT);
            if(lower.endsWith(".epub")){zip=new ZipFile(file);pages.addAll(EpubPages.read(zip));}
            else if(lower.endsWith(".pdf")){
                descriptor=ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);pdf=new PdfRenderer(descriptor);
                if(pdf.getPageCount()>MAX_PAGES)throw new IOException("Limite de 10.000 páginas excedido.");
                for(int i=0;i<pdf.getPageCount();i++)pages.add(Integer.toString(i));
            }else {
                try{zip=new ZipFile(file);}catch(ZipException ignored){}
                if(zip!=null){long total=0;int count=0;Enumeration<? extends ZipEntry> entries=zip.entries();
                    while(entries.hasMoreElements()){checkCancelled();ZipEntry e=entries.nextElement();if(++count>MAX_ENTRIES)throw new IOException("Limite de páginas excedido.");
                        if(!e.isDirectory()&&image(e.getName())){total=validateSize(e.getSize(),total);pages.add(e.getName());if(pages.size()>MAX_PAGES)throw new IOException("Limite de páginas excedido.");}}
                    pages.sort(new NaturalOrder());
                }else {
                    prepared=ArchivePageCache.acquire(file,cache);
                    prepared.indexLock.lockInterruptibly();try{if(prepared.index==null)prepared.index=index(lower);archiveIndex=(Index)prepared.index;}finally{prepared.indexLock.unlock();}
                    for(Page page:archiveIndex.pages)pages.add(page.name);
                }
            }
            if(pages.isEmpty())throw new IOException("Nenhuma página de imagem foi encontrada.");
            if(pages.size()>MAX_PAGES)throw new IOException("Limite de 10.000 páginas excedido.");
        }catch(Exception e){close();throw e;}
    }
    private static long validateSize(long size,long total)throws IOException {
        if(size>MAX_PAGE||size<0)throw new IOException("Página grande demais.");
        if(total>MAX_TOTAL-size)throw new IOException("O conteúdo excede 1,5 GB.");return total+size;
    }
    private static SevenZFile seven(File file)throws IOException{return SevenZFile.builder().setFile(file).setMaxMemoryLimitKb(MAX_DICTIONARY_KIB).get();}
    /** Commons Compress 1.27 drains entries while indexing; seek over ordinary payloads instead. */
    private static final class IndexedTarInputStream extends TarArchiveInputStream {
        private final java.nio.channels.FileChannel channel;private long payloadOffset;
        IndexedTarInputStream(FileInputStream input){super(input);channel=input.getChannel();}
        @Override protected byte[] readRecord()throws IOException {byte[] record=super.readRecord();payloadOffset=channel.position();return record;}
        @Override public TarArchiveEntry getNextTarEntry()throws IOException {
            checkCancelled();TarArchiveEntry previous=getCurrentEntry();
            if(previous!=null&&!previous.isSparse()&&!previous.isDirectory()){
                long size=previous.getSize(),position=channel.position();
                if(size<0||size>channel.size()-payloadOffset)throw new EOFException("Arquivo incompatível ou danificado.");
                long padding=(512-size%512)%512;
                if(padding>channel.size()-payloadOffset-size)throw new EOFException("Arquivo incompatível ou danificado.");
                long next=payloadOffset+size+padding;
                if(next<position)throw new EOFException("Arquivo incompatível ou danificado.");
                channel.position(next);count(next-position);setCurrentEntry(null);
            }
            return super.getNextTarEntry();
        }
    }
    private Index index(String lower)throws Exception {
        String format=lower.endsWith(".7z")||lower.endsWith(".cb7")?"7z":lower.endsWith(".tar")||lower.endsWith(".cbt")?"tar":Rar5Reader.matches(file)?"rar5":"rar";
        Index result=new Index(format);long total=0;int ordinal=0;
        if(format.equals("7z")){
            try(SevenZFile seven=seven(file)){for(SevenZArchiveEntry e:seven.getEntries()){checkCancelled();if(++ordinal>MAX_ENTRIES)throw new IOException("Limite de páginas excedido.");if(!e.isDirectory()&&image(e.getName())){total=validateSize(e.getSize(),total);result.pages.add(new Page(e.getName(),e.getSize(),ordinal-1,0,false));}}}
        }else if(format.equals("tar")){
            try(TarArchiveInputStream tar=new IndexedTarInputStream(new FileInputStream(file))){
                TarArchiveEntry e;while((e=tar.getNextTarEntry())!=null){checkCancelled();if(++ordinal>MAX_ENTRIES)throw new IOException("Limite de páginas excedido.");
                    if(e.isFile()&&!e.isSymbolicLink()&&!e.isLink()&&image(e.getName())){long size=e.getRealSize();total=validateSize(size,total);long offset=tar.getBytesRead();if(!e.isSparse()&&(offset>file.length()||size>file.length()-offset))throw new EOFException("Arquivo incompatível ou danificado.");result.pages.add(new Page(e.getName(),size,ordinal-1,offset,e.isSparse()));}}
            }
        }else if(format.equals("rar5")){
            for(Rar5Reader.Entry e:Rar5Reader.entries(file)){total=validateSize(e.size,total);result.pages.add(new Page(e.name,e.size,e.ordinal,0,false));}
        }else{
            try(Archive rar=new Archive(file)){if(rar.isEncrypted())throw new IOException("Arquivos com senha não são suportados.");
                for(FileHeader h:rar.getFileHeaders()){checkCancelled();if(++ordinal>MAX_ENTRIES)throw new IOException("Limite de páginas excedido.");if(!h.isDirectory()&&image(h.getFileNameString())){total=validateSize(h.getFullUnpackSize(),total);result.pages.add(new Page(h.getFileNameString(),h.getFullUnpackSize(),ordinal-1,0,false));}}}
        }
        if(result.pages.size()>MAX_PAGES)throw new IOException("Limite de páginas excedido.");
        NaturalOrder order=new NaturalOrder();result.pages.sort((a,b)->order.compare(a.name,b.name));return result;
    }
    private void extract(Page page,OutputStream output)throws Exception {
        OutputStream limited=limited(output,Math.min(MAX_PAGE,page.size));String format=archiveIndex.format;
        if(format.equals("tar")&&!page.sparse){try(RandomAccessFile in=new RandomAccessFile(file,"r")){in.seek(page.offset);byte[] b=new byte[65536];long left=page.size;while(left>0){checkCancelled();int n=in.read(b,0,(int)Math.min(b.length,left));if(n<0)throw new EOFException();limited.write(b,0,n);left-=n;}}}
        else if(format.equals("tar")){try(TarArchiveInputStream tar=new TarArchiveInputStream(new BufferedInputStream(new FileInputStream(file)))){for(int i=0;i<=page.ordinal;i++){checkCancelled();if(tar.getNextTarEntry()==null)throw new EOFException();}copy(tar,limited);}}
        else if(format.equals("7z")){try(SevenZFile seven=seven(file)){int i=0;boolean found=false;for(SevenZArchiveEntry e:seven.getEntries()){if(i++==page.ordinal){try(InputStream in=seven.getInputStream(e)){copy(in,limited);}found=true;break;}}if(!found)throw new EOFException();}}
        else if(format.equals("rar5")){Rar5Reader.extractPage(file,page.ordinal,limited);}
        else {try(Archive rar=new Archive(file)){List<FileHeader> headers=rar.getFileHeaders();if(page.ordinal>=headers.size())throw new EOFException();
                // junrar 7.x needs preceding solid dictionaries. Replay without retaining images.
                boolean solid=false;for(int i=0;i<=page.ordinal;i++)solid|=headers.get(i).isSolid();long[] skipped={0};
                if(solid)for(int i=0;i<page.ordinal;i++){checkCancelled();FileHeader h=headers.get(i);if(h.isDirectory())continue;rar.extractFile(h,new OutputStream(){public void write(int b)throws IOException{checkCancelled();if(++skipped[0]>MAX_TOTAL)throw new IOException("Conteúdo descompactado grande demais.");}public void write(byte[] b,int o,int n)throws IOException{checkCancelled();skipped[0]+=n;if(skipped[0]>MAX_TOTAL)throw new IOException("Conteúdo descompactado grande demais.");}});}
                rar.extractFile(headers.get(page.ordinal),limited);
            }}
    }
    private static OutputStream limited(OutputStream out,long limit){return new FilterOutputStream(out){long count;public void write(int b)throws IOException{checkCancelled();if(++count>limit)throw new IOException("Página grande demais.");out.write(b);}public void write(byte[] b,int o,int n)throws IOException{checkCancelled();if(n>limit-count)throw new IOException("Página grande demais.");count+=n;out.write(b,o,n);}};}
    static void copy(InputStream in,OutputStream out)throws IOException {byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){checkCancelled();out.write(b,0,n);}}
    private InputStream open(int index)throws Exception {
        InputStream input;
        if(zip!=null)input=zip.getInputStream(zip.getEntry(pages.get(index)));
        else{Page page=archiveIndex.pages.get(index);input=new FileInputStream(ArchivePageCache.page(prepared,index,out->extract(page,out)));}
        return new FilterInputStream(new BufferedInputStream(input,65536)){long count;public int read()throws IOException{checkCancelled();int b=in.read();if(b>=0&&++count>MAX_PAGE)throw new IOException("Página grande demais.");return b;}public int read(byte[] b,int o,int n)throws IOException{checkCancelled();int got=in.read(b,o,n);if(got>0&&(count+=got)>MAX_PAGE)throw new IOException("Página grande demais.");return got;}public long skip(long n)throws IOException{checkCancelled();long got=in.skip(Math.min(Math.max(0,n),MAX_PAGE-count+1));if((count+=got)>MAX_PAGE)throw new IOException("Página grande demais.");return got;}};
    }
    Bitmap page(int index,int target)throws IOException {
        try{lifecycle.readLock().lockInterruptibly();}catch(InterruptedException e){Thread.currentThread().interrupt();throw new InterruptedIOException();}
        Bitmap decoded=null;
        try {
            checkCancelled();if(closed)throw new IOException("Arquivo indisponível.");if(index<0||index>=pages.size())throw new IOException("Página inexistente.");target=Math.max(200,Math.min(target,2200));
            if(pdf!=null){synchronized(pdfLock){checkCancelled();try(PdfRenderer.Page p=pdf.openPage(index)){float scale=Math.min((float)target/p.getWidth(),(float)3000/p.getHeight());decoded=Bitmap.createBitmap(Math.max(1,(int)(p.getWidth()*scale)),Math.max(1,(int)(p.getHeight()*scale)),Bitmap.Config.ARGB_8888);decoded.eraseColor(Color.WHITE);p.render(decoded,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);}}}
            else {
                BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;
                try(InputStream in=open(index)){BitmapFactory.decodeStream(in,null,options);}checkCancelled();
                if(options.outWidth<=0||options.outHeight<=0)throw new IOException("Imagem inválida.");
                options.inSampleSize=1;
                while((long)Math.ceil(options.outWidth/(double)options.inSampleSize)*Math.ceil(options.outHeight/(double)options.inSampleSize)>MAX_DECODE_PIXELS||options.outWidth/(long)options.inSampleSize>target*1.5||options.outHeight/(long)options.inSampleSize>4000)options.inSampleSize*=2;
                options.inJustDecodeBounds=false;options.inPreferredConfig=Bitmap.Config.RGB_565;
                try(InputStream in=open(index)){decoded=BitmapFactory.decodeStream(in,null,options);}
                if(decoded==null)throw new IOException("Não foi possível ler esta imagem.");
            }
            checkCancelled();Bitmap result=decoded;decoded=null;return result;
        }catch(InterruptedException e){Thread.currentThread().interrupt();throw new InterruptedIOException();}
        catch(IOException e){throw e;}catch(Exception e){throw new IOException("Arquivo incompatível ou danificado.",e);}
        finally{if(decoded!=null)decoded.recycle();lifecycle.readLock().unlock();}
    }
    long cachedBytes(){if(prepared==null)return 0;long total=0;File[] files=prepared.directory.listFiles();if(files!=null)for(File f:files)if(f.isFile())total+=f.length();return total;}
    public void close(){lifecycle.writeLock().lock();try{if(closed)return;closed=true;try{if(zip!=null)zip.close();}catch(IOException ignored){}zip=null;if(pdf!=null){pdf.close();pdf=null;}try{if(descriptor!=null)descriptor.close();}catch(IOException ignored){}ArchivePageCache.release(prepared);prepared=null;archiveIndex=null;}finally{lifecycle.writeLock().unlock();}}
}

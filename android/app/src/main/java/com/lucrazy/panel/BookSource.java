package com.lucrazy.panel;

import android.graphics.*;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;
import java.io.*;
import java.util.*;
import java.util.zip.*;
import org.apache.commons.compress.archivers.sevenz.*;
import org.apache.commons.compress.archivers.tar.*;
import com.github.junrar.Archive;
import com.github.junrar.rarfile.FileHeader;

final class BookSource implements Closeable {
    static final long MAX_PAGE=48L*1024*1024, MAX_TOTAL=1536L*1024*1024;
    static final int MAX_PAGES=10000;
    final List<String> pages=new ArrayList<>();
    private ZipFile zip;
    private PdfRenderer pdf;
    private ParcelFileDescriptor descriptor;
    private File extracted;
    private long extractedBytes;
    static boolean image(String name) {return name.toLowerCase(Locale.ROOT).matches(".*\\.(png|jpe?g|webp|gif|bmp)$")&&!name.contains("__MACOSX")&&!new File(name).getName().startsWith(".");}
    static boolean supported(String name) {return name.toLowerCase(Locale.ROOT).matches(".*\\.(cbz|zip|pdf|cbr|rar|7z|cb7|tar|cbt)$");}

    BookSource(File file,File cache) throws Exception {
        try {
            String lower=file.getName().toLowerCase(Locale.ROOT);
            if(lower.endsWith(".pdf")) {
                descriptor=ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);pdf=new PdfRenderer(descriptor);
                for(int i=0;i<pdf.getPageCount();i++)pages.add(Integer.toString(i));
            } else {
                try {zip=new ZipFile(file);} catch(ZipException ignored) {}
                if(zip!=null) {
                    Enumeration<? extends ZipEntry> entries=zip.entries(); long total=0;
                    while(entries.hasMoreElements()) {ZipEntry e=entries.nextElement();if(!e.isDirectory()&&image(e.getName())){if(e.getSize()>MAX_PAGE)throw new IOException("Página grande demais.");total+=Math.max(0,e.getSize());pages.add(e.getName());}}
                    if(total>MAX_TOTAL)throw new IOException("O conteúdo excede 1,5 GB.");
                    pages.sort(new NaturalOrder());
                } else {
                    extracted=new File(cache,"pages-"+UUID.randomUUID()); if(!extracted.mkdirs())throw new IOException("Sem espaço para preparar a leitura.");
                    List<FilePage> extractedPages=new ArrayList<>();
                    if(lower.endsWith(".7z")||lower.endsWith(".cb7")) {
                        try(SevenZFile seven=new SevenZFile(file)) {
                            SevenZArchiveEntry e;while((e=seven.getNextEntry())!=null){if(e.isDirectory()||!image(e.getName()))continue;
                                if(e.getSize()>MAX_PAGE)throw new IOException("Página grande demais.");
                                String name=e.getName(); InputStream in=new InputStream(){public int read()throws IOException{return seven.read();}public int read(byte[] b,int o,int n)throws IOException{return seven.read(b,o,n);}};
                                extractedPages.add(extract(name,in,extractedPages.size()));}
                        }
                    } else if(lower.endsWith(".tar")||lower.endsWith(".cbt")) {
                        try(TarArchiveInputStream tar=new TarArchiveInputStream(new BufferedInputStream(new FileInputStream(file)))) {
                            TarArchiveEntry e;while((e=tar.getNextTarEntry())!=null)if(e.isFile()&&!e.isSymbolicLink()&&!e.isLink()&&image(e.getName()))extractedPages.add(extract(e.getName(),tar,extractedPages.size()));
                        }
                    } else {
                        try(Archive rar=new Archive(file)) {
                            if(rar.isEncrypted())throw new IOException("Arquivos com senha não são suportados.");
                            for(FileHeader h:rar.getFileHeaders())if(!h.isDirectory()&&image(h.getFileNameString())) {
                                if(h.getFullUnpackSize()>MAX_PAGE)throw new IOException("Página grande demais.");
                                if(extractedPages.size()>=MAX_PAGES)throw new IOException("Limite de páginas excedido.");
                                File dest=new File(extracted,Integer.toString(extractedPages.size()));
                                try(OutputStream out=limitedOutput(dest)){rar.extractFile(h,out);}
                                extractedPages.add(new FilePage(h.getFileNameString(),dest.getAbsolutePath()));
                            }
                        }
                    }
                    extractedPages.sort((a,b)->new NaturalOrder().compare(a.name,b.name));for(FilePage p:extractedPages)pages.add(p.path);
                }
            }
            if(pages.isEmpty())throw new IOException("Nenhuma página de imagem foi encontrada.");
            if(pages.size()>MAX_PAGES)throw new IOException("Limite de 10.000 páginas excedido.");
        } catch(Exception e){close();throw e;}
    }
    private static class FilePage {String name,path;FilePage(String n,String p){name=n;path=p;}}
    private FilePage extract(String name,InputStream in,int index)throws IOException {
        if(index>=MAX_PAGES)throw new IOException("Limite de páginas excedido.");
        File dest=new File(extracted,Integer.toString(index));try(OutputStream out=limitedOutput(dest)){copy(in,out);}return new FilePage(name,dest.getAbsolutePath());
    }
    private OutputStream limitedOutput(File file)throws IOException {
        return new FilterOutputStream(new FileOutputStream(file)) {
            long count;
            public void write(int n)throws IOException {write(new byte[]{(byte)n},0,1);}
            public void write(byte[] b,int o,int n)throws IOException {count+=n;extractedBytes+=n;if(count>MAX_PAGE||extractedBytes>MAX_TOTAL)throw new IOException("Conteúdo descompactado grande demais.");out.write(b,o,n);}
        };
    }
    static void copy(InputStream in,OutputStream out)throws IOException {byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();out.write(b,0,n);}}
    synchronized Bitmap page(int index,int target) throws IOException {
        if(index<0||index>=pages.size())throw new IOException("Página inexistente.");
        target=Math.max(200,Math.min(target,2200));
        if(pdf!=null){try(PdfRenderer.Page p=pdf.openPage(index)){float scale=Math.min((float)target/p.getWidth(),(float)3000/p.getHeight());Bitmap b=Bitmap.createBitmap(Math.max(1,(int)(p.getWidth()*scale)),Math.max(1,(int)(p.getHeight()*scale)),Bitmap.Config.ARGB_8888);b.eraseColor(Color.WHITE);p.render(b,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);return b;}}
        byte[] data;
        try(InputStream in=zip!=null?zip.getInputStream(zip.getEntry(pages.get(index))):new FileInputStream(pages.get(index));ByteArrayOutputStream out=new ByteArrayOutputStream()){
            byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>MAX_PAGE)throw new IOException("Página grande demais.");out.write(buffer,0,n);}data=out.toByteArray();
        }
        BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(data,0,data.length,options);
        if(options.outWidth<=0||options.outHeight<=0)throw new IOException("Imagem inválida.");
        options.inSampleSize=1;while(options.outWidth/options.inSampleSize>target*1.5||options.outHeight/options.inSampleSize>4000)options.inSampleSize*=2;
        options.inJustDecodeBounds=false;options.inPreferredConfig=Bitmap.Config.RGB_565;
        Bitmap image=BitmapFactory.decodeByteArray(data,0,data.length,options);if(image==null)throw new IOException("Não foi possível ler esta imagem.");return image;
    }
    public synchronized void close(){try{if(zip!=null)zip.close();}catch(IOException ignored){}zip=null;if(pdf!=null){pdf.close();pdf=null;}try{if(descriptor!=null)descriptor.close();}catch(IOException ignored){}if(extracted!=null){File[] children=extracted.listFiles();if(children!=null)for(File f:children)f.delete();extracted.delete();extracted=null;}}
}

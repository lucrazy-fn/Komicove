package com.lucrazy.komicove;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import me.zhanghai.android.libarchive.Archive;
import me.zhanghai.android.libarchive.ArchiveEntry;

final class Rar5Reader {
    interface PageSink { OutputStream open(String name) throws IOException; }
    static final class Entry {final String name;final long size;final int ordinal;Entry(String n,long s,int o){name=n;size=s;ordinal=o;}}
    static java.util.List<Entry> entries(File file)throws IOException {
        // libarchive must decompress skipped solid entries. Index raw headers before allocating a dictionary.
        return scanHeaders(file,true);
    }
    private static boolean regular(long entry){return ArchiveEntry.filetype(entry)==ArchiveEntry.AE_IFREG&&ArchiveEntry.hardlink(entry)==null;}
    private static long open(File file)throws IOException {
        validateHeaders(file);
        long archive=Archive.readNew();
        try{Archive.readSupportFilterNone(archive);Archive.readSupportFormatRar5(archive);Archive.readOpenFileName(archive,file.getAbsolutePath().getBytes(StandardCharsets.UTF_8),65536);return archive;}
        catch(IOException|RuntimeException e){Archive.readFree(archive);throw e;}
    }
    // Check native dictionary allocations before libarchive sees compressed data.
    static void validateHeaders(File file)throws IOException {
        scanHeaders(file,false);
    }
    private static java.util.List<Entry> scanHeaders(File file,boolean collect)throws IOException {
        java.util.List<Entry> pages=new java.util.ArrayList<>();
        try(RandomAccessFile input=new RandomAccessFile(file,"r")){input.seek(8);int count=0,ordinal=0;long total=0;
            while(input.getFilePointer()<input.length()){BookSource.checkCancelled();if(++count>BookSource.MAX_ENTRIES)throw new IOException("Limite de páginas excedido.");
                if(input.length()-input.getFilePointer()<5)throw new EOFException();long crcOffset=input.getFilePointer();input.skipBytes(4);long headerSize=vint(input),headerStart=input.getFilePointer();
                if(headerSize>2L*1024*1024||headerSize>input.length()-headerStart)throw new IOException("Arquivo incompatível ou danificado.");
                long type=vint(input),flags=vint(input),extraSize=(flags&1)!=0?vint(input):0,dataSize=(flags&2)!=0?vint(input):0,end=headerStart+headerSize;
                if(extraSize>headerSize)throw new IOException("Arquivo incompatível ou danificado.");
                if(type==4)throw new IOException("Arquivos com senha não são suportados.");
                if(type==2||type==3){long fileFlags=vint(input),unpacked=vint(input);if(unpacked>BookSource.MAX_TOTAL-total)throw new IOException("Conteúdo descompactado grande demais.");total+=unpacked;vint(input);if((fileFlags&2)!=0)input.skipBytes(4);if((fileFlags&4)!=0)input.skipBytes(4);long compression=vint(input);
                    int power=(int)((compression>>>10)&31);long dictionary=128L*1024<<power;
                    // RAR7's fractional dictionary field adds at most another full dictionary.
                    if((compression&63)>0&&((compression>>>15)&31)!=0)dictionary*=2;
                    if(dictionary>BookSource.MAX_DICTIONARY_KIB*1024L)throw new IOException("Conteúdo descompactado grande demais.");
                    vint(input);long nameLength=vint(input),extraStart=end-extraSize;
                    if(nameLength>65536||nameLength>extraStart-input.getFilePointer())throw new IOException("Arquivo incompatível ou danificado.");
                    byte[] nameBytes=new byte[(int)nameLength];input.readFully(nameBytes);String name=new String(nameBytes,StandardCharsets.UTF_8);int zero=name.indexOf('\0');if(zero>=0)name=name.substring(0,zero);
                    boolean redirect=false;if(input.getFilePointer()>extraStart)throw new IOException("Arquivo incompatível ou danificado.");input.seek(extraStart);
                    while(input.getFilePointer()<end){long recordSize=vint(input),recordStart=input.getFilePointer();if(recordSize==0||recordSize>end-recordStart)throw new IOException("Arquivo incompatível ou danificado.");long recordType=vint(input);if(recordType==1)throw new IOException("Arquivos com senha não são suportados.");if(recordType==5)redirect=true;if(input.getFilePointer()>recordStart+recordSize)throw new EOFException();input.seek(recordStart+recordSize);}
                    if(type==2){if(collect&&(fileFlags&1)==0&&!redirect&&BookSource.image(name)){
                        if((fileFlags&8)!=0||unpacked>BookSource.MAX_PAGE)throw new IOException("Página grande demais.");pages.add(new Entry(name,unpacked,ordinal));if(pages.size()>BookSource.MAX_PAGES)throw new IOException("Limite de páginas excedido.");
                    }ordinal++;}
                }
                if(input.getFilePointer()>end||dataSize>input.length()-end)throw new IOException("Arquivo incompatível ou danificado.");
                // CRC covers the encoded header length plus header, not the payload.
                input.seek(crcOffset);long expected=Integer.toUnsignedLong(Integer.reverseBytes(input.readInt()));java.util.zip.CRC32 crc=new java.util.zip.CRC32();byte[] bytes=new byte[4096];long remaining=end-input.getFilePointer();
                while(remaining>0){BookSource.checkCancelled();int n=input.read(bytes,0,(int)Math.min(bytes.length,remaining));if(n<0)throw new EOFException();crc.update(bytes,0,n);remaining-=n;}if(crc.getValue()!=expected)throw new IOException("Arquivo incompatível ou danificado.");
                input.seek(end+dataSize);if(type==5)break;
            }
        }return pages;
    }
    private static long vint(RandomAccessFile input)throws IOException {long value=0;for(int shift=0;shift<63;shift+=7){int b=input.readUnsignedByte();value|=(long)(b&127)<<shift;if((b&128)==0)return value;}throw new IOException("Arquivo incompatível ou danificado.");}
    static void extractPage(File file,int ordinal,OutputStream out)throws IOException {
        long archive=open(file);
        try {long entry;int index=0;ByteBuffer buffer=ByteBuffer.allocate(65536);
            while((entry=Archive.readNextHeader(archive))!=0){BookSource.checkCancelled();if(index++==ordinal){
                    if(!regular(entry)||ArchiveEntry.isEncrypted(entry)||ArchiveEntry.size(entry)>BookSource.MAX_PAGE)throw new IOException("Arquivo incompatível ou danificado.");
                    while(true){BookSource.checkCancelled();buffer.clear();Archive.readData(archive,buffer);int n=buffer.position();if(n==0)return;out.write(buffer.array(),0,n);}
                }Archive.readDataSkip(archive);
            }throw new EOFException();
        }finally{Archive.readFree(archive);}
    }

    static boolean matches(File file) throws IOException {
        byte[] signature=new byte[8];
        try(DataInputStream in=new DataInputStream(new FileInputStream(file))){
            try { in.readFully(signature); } catch(EOFException e){return false;}
        }
        return Arrays.equals(signature,new byte[]{0x52,0x61,0x72,0x21,0x1a,7,1,0});
    }

    static void extract(File file,PageSink sink) throws IOException {
        long archive=Archive.readNew();
        try {
            Archive.readSupportFilterNone(archive);
            Archive.readSupportFormatRar5(archive);
            Archive.readOpenFileName(archive,file.getAbsolutePath().getBytes(StandardCharsets.UTF_8),65536);
            ByteBuffer buffer=ByteBuffer.allocate(65536);
            long entry;
            while((entry=Archive.readNextHeader(archive))!=0){
                if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();
                if(ArchiveEntry.isEncrypted(entry))throw new IOException("Arquivos com senha não são suportados.");
                String name=ArchiveEntry.pathnameUtf8(entry);
                if(name==null||ArchiveEntry.filetype(entry)!=ArchiveEntry.AE_IFREG
                        ||ArchiveEntry.hardlink(entry)!=null||!BookSource.image(name)){
                    Archive.readDataSkip(archive);continue;
                }
                if(ArchiveEntry.size(entry)>BookSource.MAX_PAGE)throw new IOException("Página grande demais.");
                try(OutputStream out=sink.open(name)){
                    while(true){
                        if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();
                        buffer.clear();Archive.readData(archive,buffer);
                        int count=buffer.position();if(count==0)break;
                        out.write(buffer.array(),0,count);
                    }
                }
            }
        } finally { Archive.readFree(archive); }
    }
}

package com.lucrazy.panel;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import me.zhanghai.android.libarchive.Archive;
import me.zhanghai.android.libarchive.ArchiveEntry;

final class Rar5Reader {
    interface PageSink { OutputStream open(String name) throws IOException; }

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

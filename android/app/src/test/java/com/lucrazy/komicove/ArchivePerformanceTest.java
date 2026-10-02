package com.lucrazy.komicove;

import java.io.*;
import java.nio.*;
import java.util.*;
import org.apache.commons.compress.archivers.tar.*;
import org.apache.commons.compress.archivers.sevenz.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=28)
public class ArchivePerformanceTest {
    static byte[] bmp(int width,int height) {
        int stride=(width*3+3)&~3,size=54+stride*height;
        byte[] data=new byte[size];ByteBuffer b=ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        b.put((byte)'B').put((byte)'M').putInt(size).putInt(0).putInt(54).putInt(40).putInt(width).putInt(height).putShort((short)1).putShort((short)24).putInt(0).putInt(size-54);
        // Incompressible deterministic image pixels, generated without another page-sized array.
        Random random=new Random(42);for(int i=54;i<size;i++)data[i]=(byte)random.nextInt(256);
        return data;
    }
    static File tar(File directory,int count,byte[] page)throws Exception {
        File file=File.createTempFile("reader-large-",".cbt",directory);
        try(TarArchiveOutputStream out=new TarArchiveOutputStream(new BufferedOutputStream(new FileOutputStream(file)))) {
            for(int i=0;i<count;i++){TarArchiveEntry entry=new TarArchiveEntry(String.format(Locale.ROOT,"page%04d.bmp",i));entry.setSize(page.length);out.putArchiveEntry(entry);out.write(page);out.closeArchiveEntry();}
        }
        return file;
    }
    @Test public void largeTarFirstPageAndReopen()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir();File archive=tar(cache,32,bmp(1024,1024));
        try {
            assertTrue(archive.length()>96L*1024*1024);
            long start=System.nanoTime();
            try(BookSource source=new BookSource(archive,cache)){
                long prepared=System.nanoTime();assertEquals(32,source.pages.size());
                assertEquals(0,source.cachedBytes());
                android.graphics.Bitmap first=source.page(0,1200);assertNotNull(first);first.recycle();
                assertEquals(1024*1024*3+54,source.cachedBytes());
                System.out.printf(Locale.ROOT,"READER_BENCH large_tar bytes=%d prepare_ms=%.2f first_page_ms=%.2f temporary_bytes=%d%n",archive.length(),(prepared-start)/1e6,(System.nanoTime()-start)/1e6,temporaryBytes(cache));
            }
            long reopened=System.nanoTime();try(BookSource source=new BookSource(archive,cache)){source.page(0,1200).recycle();System.out.printf(Locale.ROOT,"READER_BENCH reopen_ms=%.2f%n",(System.nanoTime()-reopened)/1e6);}
        }finally{archive.delete();}
    }
    @Test public void sevenZPagesAreLazyAndCached()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir(),archive=File.createTempFile("reader-seven-",".cb7",cache);byte[] page=bmp(512,512);
        try{try(SevenZOutputFile out=new SevenZOutputFile(archive)){out.setContentCompression(SevenZMethod.COPY);for(String name:new String[]{"10.bmp","2.bmp","1.bmp"}){SevenZArchiveEntry entry=new SevenZArchiveEntry();entry.setName(name);out.putArchiveEntry(entry);out.write(page);out.closeArchiveEntry();}}
            try(BookSource source=new BookSource(archive,cache)){assertEquals("1.bmp",source.pages.get(0));assertEquals(0,source.cachedBytes());source.page(0,600).recycle();assertEquals(page.length,source.cachedBytes());source.page(2,600).recycle();assertEquals(page.length*2L,source.cachedBytes());}
            try(BookSource source=new BookSource(archive,cache)){assertEquals(page.length*2L,source.cachedBytes());source.page(0,600).recycle();assertEquals(page.length*2L,source.cachedBytes());}
        }finally{archive.delete();}
    }
    @Test public void tarLongNamesAndPaxMetadataPreserveOffsets()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir();byte[] page=bmp(32,48);
        for(int longMode:new int[]{TarArchiveOutputStream.LONGFILE_GNU,TarArchiveOutputStream.LONGFILE_POSIX}){
            File archive=File.createTempFile("tar-extended-",".cbt",cache);
            try{try(TarArchiveOutputStream out=new TarArchiveOutputStream(new FileOutputStream(archive))){out.setLongFileMode(longMode);
                for(String name:new String[]{String.join("",Collections.nCopies(160,"a"))+".bmp","last.bmp"}){TarArchiveEntry e=new TarArchiveEntry(name);e.setSize(page.length);out.putArchiveEntry(e);out.write(page);out.closeArchiveEntry();}}
                try(BookSource source=new BookSource(archive,cache)){assertEquals(2,source.pages.size());source.page(0,200).recycle();source.page(1,200).recycle();assertEquals(2L*page.length,source.cachedBytes());}
            }finally{archive.delete();}
        }
    }
    @Test public void cancelledExtractionLeavesNoPartialPageAndDoesNotDeleteNeighbours()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir(),archive=tar(cache,2,bmp(20,30));File neighbour=File.createTempFile("must-preserve-",".txt",cache);
        try(BookSource source=new BookSource(archive,cache)){Thread.currentThread().interrupt();try{source.page(0,200);fail();}catch(InterruptedIOException expected){}finally{Thread.interrupted();}assertEquals(0,source.cachedBytes());source.page(0,200).recycle();assertTrue(neighbour.exists());}
        finally{archive.delete();neighbour.delete();}
    }
    @Test public void oversizedDeclaredPageIsRejectedBeforeExtraction()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir(),archive=tar(cache,1,bmp(20,30));
        // Valid TAR header claiming a malicious image allocation, without writing its payload.
        try(RandomAccessFile out=new RandomAccessFile(archive,"rw")){TarArchiveEntry e=new TarArchiveEntry("bomb.bmp");e.setSize(BookSource.MAX_PAGE+1);byte[] header=new byte[512];e.writeEntryHeader(header);out.seek(0);out.write(header);}
        try{new BookSource(archive,cache);fail();}catch(IOException expected){}finally{archive.delete();}
    }
    @Test public void simultaneousPagesAndCloseAreSafe()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir(),archive=tar(cache,4,bmp(128,128));java.util.concurrent.ExecutorService workers=java.util.concurrent.Executors.newFixedThreadPool(2);
        try(BookSource source=new BookSource(archive,cache)){java.util.concurrent.Future<?> a=workers.submit(()->{try{source.page(0,200).recycle();}catch(IOException e){throw new RuntimeException(e);}});java.util.concurrent.Future<?> b=workers.submit(()->{try{source.page(3,200).recycle();}catch(IOException e){throw new RuntimeException(e);}});a.get(10,java.util.concurrent.TimeUnit.SECONDS);b.get(10,java.util.concurrent.TimeUnit.SECONDS);assertEquals(2L*bmp(128,128).length,source.cachedBytes());}
        finally{workers.shutdownNow();archive.delete();}
    }
    @Test public void compressedSolidRar4NavigatesOutOfOrder()throws Exception {
        String path=System.getenv("PANEL_TEST_RAR4");Assume.assumeNotNull(path);File cache=RuntimeEnvironment.getApplication().getCacheDir();
        try(BookSource source=new BookSource(new File(path),cache)){assertTrue(source.pages.size()>1);for(int page:new int[]{0,source.pages.size()-1,source.pages.size()/2,0})source.page(page,600).recycle();}
    }
    @Test public void partialCacheWriteIsCancelledAndIdleCleanupKeepsActiveEntries()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir(),archive=File.createTempFile("cache-safety-",".cbt",cache);
        ArchivePageCache.Entry entry=ArchivePageCache.acquire(archive,cache);
        try{try{ArchivePageCache.page(entry,0,out->{out.write(new byte[2048]);Thread.currentThread().interrupt();BookSource.checkCancelled();});fail();}catch(InterruptedIOException expected){}finally{Thread.interrupted();}
            assertEquals(0,ArchivePerformanceTest.treeBytes(entry.directory));assertEquals(0,entry.directory.listFiles().length);
            File page=ArchivePageCache.page(entry,0,out->out.write(new byte[32]));entry.touched=0;ArchivePageCache.trimIdle(cache);assertTrue(page.exists());
            ArchivePageCache.release(entry);entry.touched=0;ArchivePageCache.trimIdle(cache);assertFalse(page.exists());
        }finally{ArchivePageCache.release(entry);archive.delete();}
    }
    @Test public void actualCacheBudgetIsEnforcedAtomically()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir(),archive=File.createTempFile("cache-budget-",".cbt",cache);ArchivePageCache.Entry entry=ArchivePageCache.acquire(archive,cache);
        try{entry.bytes=BookSource.MAX_TOTAL;try{ArchivePageCache.page(entry,0,out->out.write(1));fail();}catch(IOException expected){}assertEquals(0,entry.directory.listFiles().length);}
        finally{entry.bytes=0;ArchivePageCache.release(entry);archive.delete();}
    }
    @Test public void nativeRarDictionaryBombIsRejectedBeforeNativeAllocation()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir(),archive=File.createTempFile("rar-dictionary-",".rar",cache);ByteArrayOutputStream header=new ByteArrayOutputStream();
        for(long number:new long[]{2,0,0,1,0,16L<<10})vint(header,number);
        try(OutputStream out=new FileOutputStream(archive)){out.write(new byte[]{0x52,0x61,0x72,0x21,0x1a,7,1,0,0,0,0,0});vint(out,header.size());out.write(header.toByteArray());}
        try{Rar5Reader.validateHeaders(archive);fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("grande"));}finally{archive.delete();}
    }
    private static void vint(OutputStream out,long value)throws IOException{do{int b=(int)(value&127);value>>>=7;out.write(value==0?b:b|128);}while(value!=0);}
    private static void rar5Block(OutputStream out,byte[] header,byte[] payload)throws IOException{
        ByteArrayOutputStream encoded=new ByteArrayOutputStream();vint(encoded,header.length);encoded.write(header);java.util.zip.CRC32 crc=new java.util.zip.CRC32();crc.update(encoded.toByteArray());long value=crc.getValue();for(int i=0;i<4;i++)out.write((int)(value>>>(i*8)));out.write(encoded.toByteArray());out.write(payload);
    }
    @Test public void rar5HeaderIndexSkipsPayloadAndChecksCrc()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir(),archive=File.createTempFile("rar-header-index-",".rar",cache);byte[] page=bmp(128,128);
        try{try(OutputStream out=new FileOutputStream(archive)){out.write(new byte[]{0x52,0x61,0x72,0x21,0x1a,7,1,0});rar5Block(out,new byte[]{1,0,0},new byte[0]);
                for(String name:new String[]{"folder","first.bmp","last.bmp"}){boolean directory=name.equals("folder");ByteArrayOutputStream header=new ByteArrayOutputStream();for(long field:new long[]{2,2,directory?0:page.length,directory?1:0,directory?0:page.length,0,0,1,name.length()})vint(header,field);header.write(name.getBytes(java.nio.charset.StandardCharsets.UTF_8));rar5Block(out,header.toByteArray(),directory?new byte[0]:page);}
                rar5Block(out,new byte[]{5,0,0},new byte[0]);}
            List<Rar5Reader.Entry> entries=Rar5Reader.entries(archive);assertEquals(2,entries.size());assertEquals(1,entries.get(0).ordinal);assertEquals("last.bmp",entries.get(1).name);assertEquals(page.length,entries.get(0).size);
            try(RandomAccessFile file=new RandomAccessFile(archive,"rw")){file.seek(8);file.write(0);}try{Rar5Reader.entries(archive);fail();}catch(IOException expected){}
        }finally{archive.delete();}
    }
    @Test public void tarPageCountLimitStillRejectsMaliciousArchive()throws Exception {
        File cache=RuntimeEnvironment.getApplication().getCacheDir(),archive=tar(cache,BookSource.MAX_PAGES+1,bmp(1,1));try{new BookSource(archive,cache);fail();}catch(IOException expected){}finally{archive.delete();}
    }
    static long temporaryBytes(File directory){long bytes=0;File[] files=directory.listFiles();if(files!=null)for(File f:files){if(f.isDirectory()&&(f.getName().startsWith("pages-")||f.getName().equals("reader-pages-v1")))bytes+=treeBytes(f);}return bytes;}
    static long treeBytes(File directory){long bytes=0;File[] files=directory.listFiles();if(files!=null)for(File f:files)bytes+=f.isDirectory()?treeBytes(f):f.length();return bytes;}
}

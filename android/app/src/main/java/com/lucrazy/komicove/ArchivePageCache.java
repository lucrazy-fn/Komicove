package com.lucrazy.komicove;

import java.io.*;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

/** Process-session cache. Only this private namespace may be pruned. */
final class ArchivePageCache {
    static final long MAX_DISK_BYTES=256L*1024*1024, IDLE_MS=30*60*1000L;
    private static final Map<String,Entry> entries=new LinkedHashMap<>();
    static final class Entry {
        final File directory;
        final Map<Integer,ReentrantLock> locks=new HashMap<>();
        final ReentrantLock indexLock=new ReentrantLock();
        Object index;int users;long bytes;long touched=System.currentTimeMillis();
        Entry(File directory){this.directory=directory;}
        synchronized ReentrantLock lock(int page){return locks.computeIfAbsent(page,k->new ReentrantLock());}
    }
    interface Writer {void write(OutputStream out)throws Exception;}
    static synchronized Entry acquire(File file,File cache)throws Exception {
        File root=new File(cache,"reader-pages-v1");
        if(Files.isSymbolicLink(root.toPath())||!root.mkdirs()&&!root.isDirectory())throw new IOException("Sem espaço para preparar a leitura.");
        String identity=file.getCanonicalPath()+"\n"+file.length()+"\n"+file.lastModified();
        StringBuilder key=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(identity.getBytes(java.nio.charset.StandardCharsets.UTF_8)))key.append(String.format(Locale.ROOT,"%02x",b&255));
        String path=new File(root,key.toString()).getAbsolutePath();Entry entry=entries.get(path);
        if(entry==null){entry=new Entry(new File(path));entries.put(path,entry);}
        if(Files.isSymbolicLink(entry.directory.toPath())||!entry.directory.mkdirs()&&!entry.directory.isDirectory())throw new IOException("Sem espaço para preparar a leitura.");
        if(entry.users==0){File[] leftovers=entry.directory.listFiles();if(leftovers!=null)for(File pending:leftovers)if(pending.isFile()&&!Files.isSymbolicLink(pending.toPath())&&pending.getName().matches("pending-.*\\.part"))pending.delete();entry.bytes=size(entry.directory);}
        entry.users++;entry.touched=System.currentTimeMillis();prune(root);return entry;
    }
    static File page(Entry entry,int page,Writer writer)throws Exception {
        ReentrantLock lock=entry.lock(page);lock.lockInterruptibly();
        try {
            checkCancelled();File complete=new File(entry.directory,page+".page");
            if(complete.isFile()&&!Files.isSymbolicLink(complete.toPath())){complete.setLastModified(System.currentTimeMillis());return complete;}
            File temporary=File.createTempFile("pending-",".part",entry.directory);
            try {
                try(OutputStream out=new BufferedOutputStream(new FileOutputStream(temporary))){writer.write(out);}
                checkCancelled();
            synchronized(entry){if(temporary.length()>BookSource.MAX_TOTAL-entry.bytes)throw new IOException("Conteúdo descompactado grande demais.");if(!temporary.renameTo(complete))throw new IOException("Sem espaço para preparar a leitura.");entry.bytes+=complete.length();}
                return complete;
            }finally{temporary.delete();}
        }finally{lock.unlock();}
    }
    static synchronized void release(Entry entry){if(entry==null)return;entry.users=Math.max(0,entry.users-1);entry.touched=System.currentTimeMillis();prune(entry.directory.getParentFile());}
    private static void checkCancelled()throws InterruptedIOException{if(Thread.currentThread().isInterrupted())throw new InterruptedIOException();}
    static synchronized void trimIdle(File cache){File root=new File(cache,"reader-pages-v1");if(root.isDirectory()&&!Files.isSymbolicLink(root.toPath()))prune(root);}
    private static void prune(File root){
        File[] dirs=root.listFiles();if(dirs==null)return;long total=0;List<File> idle=new ArrayList<>();
        for(File dir:dirs){if(!dir.getName().matches("[a-f0-9]{64}")||Files.isSymbolicLink(dir.toPath()))continue;Entry e=entries.get(dir.getAbsolutePath());total+=size(dir);if(e==null||e.users==0)idle.add(dir);}
        idle.sort(Comparator.comparingLong(File::lastModified));
        int idleCount=idle.size();
        for(File dir:idle){Entry e=entries.get(dir.getAbsolutePath());long touched=e==null?dir.lastModified():e.touched;
            if(total>MAX_DISK_BYTES||System.currentTimeMillis()-touched>IDLE_MS||idleCount>4){long bytes=size(dir);deleteOwned(root,dir);entries.remove(dir.getAbsolutePath());total-=bytes;idleCount--;}
        }
    }
    private static long size(File dir){long total=0;File[] files=dir.listFiles();if(files!=null)for(File f:files)if(f.isFile()&&!Files.isSymbolicLink(f.toPath()))total+=f.length();return total;}
    private static void deleteOwned(File root,File dir){
        try{if(!dir.getCanonicalFile().getParentFile().equals(root.getCanonicalFile())||Files.isSymbolicLink(dir.toPath()))return;
            File[] files=dir.listFiles();if(files!=null)for(File f:files){if(!Files.isSymbolicLink(f.toPath())&&f.isFile()&&(f.getName().matches("[0-9]+\\.page")||f.getName().matches("pending-.*\\.part")))f.delete();}
            dir.delete();
        }catch(IOException ignored){}
    }
}

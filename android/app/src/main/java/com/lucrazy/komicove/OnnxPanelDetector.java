package com.lucrazy.komicove;

import android.content.Context;
import android.graphics.*;
import android.util.Log;
import ai.onnxruntime.*;
import java.io.*;
import java.nio.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.CancellationException;
import java.util.concurrent.locks.ReentrantLock;

/** Local guided-reading inference, shared by normal and test builds. */
final class OnnxPanelDetector extends AiPanelDetector {
    private final Context context;
    private final ReentrantLock lock=new ReentrantLock();
    private OrtSession session;
    private OrtEnvironment environment;
    private FloatBuffer buffer;
    private volatile boolean closed,disabled;
    private volatile OrtSession.RunOptions active;

    OnnxPanelDetector(Context context){super(context);this.context=context.getApplicationContext();}
    private void open()throws IOException,OrtException,NoSuchAlgorithmException {
        File directory=new File(context.getCacheDir(),"guided-ai");
        if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("Model cache unavailable");
        File model=new File(directory,"inkwell.onnx");
        if(!valid(model)){
            File partial=File.createTempFile("inkwell-",".partial",directory);
            try{
                try(InputStream in=context.getAssets().open("guided-ai/inkwell.onnx");OutputStream out=new FileOutputStream(partial)){
                    byte[] bytes=new byte[65536];int count,total=0;
                    while((count=in.read(bytes))!=-1){check();total+=count;if(total>BYTES)throw new IOException("Model exceeds limit");out.write(bytes,0,count);}
                }
                if(!valid(partial))throw new IOException("Model verification failed");
                if(!partial.renameTo(model))throw new IOException("Model cache commit failed");
            }finally{if(partial.exists()&&!partial.delete())Log.w("KomicoveAI","Partial model cache cleanup deferred");}
        }
        check();environment=OrtEnvironment.getEnvironment();
        try(OrtSession.SessionOptions options=new OrtSession.SessionOptions()){
            options.setIntraOpNumThreads(2);options.setInterOpNumThreads(1);
            options.setExecutionMode(OrtSession.SessionOptions.ExecutionMode.SEQUENTIAL);
            options.setCPUArenaAllocator(false);options.setMemoryPatternOptimization(false);
            options.setSessionLogLevel(OrtLoggingLevel.ORT_LOGGING_LEVEL_ERROR);
            session=environment.createSession(model.getAbsolutePath(),options);
        }
        if(session.getInputInfo().size()!=1)throw new IOException("Model input mismatch");
        TensorInfo info=(TensorInfo)session.getInputInfo().values().iterator().next().getInfo();
        long[] shape=info.getShape();long[] expected={1,3,SIZE,SIZE};
        if(shape.length!=4)throw new IOException("Model input mismatch");
        for(int i=0;i<4;i++)if(shape[i]>0&&shape[i]!=expected[i])throw new IOException("Model input mismatch");
        buffer=ByteBuffer.allocateDirect(3*SIZE*SIZE*4).order(ByteOrder.nativeOrder()).asFloatBuffer();
    }
    PanelDetector.Result detect(Bitmap image,PanelDetector.Result baseline,boolean manga){
        check();boolean acquired=false;
        try{
            lock.lockInterruptibly();acquired=true;check();if(closed||disabled)return baseline;
            if(session==null)open();check();
            float scale=Math.min(SIZE/(float)image.getWidth(),SIZE/(float)image.getHeight());
            int width=Math.max(1,Math.round(image.getWidth()*scale)),height=Math.max(1,Math.round(image.getHeight()*scale));
            int left=(SIZE-width)/2,top=(SIZE-height)/2;
            Bitmap input=Bitmap.createBitmap(SIZE,SIZE,Bitmap.Config.ARGB_8888);
            int[] pixels=new int[SIZE*SIZE];
            try{
                Canvas canvas=new Canvas(input);canvas.drawColor(Color.rgb(114,114,114));
                canvas.drawBitmap(image,null,new Rect(left,top,left+width,top+height),new Paint(Paint.FILTER_BITMAP_FLAG));
                input.getPixels(pixels,0,SIZE,0,0,SIZE,SIZE);
                int plane=SIZE*SIZE;buffer.rewind();
                for(int channel=0;channel<3;channel++)for(int i=0;i<plane;i++){
                    if((i&4095)==0)check();int shift=16-channel*8;buffer.put(((pixels[i]>>shift)&255)/255f);
                }
                buffer.rewind();
            }finally{input.recycle();}
            check();
            try(OnnxTensor tensor=OnnxTensor.createTensor(environment,buffer,new long[]{1,3,SIZE,SIZE});OrtSession.RunOptions options=new OrtSession.RunOptions()){
                active=options;Thread owner=Thread.currentThread();java.util.concurrent.atomic.AtomicBoolean finished=new java.util.concurrent.atomic.AtomicBoolean();
                Thread monitor=new Thread(()->{while(!finished.get()){
                    if(closed||owner.isInterrupted()){try{options.setTerminate(true);}catch(OrtException ignored){}return;}
                    try{Thread.sleep(20);}catch(InterruptedException stop){return;}
                }},"guided-ai-cancel");monitor.setDaemon(true);monitor.start();
                try(OrtSession.Result prediction=session.run(Collections.singletonMap(session.getInputNames().iterator().next(),tensor),options)){
                    check();if(closed)throw new CancellationException();
                    Object value=prediction.get(0).getValue();
                    if(!(value instanceof float[][][])||((float[][][])value).length!=1)throw new IOException("Model output mismatch");
                    List<Detection> boxes=decode(((float[][][])value)[0],left,top,width,height);
                    return combine(boxes,baseline,manga,image.getWidth()>image.getHeight());
                }finally{finished.set(true);monitor.interrupt();boolean interrupted=Thread.interrupted();try{monitor.join();}catch(InterruptedException ignored){interrupted=true;}finally{if(interrupted)Thread.currentThread().interrupt();active=null;}}
            }
        }catch(InterruptedException e){Thread.currentThread().interrupt();throw new CancellationException();}
        catch(CancellationException e){throw e;}
        catch(IOException|OrtException|NoSuchAlgorithmException|RuntimeException|LinkageError e){
            check();if(closed)throw new CancellationException();disabled=true;release();
            Log.w("KomicoveAI","Local model unavailable; existing detector retained ("+e.getClass().getSimpleName()+")");return baseline;
        }finally{if(acquired){if(closed)release();lock.unlock();}}
    }
    private void release(){buffer=null;if(session!=null){try{session.close();}catch(OrtException ignored){}session=null;}}
    public void close(){closed=true;OrtSession.RunOptions running=active;if(running!=null)try{running.setTerminate(true);}catch(OrtException|IllegalStateException ignored){}if(lock.tryLock())try{release();}finally{lock.unlock();}}
}

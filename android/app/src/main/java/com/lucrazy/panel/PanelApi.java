package com.lucrazy.panel;

import android.content.*;
import android.security.keystore.*;
import android.util.Base64;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import java.security.KeyStore;
import java.io.*;
import java.util.concurrent.TimeUnit;
import okhttp3.*;
import org.json.*;

final class PanelApi {
    static final String DEFAULT_BASE = "https://panel-api-tr1a.onrender.com";
    private final SharedPreferences prefs;private final OkHttpClient client=new OkHttpClient.Builder().connectTimeout(15,TimeUnit.SECONDS).readTimeout(90,TimeUnit.SECONDS).followRedirects(false).followSslRedirects(false).build();
    private String token="";JSONObject user=new JSONObject();
    PanelApi(Context c){prefs=c.getSharedPreferences("api",0);try{String value=prefs.getString("session","");if(!value.isEmpty()){String[] parts=value.split(":");Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(parts[0],0)));token=new String(cipher.doFinal(Base64.decode(parts[1],0)),java.nio.charset.StandardCharsets.UTF_8);user=new JSONObject(prefs.getString("user","{}"));}}catch(Exception ignored){clear();}}
    String base(){return DEFAULT_BASE;}boolean signedIn(){return !token.isEmpty();}boolean moderator(){String role=user.optString("role");return role.equals("moderator")||role.equals("admin")||role.equals("owner");}
    void base(String value)throws Exception {if(value!=null&&!value.trim().isEmpty()&&!DEFAULT_BASE.equals(value.trim().replaceAll("/+$","")))throw new IOException("O servidor da versão pública é gerenciado pelo PANEL.");}
    private javax.crypto.SecretKey key()throws Exception {KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);if(!ks.containsAlias("panel-session")){KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");generator.init(new KeyGenParameterSpec.Builder("panel-session",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());generator.generateKey();}return (javax.crypto.SecretKey)ks.getKey("panel-session",null);}
    void authenticate(String path,JSONObject body)throws Exception {JSONObject result=(JSONObject)json("POST",path,body);String next=result.getString("token");JSONObject nextUser=result.getJSONObject("user");Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());String encrypted=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(next.getBytes(java.nio.charset.StandardCharsets.UTF_8)),Base64.NO_WRAP);token=next;user=nextUser;prefs.edit().putString("session",encrypted).putString("user",user.toString()).apply();}
    void clear(){token="";user=new JSONObject();prefs.edit().remove("session").remove("user").apply();}
    private Request.Builder request(String path)throws IOException {if(base().isEmpty())throw new IOException("Configure o endereço HTTPS da API em Ajustes.");Request.Builder builder=new Request.Builder().url(base()+path);if(!token.isEmpty())builder.header("Authorization","Bearer "+token);return builder;}
    private void check(Response r)throws Exception {if(r.isSuccessful())return;String message="Servidor retornou erro "+r.code();if(r.body()!=null){String text=r.body().string();try{message=new JSONObject(text).optString("detail",message);}catch(JSONException ignored){}}if(r.code()==401)clear();throw new IOException(message);}
    Object json(String method,String path,JSONObject data)throws Exception {RequestBody body=data==null?null:RequestBody.create(data.toString(),MediaType.get("application/json"));if(body==null&&(method.equals("POST")||method.equals("PUT")))body=RequestBody.create("",null);try(Response r=client.newCall(request(path).method(method,body).build()).execute()){check(r);if(r.code()==204||r.body()==null)return new JSONObject();return new JSONTokener(r.body().string()).nextValue();}}
    byte[] bytes(String path)throws Exception {try(Response r=client.newCall(request(path).get().build()).execute()){check(r);if(r.body()==null)throw new IOException("Resposta vazia.");if(r.body().contentLength()>10*1024*1024)throw new IOException("Capa grande demais.");try(InputStream in=r.body().byteStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(out.size()+n>10*1024*1024)throw new IOException("Capa grande demais.");out.write(b,0,n);}return out.toByteArray();}}}
    LibraryStore.Book download(String path,String filename,LibraryStore store,Transfer transfer)throws Exception {try(Response r=client.newCall(request(path).get().build()).execute()){check(r);if(r.body()==null)throw new IOException("Arquivo indisponível.");transfer.total=r.body().contentLength();try(InputStream in=new FilterInputStream(r.body().byteStream()){
        public int read(byte[] b,int o,int len)throws IOException {while(transfer.paused&&!transfer.cancelled){try{Thread.sleep(100);}catch(InterruptedException e){throw new InterruptedIOException();}}if(transfer.cancelled)throw new IOException("Download cancelado.");int n=super.read(b,o,len);if(n>0)transfer.received+=n;return n;}
    }){return store.importStream(in,filename);}}}
    void upload(String id,File file)throws Exception {RequestBody data=new MultipartBody.Builder().setType(MultipartBody.FORM).addFormDataPart("file",file.getName(),RequestBody.create(file,MediaType.get("application/octet-stream"))).build();try(Response r=client.newCall(request("/publications/"+id+"/file").put(data).build()).execute()){check(r);}}
    JSONObject checkAndroidUpdate()throws Exception {Request r=new Request.Builder().url("https://api.github.com/repos/lucrazy-fn/PANEL-ComicBookReader/releases/latest").header("Accept","application/vnd.github+json").build();try(Response response=client.newCall(r).execute()){if(!response.isSuccessful()||response.body()==null)throw new IOException("Não foi possível verificar atualizações.");return new JSONObject(response.body().string());}}
    static final class Transfer {volatile long received,total;volatile boolean paused,cancelled,finished;volatile String error="";String title;}
}

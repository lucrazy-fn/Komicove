package com.lucrazy.komicove;

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
    boolean validateSession()throws Exception {if(!signedIn())return false;JSONObject fresh=(JSONObject)json("GET","/auth/me",null);user=fresh;prefs.edit().putString("user",user.toString()).apply();return true;}
    void updateCachedUser(JSONObject fresh){user=fresh==null?new JSONObject():fresh;prefs.edit().putString("user",user.toString()).apply();}
    void base(String value)throws Exception {if(value!=null&&!value.trim().isEmpty()&&!DEFAULT_BASE.equals(value.trim().replaceAll("/+$","")))throw new IOException("O servidor da versão pública é gerenciado pelo Komicove.");}
    private javax.crypto.SecretKey key()throws Exception {KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);if(!ks.containsAlias("panel-session")){KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");generator.init(new KeyGenParameterSpec.Builder("panel-session",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());generator.generateKey();}return (javax.crypto.SecretKey)ks.getKey("panel-session",null);}
    void authenticate(String path,JSONObject body)throws Exception {JSONObject result=(JSONObject)json("POST",path,body);String next=result.getString("token");JSONObject nextUser=result.getJSONObject("user");Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());String encrypted=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(next.getBytes(java.nio.charset.StandardCharsets.UTF_8)),Base64.NO_WRAP);token=next;user=nextUser;prefs.edit().putString("session",encrypted).putString("user",user.toString()).apply();}
    void clear(){token="";user=new JSONObject();prefs.edit().remove("session").remove("user").apply();}
    private Request.Builder request(String path)throws IOException {if(base().isEmpty())throw new IOException("Configure o endereço HTTPS da API em Ajustes.");Request.Builder builder=new Request.Builder().url(base()+path);if(!token.isEmpty())builder.header("Authorization","Bearer "+token);return builder;}
    private void check(Response r)throws Exception {if(r.isSuccessful())return;int code=r.code();String message=code>=500?"O servidor está temporariamente indisponível. Tente novamente em instantes.":code==429?"Muitas tentativas em pouco tempo. Aguarde um momento e tente novamente.":code==403?"Você não tem permissão para realizar esta ação.":code==404?"O conteúdo solicitado não foi encontrado.":"Não foi possível concluir a solicitação.";if(r.body()!=null){String text=r.body().string();try{Object detail=new JSONObject(text).opt("detail");if(detail instanceof JSONArray)message=validationMessage((JSONArray)detail,message);else if(code<500&&code!=429&&detail!=null&&!JSONObject.NULL.equals(detail))message=String.valueOf(detail);}catch(JSONException ignored){}}if(code==401){clear();message="Sua sessão expirou. Entre novamente.";}throw new IOException(message);}
    private String validationMessage(JSONArray details,String fallback){
        if(details.length()==0)return fallback;
        JSONObject item=details.optJSONObject(0);if(item==null)return fallback;
        JSONArray location=item.optJSONArray("loc");String field=location!=null&&location.length()>0?location.optString(location.length()-1):"";
        String type=item.optString("type"),raw=item.optString("msg");
        if("username".equals(field)&&type.contains("too_short"))return "O usuário deve ter pelo menos 3 caracteres.";
        if("password".equals(field)&&type.contains("too_short"))return "A senha deve ter pelo menos 8 caracteres.";
        if("email".equals(field))return "Informe um e-mail válido.";
        if("display_name".equals(field))return "Informe um nome de exibição válido.";
        String label="username".equals(field)?"usuário":"password".equals(field)?"senha":"email".equals(field)?"e-mail":field.replace('_',' ');
        return label.isEmpty()?(raw.isEmpty()?fallback:raw):"Verifique o campo "+label+".";
    }
    Object json(String method,String path,JSONObject data)throws Exception {RequestBody body=data==null?null:RequestBody.create(data.toString(),MediaType.get("application/json"));if(body==null&&(method.equals("POST")||method.equals("PUT")))body=RequestBody.create("",null);try(Response r=client.newCall(request(path).method(method,body).build()).execute()){check(r);if(r.code()==204||r.body()==null)return new JSONObject();return new JSONTokener(r.body().string()).nextValue();}}
    byte[] bytes(String path)throws Exception {try(Response r=client.newCall(request(path).get().build()).execute()){check(r);if(r.body()==null)throw new IOException("Resposta vazia.");if(r.body().contentLength()>10*1024*1024)throw new IOException("Capa grande demais.");try(InputStream in=r.body().byteStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(out.size()+n>10*1024*1024)throw new IOException("Capa grande demais.");out.write(b,0,n);}return out.toByteArray();}}}
    void uploadAvatar(File file)throws Exception {RequestBody data=new MultipartBody.Builder().setType(MultipartBody.FORM).addFormDataPart("avatar","avatar.jpg",RequestBody.create(file,MediaType.get("image/jpeg"))).build();try(Response r=client.newCall(request("/account/avatar").put(data).build()).execute()){check(r);}}
    LibraryStore.Book download(String path,String filename,LibraryStore store,Transfer transfer)throws Exception {try(Response r=client.newCall(request(path).get().build()).execute()){check(r);if(r.body()==null)throw new IOException("Arquivo indisponível.");transfer.total=r.body().contentLength();try(InputStream in=new FilterInputStream(r.body().byteStream()){
        public int read(byte[] b,int o,int len)throws IOException {while(transfer.paused&&!transfer.cancelled){try{Thread.sleep(100);}catch(InterruptedException e){throw new InterruptedIOException();}}if(transfer.cancelled)throw new IOException("Download cancelado.");int n=super.read(b,o,len);if(n>0)transfer.received+=n;return n;}
    }){return store.importStream(in,filename);}}}
    void upload(String id,File file)throws Exception {RequestBody data=new MultipartBody.Builder().setType(MultipartBody.FORM).addFormDataPart("file",file.getName(),RequestBody.create(file,MediaType.get("application/octet-stream"))).build();try(Response r=client.newCall(request("/publications/"+id+"/file").put(data).build()).execute()){check(r);}}
    private JSONObject githubLatest(String repository)throws Exception {
        String url="https://api.github.com/repos/"+repository+"/releases/latest";
        OkHttpClient github=client.newBuilder().readTimeout(10,TimeUnit.SECONDS).build();
        for(int redirect=0;redirect<4;redirect++){
            Request request=new Request.Builder().url(url).header("Accept","application/vnd.github+json").build();
            try(Response response=github.newCall(request).execute()){
                if(response.code()==404)return null;
                if(response.code()==301||response.code()==302||response.code()==307||response.code()==308){
                    String next=response.header("Location");if(next==null)throw new IOException("Não foi possível verificar atualizações.");
                    HttpUrl parsed=HttpUrl.get(url).resolve(next);if(parsed==null||!parsed.isHttps()||!parsed.host().equals("api.github.com"))throw new IOException("Não foi possível verificar atualizações.");url=parsed.toString();continue;
                }
                if(!response.isSuccessful()||response.body()==null)throw new IOException("Não foi possível verificar atualizações.");
                return new JSONObject(response.body().string());
            }
        }throw new IOException("Não foi possível verificar atualizações.");
    }
    JSONArray updates()throws Exception {
        java.util.List<JSONObject> found=new java.util.ArrayList<>();int successes=0;
        for(String repository:AppUpdates.REPOSITORIES){try{JSONObject release=githubLatest(repository);successes++;JSONObject item=AppUpdates.release(release,repository,BuildConfig.VERSION_NAME);if(item!=null)found.add(item);}catch(Exception ignored){}}
        try{JSONArray messages=(JSONArray)json("GET","/updates",null);successes++;for(int i=0;i<messages.length();i++)found.add(AppUpdates.announcement(messages.getJSONObject(i)));}catch(Exception ignored){}
        if(successes==0)throw new IOException("Não foi possível verificar atualizações.");
        return AppUpdates.merge(found,BuildConfig.VERSION_NAME);
    }
    JSONObject checkAndroidUpdate()throws Exception {return AppUpdates.automatic(updates(),BuildConfig.VERSION_NAME,java.util.Collections.emptySet());}
    static final class Transfer {volatile long received,total;volatile boolean paused,cancelled,finished;volatile String error="";String title;}
}

package com.lucrazy.komicove;

import java.math.BigInteger;
import java.net.URI;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.regex.*;
import org.json.*;

final class AppUpdates {
    static final String[] REPOSITORIES={"lucrazy-fn/PANEL-ComicBookReader","lucrazy-fn/Komicove"};
    static final String SITE="https://lucrazy-fn.github.io/Komicove/#downloads";
    private static final Pattern VERSION=Pattern.compile("[vV]?(\\d+)\\.(\\d+)(?:\\.(\\d+))?(?:-([0-9A-Za-z.-]+))?(?:\\+[0-9A-Za-z.-]+)?");
    private static final Pattern ANDROID=Pattern.compile("^[ \\t]*(?:[-*#]+[ \\t]*)?android[ \\t]*(?:version[ \\t]*)?(\\d+\\.\\d+(?:\\.\\d+)?)",Pattern.CASE_INSENSITIVE|Pattern.MULTILINE);
    private static final class Version implements Comparable<Version> {
        final BigInteger[] numbers;final String suffix,key;
        Version(Matcher match){numbers=new BigInteger[]{new BigInteger(match.group(1)),new BigInteger(match.group(2)),new BigInteger(match.group(3)==null?"0":match.group(3))};suffix=match.group(4);key=numbers[0]+"."+numbers[1]+"."+numbers[2]+(suffix==null?"":"-"+suffix);}
        public int compareTo(Version other){for(int i=0;i<3;i++){int comparison=numbers[i].compareTo(other.numbers[i]);if(comparison!=0)return comparison;}if(suffix==null)return other.suffix==null?0:1;if(other.suffix==null)return -1;String[] a=suffix.split("\\."),b=other.suffix.split("\\.");for(int i=0;i<Math.min(a.length,b.length);i++){boolean an=a[i].matches("\\d+"),bn=b[i].matches("\\d+");int comparison=an&&bn?new BigInteger(a[i]).compareTo(new BigInteger(b[i])):an!=bn?(an?-1:1):a[i].compareTo(b[i]);if(comparison!=0)return comparison;}return Integer.compare(a.length,b.length);}
    }
    private static Version version(String value){if(value==null||value.length()>64)return null;Matcher match=VERSION.matcher(value.trim());return match.matches()?new Version(match):null;}
    static boolean compatible(String remote,String current){Version a=version(remote),b=version(current);return a!=null&&b!=null&&(b.numbers[0].signum()!=0||a.numbers[0].signum()==0);}
    static boolean newer(String remote,String current){Version a=version(remote),b=version(current);return compatible(remote,current)&&a.compareTo(b)>0;}
    static String androidVersion(String tag,String notes){Matcher match=ANDROID.matcher(notes==null?"":notes);return match.find()?match.group(1):tag.replaceFirst("^[vV]","");}
    static String safeUrl(String value){
        if(SITE.equals(value))return value;
        try{URI uri=new URI(value).normalize();if(!"https".equals(uri.getScheme())||!"github.com".equalsIgnoreCase(uri.getHost())||uri.getUserInfo()!=null||uri.getPort()!=-1||uri.getQuery()!=null||uri.getFragment()!=null)return "";
            String path=uri.getPath().toLowerCase(Locale.ROOT);for(String part:path.split("/"))if(part.equals(".")||part.equals(".."))return "";for(String repo:REPOSITORIES){String root="/"+repo.toLowerCase(Locale.ROOT)+"/releases";if(path.equals(root)||path.startsWith(root+"/"))return value;}
        }catch(Exception ignored){}return "";
    }
    static JSONObject release(JSONObject raw,String repository,String current)throws JSONException {
        if(raw==null||raw.optBoolean("draft")||raw.optBoolean("prerelease")||!compatible(raw.optString("tag_name"),current))return null;
        String notes=raw.optString("body"),tag=androidVersion(raw.optString("tag_name"),notes);
        String title=raw.optString("name");if(title.trim().isEmpty())title=raw.optString("tag_name");
        return new JSONObject().put("title",title).put("version",tag).put("notes",notes)
            .put("source","github").put("repository",repository).put("created_at",raw.optString("published_at",raw.optString("created_at")))
            .put("url",safeUrl(raw.optString("html_url","https://github.com/"+repository+"/releases")));
    }
    static JSONObject announcement(JSONObject raw)throws JSONException {
        JSONObject copy=new JSONObject(raw.toString());copy.put("version",androidVersion(raw.optString("version"),raw.optString("notes")));
        copy.put("source","panel").put("url",safeUrl(raw.optString("download_url")));return copy;
    }
    static JSONArray merge(List<JSONObject> items,String current)throws JSONException {
        Map<String,JSONObject> unique=new LinkedHashMap<>();
        for(JSONObject item:items){if(item==null)continue;Version parsed=version(item.optString("version"));if(parsed==null)continue;JSONObject previous=unique.get(parsed.key);
            boolean panel="panel".equals(item.optString("source")),previousPanel=previous!=null&&"panel".equals(previous.optString("source"));
            if(previous==null||(panel&&!previousPanel)||(panel==previousPanel&&item.optString("created_at").compareTo(previous.optString("created_at"))>0))unique.put(parsed.key,item);
        }
        List<JSONObject> sorted=new ArrayList<>(unique.values());sorted.sort((a,b)->{boolean ac=compatible(a.optString("version"),current),bc=compatible(b.optString("version"),current);return ac!=bc?(ac?-1:1):version(b.optString("version")).compareTo(version(a.optString("version")));});
        JSONArray result=new JSONArray();for(JSONObject item:sorted)result.put(item);return result;
    }
    static JSONObject automatic(JSONArray items,String current,Set<String> seen){for(int i=0;i<items.length();i++){JSONObject item=items.optJSONObject(i);if(item==null)continue;if(newer(item.optString("version"),current)||("panel".equals(item.optString("source"))&&!seen.contains(item.optString("id"))&&compatible(item.optString("version"),current)))return item;}return null;}
    static String date(String value){try{return OffsetDateTime.parse(value).atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"));}catch(Exception ignored){return "";}}
    static String plainNotes(String notes){return (notes==null?"":notes).replaceAll("(?m)^#{1,6}\\s*","").replaceAll("!\\[([^\\]]*)\\]\\([^)]*\\)","$1").replaceAll("\\[([^\\]]+)\\]\\(([^)]+)\\)","$1 ($2)").replaceAll("`+|\\*\\*","").trim();}
}

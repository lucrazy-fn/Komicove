package com.lucrazy.komicove;

import org.json.*;

/** Only reading state is enabled. Other local domains remain untouched by merges. */
final class LibrarySync {
    interface Transport { JSONArray exchange(JSONArray entries)throws Exception; }
    static boolean run(LibraryStore store,Transport transport)throws Exception {
        JSONArray entries=store.prepareSyncPayload();JSONObject merged=new JSONObject();
        for(int offset=0;offset<Math.max(1,entries.length());offset+=5000){
            JSONArray batch=new JSONArray();for(int i=offset;i<Math.min(entries.length(),offset+5000);i++)batch.put(entries.getJSONObject(i));
            JSONArray remote=transport.exchange(batch);
            for(int i=0;i<remote.length();i++){JSONObject row=remote.getJSONObject(i);merged.put(row.getString("item_key"),row);}
        }
        JSONArray remote=new JSONArray();java.util.Iterator<String> keys=merged.keys();while(keys.hasNext())remote.put(merged.get(keys.next()));
        return store.applySyncResponse(remote);
    }
}

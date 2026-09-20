'use strict';
class LiveSession {
  constructor(id,token,onDisconnect){
    this.id=id;this.pending=new Map();this.states=new Map();this.waiters=new Set();this.serial=0;this.closed=false;
    this.socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/live/${id}`);
    this.ready=new Promise((resolve,reject)=>{
      this.readyReject=reject;
      this.socket.onopen=()=>this.socket.send(JSON.stringify({token}));
      this.socket.onmessage=event=>{
        const msg=JSON.parse(event.data);
        if(msg.type==='hello'){resolve(msg.data);return;}
        if(msg.type==='reply'){
          const pending=this.pending.get(msg.id);if(!pending)return;
          this.pending.delete(msg.id);clearTimeout(pending.timer);
          if(msg.status>=400){const error=new Error(msg.data.detail||'Request failed');error.status=msg.status;pending.reject(error);}
          else pending.resolve(msg.data);
          return;
        }
        if(msg.session_id!==this.id)return;
        const key=`${msg.type}:${msg.data.id}`,previous=this.states.get(key);
        if(msg.type==='session'&&previous&&previous.revision>msg.data.revision)return;
        this.states.set(key,msg.data);
        if(this.states.size>128)this.states.delete(this.states.keys().next().value);
        for(const waiter of [...this.waiters])waiter();
      };
      this.socket.onclose=()=>{this.closed=true;const error=new Error('Connection lost. Reopen the saved session to reconnect safely.');reject(error);
        for(const pending of this.pending.values()){clearTimeout(pending.timer);pending.reject(error);}this.pending.clear();
        for(const waiter of [...this.waiters])waiter();onDisconnect();};
      this.socket.onerror=()=>reject(new Error('The live connection could not open. Refresh and try again.'));
    });
  }
  async request(path,body,identity){
    await this.ready;if(this.closed)throw new Error('The live connection is closed. Reopen your saved session.');
    const id=String(++this.serial);
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error('The local request timed out. Reopen the session before retrying.'));this.close();},65000);
      this.pending.set(id,{resolve,reject,timer});
      this.socket.send(JSON.stringify({id,path,method:body===undefined?'GET':'POST',body,session_id:this.id,...identity}));
    });
  }
  wait(kind,id,predicate){
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.waiters.delete(check);reject(new Error('The local response timed out. Retry or reopen the saved session.'));},65000);
      const check=()=>{
        if(this.closed){clearTimeout(timer);this.waiters.delete(check);reject(new Error('Live connection closed'));return;}
        const value=this.states.get(`${kind}:${id}`);
        if(value&&predicate(value)){clearTimeout(timer);this.waiters.delete(check);resolve(value);}
      };
      this.waiters.add(check);check();
    });
  }
  close(){this.socket.close();}
}

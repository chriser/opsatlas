/* One speaker at a time. A prepared question waits for a committed cue.
   User speech invalidates both current playback and pending audio. */
export class AudioFloor {
  constructor(makeAudio=src=>new Audio(src)){this.makeAudio=makeAudio;this.current=null;this.queue=[];this.generation=0;}
  play(src,onStart=null){return new Promise(resolve=>{this.queue.push({src,onStart,resolve,generation:this.generation});this.drain();});}
  drain(){
    if(this.current||!this.queue.length)return;
    const item=this.queue.shift();
    if(item.generation!==this.generation){item.resolve(false);this.drain();return;}
    const audio=this.makeAudio(item.src);this.current={audio,item};
    let started=false;audio.onplaying=()=>{if(!started&&this.current?.audio===audio){started=true;item.onStart?.();}};
    const finish=ok=>{if(this.current?.audio!==audio)return;this.current=null;item.resolve(ok);this.drain();};
    audio.onended=()=>finish(true);audio.onerror=()=>finish(false);
    Promise.resolve(audio.play()).catch(()=>finish(false));
  }
  interrupt(){
    this.generation++;
    for(const item of this.queue)item.resolve(false);this.queue=[];
    if(this.current){const {audio,item}=this.current;this.current=null;audio.pause();audio.removeAttribute?.('src');item.resolve(false);}
  }
}

export function decision({speechMs,silenceMs,probability,patienceMs,invited}){
  if(speechMs>=500&&silenceMs>=1000&&probability!==null&&probability>=.7)return 'question';
  if(patienceMs>0&&silenceMs>=patienceMs&&!invited)return 'patience';
  return 'listen';
}

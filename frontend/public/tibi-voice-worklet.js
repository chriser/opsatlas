/* Tibi's duplex PCM worklet for the OpsAtlas control panel (same processor as services/sme_interviewer/web/voice-worklet.js). */
/* Local duplex PCM processing. No network or storage in the audio thread. */
class VoiceProcessor extends AudioWorkletProcessor {
  constructor(){
    super();this.record=false;this.sum=0;this.count=0;this.phase=0;this.frame=new Int16Array(512);this.fill=0;
    this.lastOutput=0;this.inGap=true;this.hasOutput=false;this.fadeLeft=0;this.fadeFrom=0;this.fadeSamples=Math.max(1,Math.round(sampleRate*.005));
    this.generation='';this.queue=[];this.position=0;this.started=false;this.prebufferMs=0;this.buffering=true;this.ended=false;
    this.port.onmessage=({data:d})=>{
      if(d.type==='configure')this.prebufferMs=Math.max(0,Math.min(200,d.prebufferMs||0));
      if(d.type==='begin'&&d.generation===this.generation)this.ended=false;
      if(d.type==='end'&&d.generation===this.generation)this.ended=true;
      if(d.type==='capture'){this.record=d.enabled;this.fill=0;this.sum=0;this.count=0;this.phase=0;}
      if(d.type==='reset'){this.fadeFrom=this.lastOutput;this.fadeLeft=this.hasOutput?this.fadeSamples:0;this.inGap=true;this.generation=d.generation;this.queue=[];this.position=0;this.started=false;this.buffering=true;this.ended=false;}
      if(d.type==='audio'&&d.generation===this.generation){
        if(this.queue.reduce((s,x)=>s+x.pcm.length/x.rate,0)>30){this.queue=[];this.port.postMessage({type:'overflow'});return;}
        this.queue.push({pcm:new Int16Array(d.pcm),rate:d.rate,index:d.index,cue:!!d.cue});
      }
    };
  }
  smoothGap(value,gap){
    if(!gap&&!this.hasOutput){this.fadeFrom=0;this.fadeLeft=this.fadeSamples;}
    if(gap!==this.inGap&&this.hasOutput){this.fadeFrom=this.lastOutput;this.fadeLeft=this.fadeSamples;}
    this.inGap=gap;
    if(!gap)this.hasOutput=true;
    if(this.fadeLeft){const mix=this.fadeLeft--/this.fadeSamples;value=this.fadeFrom*mix+value*(1-mix);}
    this.lastOutput=value;return value;
  }
  process(inputs,outputs){
    const input=inputs[0]?.[0],output=outputs[0][0];
    for(let i=0;i<output.length;i++){
      if(this.record){
        this.sum+=input?.[i]||0;this.count++;this.phase+=16000;
        if(this.phase>=sampleRate){
          this.phase-=sampleRate;const value=Math.max(-1,Math.min(1,this.sum/this.count));this.sum=0;this.count=0;
          this.frame[this.fill++]=Math.round(value*32767);
          if(this.fill===512){const pcm=this.frame.buffer;this.port.postMessage({type:'frame',pcm},[pcm]);this.frame=new Int16Array(512);this.fill=0;}
        }
      }
      if(this.buffering){
        const seconds=this.queue.reduce((n,x,j)=>n+(x.pcm.length-(j===0?this.position:0))/x.rate,0);
        if(!seconds||(!this.ended&&seconds*1000<this.prebufferMs)){output[i]=this.smoothGap(0,true);continue;}
        this.buffering=false;
      }
      const next=this.queue[0];
      if(!next){output[i]=this.smoothGap(0,true);continue;}
      if(!next.announced){next.announced=true;this.port.postMessage({type:"chunk_started",generation:this.generation,index:next.index,cue:next.cue});}
      if(!this.started){this.started=true;this.port.postMessage({type:'playing',generation:this.generation,contextTime:currentTime+i/sampleRate});}
      const j=Math.floor(this.position),fraction=this.position-j;
      const following=j+1<next.pcm.length?next.pcm[j+1]:
        (this.queue[1]?.rate===next.rate?this.queue[1].pcm[0]:next.pcm[j]);
      output[i]=this.smoothGap(((next.pcm[j]||0)*(1-fraction)+(following||0)*fraction)/32768,false);
      this.position+=next.rate/sampleRate;
      if(this.position>=next.pcm.length){this.queue.shift();this.position-=next.pcm.length;this.port.postMessage({type:'consumed',generation:this.generation,index:next.index});if(!this.queue.length){this.buffering=true;if(!this.ended&&this.prebufferMs)this.port.postMessage({type:'underrun',generation:this.generation});this.port.postMessage({type:'drained',generation:this.generation});}}
    }
    return true;
  }
}
registerProcessor('voice-pcm',VoiceProcessor);

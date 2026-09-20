/* Local duplex PCM processing. No network or storage in the audio thread. */
class VoiceProcessor extends AudioWorkletProcessor {
  constructor(){
    super();this.record=false;this.sum=0;this.count=0;this.phase=0;this.frame=new Int16Array(512);this.fill=0;
    this.generation='';this.queue=[];this.position=0;this.started=false;
    this.port.onmessage=({data:d})=>{
      if(d.type==='capture'){this.record=d.enabled;this.fill=0;this.sum=0;this.count=0;this.phase=0;}
      if(d.type==='reset'){this.generation=d.generation;this.queue=[];this.position=0;this.started=false;}
      if(d.type==='audio'&&d.generation===this.generation){
        if(this.queue.reduce((s,x)=>s+x.pcm.length/x.rate,0)>30){this.queue=[];this.port.postMessage({type:'overflow'});return;}
        this.queue.push({pcm:new Int16Array(d.pcm),rate:d.rate,index:d.index});
      }
    };
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
      const next=this.queue[0];
      if(!next){output[i]=0;continue;}
      if(!this.started){this.started=true;this.port.postMessage({type:'playing',generation:this.generation,contextTime:currentTime+i/sampleRate});}
      const j=Math.floor(this.position),fraction=this.position-j;
      output[i]=((next.pcm[j]||0)*(1-fraction)+(next.pcm[Math.min(j+1,next.pcm.length-1)]||0)*fraction)/32768;
      this.position+=next.rate/sampleRate;
      if(this.position>=next.pcm.length){this.queue.shift();this.position-=next.pcm.length;this.port.postMessage({type:'consumed',generation:this.generation,index:next.index});if(!this.queue.length)this.port.postMessage({type:'drained',generation:this.generation});}
    }
    return true;
  }
}
registerProcessor('voice-pcm',VoiceProcessor);

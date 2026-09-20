'use strict';
// All milestones use one page's monotonic clock; null means not observed.
class TurnTiming {
  constructor(session, source, send, clock=()=>performance.now(), pageId=TurnTiming.pageId) {
    this.sessionId=session.id;this.send=send;this.clock=clock;this.origin=clock();
    this.data={version:1,id:crypto.randomUUID(),page_id:pageId,generation_id:crypto.randomUUID(),
      revision:session.revision,sequence:0,source,runtime:'unknown',endpoint_kind:'none',status:'open',
      marks:Object.fromEntries(['capture_start','speech_end','endpoint','encoded','asr_requested','final_transcript',
        'confirmation_start','confirmed','plan_requested','first_token','question_ready','tts_requested','audio_ready',
        'first_audio','playback_start'].map(key=>[key,null]))};
  }
  mark(key) {
    if(this.data.status!=='open'||this.data.marks[key]!==null)return;
    this.data.marks[key]=Math.round((this.clock()-this.origin)*1000)/1000;
    this.flush();
  }
  finish(status) {if(this.data.status!=='open')return;this.data.status=status;this.flush();}
  flush() {this.data.sequence++;this.send(this.sessionId,JSON.parse(JSON.stringify(this.data)));}
}
TurnTiming.pageId=crypto.randomUUID();

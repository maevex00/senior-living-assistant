// Emit ~128 ms chunks of 16 kHz mono audio. Linear interpolation keeps fractional
// phase across render quanta; sampleRate is the actual AudioContext rate.
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pending = [];
    this.position = 0;
    this.output = [];
  }
  process(inputs) {
    const channels = inputs[0];
    if (!channels?.length) return true;
    const mono = channels[0].map(
      (_, i) => channels.reduce((sum, c) => sum + c[i], 0) / channels.length,
    );
    this.pending.push(...mono);
    const step = sampleRate / 16000;
    while (this.position + 1 < this.pending.length) {
      const i = Math.floor(this.position),
        f = this.position - i;
      this.output.push(this.pending[i] * (1 - f) + this.pending[i + 1] * f);
      this.position += step;
      if (this.output.length === 2048) {
        const chunk = new Float32Array(this.output);
        this.port.postMessage(chunk, [chunk.buffer]);
        this.output = [];
      }
    }
    const used = Math.floor(this.position);
    this.pending.splice(0, used);
    this.position -= used;
    return true;
  }
}
registerProcessor("pcm-capture", PCMProcessor);

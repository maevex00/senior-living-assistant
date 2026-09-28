export function pcm16(samples: Float32Array): string {
  const buffer = new ArrayBuffer(samples.length * 2),
    view = new DataView(buffer);
  samples.forEach((s, i) => {
    const n = Math.max(-1, Math.min(1, s));
    view.setInt16(i * 2, Math.round(n * (n < 0 ? 32768 : 32767)), true);
  });
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary);
}

export function decodePCM(data: string): Float32Array {
  const binary = atob(data),
    buffer = new ArrayBuffer(binary.length),
    bytes = new Uint8Array(buffer);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const view = new DataView(buffer),
    result = new Float32Array(Math.floor(binary.length / 2));
  for (let i = 0; i < result.length; i++)
    result[i] = view.getInt16(i * 2, true) / 32768;
  return result;
}

export class AudioPlayback {
  private next = 0;
  private sources = new Set<AudioBufferSourceNode>();
  constructor(private context: AudioContext) {}
  play(data: string) {
    const samples = decodePCM(data);
    const buffer = this.context.createBuffer(1, samples.length, 24000);
    buffer.copyToChannel(new Float32Array(samples), 0);
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);
    source.onended = () => {
      this.sources.delete(source);
      source.disconnect();
    };
    this.next = Math.max(this.next, this.context.currentTime);
    source.start(this.next);
    this.next += buffer.duration;
    this.sources.add(source);
  }
  clear() {
    for (const source of this.sources) {
      source.stop();
      source.disconnect();
    }
    this.sources.clear();
    this.next = 0;
  }
}

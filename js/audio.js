// Web Audio APIによるチップチューン風効果音 + BGM
// 外部ファイル不要、すべて合成
window.Audio8 = (function() {
  let ctx = null;
  let masterGain = null;
  let bgmNode = null;
  let muted = false;

  function init() {
    if (ctx) return ctx;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
    masterGain = ctx.createGain();
    masterGain.gain.value = 0.25;
    masterGain.connect(ctx.destination);
    return ctx;
  }

  // 単音を鳴らす
  function beep(freq, duration, type = 'square', volume = 0.3) {
    if (muted) return;
    init();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    gain.gain.value = 0;
    gain.gain.linearRampToValueAtTime(volume, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(masterGain);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + duration);
  }

  // 周波数を上下する効果音
  function sweep(f1, f2, duration, type = 'square', volume = 0.3) {
    if (muted) return;
    init();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(f1, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(f2, ctx.currentTime + duration);
    gain.gain.value = 0;
    gain.gain.linearRampToValueAtTime(volume, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(masterGain);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  }

  // ノイズ（打撃音用）
  function noise(duration, freq = 200, volume = 0.3) {
    if (muted) return;
    init();
    if (!ctx) return;
    const bufSize = ctx.sampleRate * duration;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < bufSize; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / bufSize, 2);
    const src = ctx.createBufferSource();
    const filter = ctx.createBiquadFilter();
    const gain = ctx.createGain();
    filter.type = 'lowpass';
    filter.frequency.value = freq;
    gain.gain.value = volume;
    src.buffer = buf;
    src.connect(filter);
    filter.connect(gain);
    gain.connect(masterGain);
    src.start();
  }

  // 効果音群
  const SFX = {
    punch:   () => { noise(0.08, 400, 0.4); beep(180, 0.05, 'square', 0.2); },
    kick:    () => { noise(0.15, 250, 0.5); sweep(150, 80, 0.15, 'sawtooth', 0.3); },
    special: () => { sweep(800, 200, 0.4, 'sawtooth', 0.4); noise(0.3, 100, 0.4); },
    guard:   () => { beep(440, 0.1, 'triangle', 0.2); beep(220, 0.1, 'triangle', 0.2); },
    hit:     () => { noise(0.1, 600, 0.5); },
    miss:    () => { sweep(300, 100, 0.15, 'square', 0.15); },
    victory: () => {
      [523, 659, 784, 1047].forEach((f, i) => setTimeout(() => beep(f, 0.15, 'square', 0.3), i * 100));
    },
    defeat:  () => {
      [400, 300, 200, 100].forEach((f, i) => setTimeout(() => beep(f, 0.2, 'sawtooth', 0.3), i * 150));
    },
    bontan:  () => {
      [659, 880, 1320].forEach((f, i) => setTimeout(() => beep(f, 0.1, 'square', 0.3), i * 80));
      setTimeout(() => sweep(220, 800, 0.5, 'triangle', 0.25), 300);
    },
    train:   () => {
      // 発車ベル風
      [880, 880, 880].forEach((f, i) => setTimeout(() => beep(f, 0.1, 'sine', 0.25), i * 150));
      // ガタンゴトン
      setTimeout(() => {
        for (let i = 0; i < 6; i++) {
          setTimeout(() => { noise(0.05, 150, 0.2); beep(100, 0.05, 'sine', 0.15); }, i * 120);
        }
      }, 500);
    },
    menu:    () => beep(660, 0.05, 'square', 0.2),
    final:   () => {
      // 最終ボス登場SE
      sweep(50, 800, 1.5, 'sawtooth', 0.4);
      setTimeout(() => noise(0.3, 80, 0.5), 1500);
    }
  };

  // BGM（駅マップ画面で軽くループ）
  function startBgm(mode = 'map') {
    if (muted) return;
    stopBgm();
    init();
    if (!ctx) return;

    // 簡易シーケンサ：駅メロ風の和風メロディ
    const mapMelody = [
      { f: 523, d: 0.3 }, { f: 587, d: 0.3 }, { f: 659, d: 0.3 }, { f: 784, d: 0.3 },
      { f: 880, d: 0.3 }, { f: 784, d: 0.3 }, { f: 659, d: 0.3 }, { f: 587, d: 0.6 },
      { f: 523, d: 0.3 }, { f: 659, d: 0.3 }, { f: 784, d: 0.3 }, { f: 1047, d: 0.3 },
      { f: 880, d: 0.6 }, { f: 784, d: 0.3 }, { f: 659, d: 0.3 }, { f: 523, d: 0.6 }
    ];
    const battleMelody = [
      { f: 392, d: 0.15 }, { f: 466, d: 0.15 }, { f: 523, d: 0.15 }, { f: 466, d: 0.15 },
      { f: 392, d: 0.15 }, { f: 466, d: 0.15 }, { f: 523, d: 0.15 }, { f: 622, d: 0.3 },
      { f: 523, d: 0.15 }, { f: 466, d: 0.15 }, { f: 392, d: 0.15 }, { f: 466, d: 0.15 },
      { f: 523, d: 0.3 }, { f: 392, d: 0.3 }
    ];
    const titleMelody = [
      { f: 659, d: 0.4 }, { f: 784, d: 0.4 }, { f: 880, d: 0.8 },
      { f: 784, d: 0.4 }, { f: 659, d: 0.4 }, { f: 587, d: 0.8 },
      { f: 523, d: 0.4 }, { f: 587, d: 0.4 }, { f: 659, d: 1.2 }
    ];

    const melody = mode === 'battle' ? battleMelody : mode === 'title' ? titleMelody : mapMelody;
    let i = 0;
    let stopped = false;
    bgmNode = { stop: () => { stopped = true; } };

    function playNext() {
      if (stopped || muted) return;
      const note = melody[i % melody.length];
      beep(note.f, note.d * 0.9, 'square', 0.08);
      // 低音パート
      beep(note.f / 4, note.d * 0.9, 'triangle', 0.06);
      setTimeout(playNext, note.d * 1000);
      i++;
    }
    playNext();
  }

  function stopBgm() {
    if (bgmNode) { bgmNode.stop(); bgmNode = null; }
  }

  function toggleMute() {
    muted = !muted;
    if (muted) stopBgm();
    return muted;
  }

  function isMuted() { return muted; }

  return { SFX, startBgm, stopBgm, toggleMute, isMuted, init };
})();

// 戦闘システム（くにおくん風）
window.Battle = (function() {
  let state = null;

  // アーキタイプ画像があれば<img>、なければ絵文字+色矩形にフォールバック
  function applyCharSprite(charEl, archetypeId, data) {
    const body = charEl.querySelector('.char-body');
    const head = charEl.querySelector('.char-head');
    const pants = charEl.querySelector('.char-pants');

    // 既存imgを除去
    const oldImg = charEl.querySelector('img.char-sprite');
    if (oldImg) oldImg.remove();

    const imgPath = `assets/characters/${archetypeId}.png`;
    const img = new Image();
    img.onload = () => {
      // 画像があれば表示、emoji+矩形は隠す
      const sprite = document.createElement('img');
      sprite.src = imgPath;
      sprite.className = 'char-sprite';
      charEl.appendChild(sprite);
      head.style.display = 'none';
      body.style.display = 'none';
      pants.style.display = 'none';
    };
    img.onerror = () => {
      // フォールバック：絵文字+CSS矩形
      head.style.display = '';
      body.style.display = '';
      pants.style.display = '';
      body.style.background = data.color;
      head.textContent = data.emoji || '😡';
      pants.style.background = data.bontanColor || '#1a1a1a';
    };
    img.src = imgPath;
  }

  function renderScene(stationId) {
    const scene = (window.SCENES && window.SCENES[stationId]) || null;
    const bg = document.getElementById('battle-bg');
    bg.innerHTML = '';
    if (!scene) {
      bg.style.background = 'linear-gradient(180deg, #4a6fa5 0%, #7a9fcf 60%, #5a7a3a 60%, #3a5a1a 100%)';
      return;
    }
    const gh = scene.groundH || 35;
    // 空+地面のグラデを縦に貼る
    bg.style.background = `${scene.sky}`;
    // 地面のオーバーレイ
    const ground = document.createElement('div');
    ground.className = 'scene-ground';
    ground.style.cssText = `position:absolute; left:0; right:0; bottom:0; height:${gh}%; background:${scene.ground}; z-index:1;`;
    bg.appendChild(ground);
    // ステージ名表示
    const label = document.createElement('div');
    label.className = 'scene-label';
    label.textContent = scene.name;
    bg.appendChild(label);
    // 装飾オブジェ
    (scene.deco || []).forEach(d => {
      const el = document.createElement('div');
      el.className = 'scene-deco';
      el.textContent = d.e;
      el.style.cssText = `position:absolute; left:${d.x}%; top:${d.y}%; font-size:${d.s}px; transform:translate(-50%,-50%) ${d.r ? `rotate(${d.r}deg)` : ''}; z-index:${d.y > (100 - gh) ? 2 : 1}; user-select:none; pointer-events:none;`;
      bg.appendChild(el);
    });
  }

  function init(enemyData, onWin, onLose, stationId) {
    const player = window.Game.getPlayer();
    state = {
      player: { hp: player.hp, maxHp: player.maxHp, atk: player.atk, guarding: false, busy: false },
      enemy: { ...enemyData, maxHp: enemyData.hp, currentHp: enemyData.hp, busy: false },
      log: [],
      onWin,
      onLose,
      finished: false
    };

    renderScene(stationId);
    document.getElementById('enemy-name').textContent = enemyData.name;
    const enemyChar = document.getElementById('enemy-char');
    enemyChar.classList.remove('defeated', 'hit', 'attacking', 'pantsless');
    enemyChar.style.setProperty('--body', enemyData.color);
    applyCharSprite(enemyChar, enemyData.archetypeId, enemyData);

    const playerChar = document.getElementById('player-char');
    playerChar.classList.remove('defeated', 'hit', 'attacking', 'pantsless');
    applyCharSprite(playerChar, 'player', { color: '#4a90e2', emoji: '😤', bontanColor: '#3a3a3a' });

    if (enemyData.isRare) {
      log(`<span style="color:#ff3366; font-weight:bold">⚠️ レアエンカウント！本物の極道が現れた！</span>`);
    }
    log(`${enemyData.title}「${enemyData.name}」が現れた！`);
    log(`「${enemyData.voice}」`);
    updateUI();

    // Enemy AI loop
    state.enemyTimer = setInterval(enemyAction, 1400 + Math.random() * 800);
  }

  function log(msg) {
    state.log.push(msg);
    const el = document.getElementById('battle-log');
    el.innerHTML = state.log.slice(-3).map(m => `<div>${m}</div>`).join('');
    el.scrollTop = el.scrollHeight;
  }

  function updateUI() {
    const p = state.player, e = state.enemy;
    const pPct = Math.max(0, (p.hp / p.maxHp) * 100);
    const ePct = Math.max(0, (e.currentHp / e.maxHp) * 100);
    document.getElementById('player-hp-fill').style.width = pPct + '%';
    document.getElementById('enemy-hp-fill').style.width = ePct + '%';
    document.getElementById('player-hp-text').textContent = `${Math.max(0, Math.ceil(p.hp))}/${p.maxHp}`;
    document.getElementById('enemy-hp-text').textContent = `${Math.max(0, Math.ceil(e.currentHp))}/${e.maxHp}`;
  }

  function showHit(targetSelector, text) {
    const target = document.querySelector(targetSelector);
    const stage = document.getElementById('battle-stage');
    const fx = document.getElementById('hit-effect');
    const rect = target.getBoundingClientRect();
    const stageRect = stage.getBoundingClientRect();
    fx.textContent = text;
    fx.style.left = (rect.left - stageRect.left + 20) + 'px';
    fx.style.top = (rect.top - stageRect.top - 20) + 'px';
    fx.classList.remove('show');
    void fx.offsetWidth;
    fx.classList.add('show');
  }

  // 攻撃倍率（プレイヤーのatkを基準にする）
  const ACTIONS = {
    punch:   { name: 'パンチ', mult: 1.0, hit: 0.9, cd: 350,  text: 'BAM!',   sfx: 'punch' },
    kick:    { name: 'キック', mult: 1.6, hit: 0.7, cd: 600,  text: 'BOOM!',  sfx: 'kick' },
    special: { name: '必殺技', mult: 2.8, hit: 0.6, cd: 1200, text: 'WHAM!!', sfx: 'special' },
    guard:   { name: 'ガード', mult: 0,   hit: 1.0, cd: 800,  text: '',       sfx: 'guard' }
  };

  function playerAction(actionKey) {
    if (state.finished || state.player.busy) return;
    const action = ACTIONS[actionKey];
    state.player.busy = true;
    state.player.guarding = (actionKey === 'guard');

    const playerChar = document.getElementById('player-char');
    playerChar.classList.add('attacking');
    setTimeout(() => playerChar.classList.remove('attacking'), 300);
    window.Audio8 && window.Audio8.SFX[action.sfx] && window.Audio8.SFX[action.sfx]();

    if (actionKey === 'guard') {
      log(`プレイヤーはガード体勢！`);
    } else if (Math.random() < action.hit) {
      const baseDmg = state.player.atk * action.mult;
      const dmg = Math.max(1, Math.floor(baseDmg + Math.random() * 4 - 2));
      state.enemy.currentHp -= dmg;
      const enemyChar = document.getElementById('enemy-char');
      enemyChar.classList.add('hit');
      setTimeout(() => enemyChar.classList.remove('hit'), 300);
      setTimeout(() => window.Audio8 && window.Audio8.SFX.hit(), 80);
      showHit('#enemy-char', action.text);
      log(`プレイヤー ${action.name}！ ${dmg}ダメージ！`);
      checkVictory();
    } else {
      window.Audio8 && window.Audio8.SFX.miss();
      log(`プレイヤーの${action.name}は外れた…`);
    }

    updateUI();
    setTimeout(() => { state.player.busy = false; state.player.guarding = false; }, action.cd);
  }

  function enemyAction() {
    if (state.finished || state.enemy.busy) return;
    state.enemy.busy = true;
    const enemyChar = document.getElementById('enemy-char');
    enemyChar.classList.add('attacking');
    setTimeout(() => enemyChar.classList.remove('attacking'), 300);

    // 敵の攻撃選択
    const attacks = [
      { name: 'パンチ', dmg: state.enemy.atk, hit: 0.85, text: 'WHACK!' },
      { name: 'キック', dmg: state.enemy.atk * 1.5, hit: 0.65, text: 'BAM!!' }
    ];
    const a = attacks[Math.random() < 0.7 ? 0 : 1];

    if (Math.random() < a.hit) {
      let dmg = Math.floor(a.dmg + Math.random() * 3);
      if (state.player.guarding) dmg = Math.max(1, Math.floor(dmg * 0.2));
      state.player.hp -= dmg;
      const playerChar = document.getElementById('player-char');
      playerChar.classList.add('hit');
      setTimeout(() => playerChar.classList.remove('hit'), 300);
      setTimeout(() => window.Audio8 && window.Audio8.SFX.hit(), 80);
      showHit('#player-char', a.text);
      log(`${state.enemy.name}の${a.name}！ ${dmg}ダメージ！`);
      checkDefeat();
    } else {
      log(`${state.enemy.name}の${a.name}を回避！`);
    }

    updateUI();
    setTimeout(() => { state.enemy.busy = false; }, 600);
  }

  function checkVictory() {
    if (state.enemy.currentHp <= 0 && !state.finished) {
      state.finished = true;
      clearInterval(state.enemyTimer);
      document.getElementById('enemy-char').classList.add('defeated');
      log(`${state.enemy.name}を倒した！`);
      setTimeout(() => state.onWin(state.enemy), 1200);
    }
  }

  function checkDefeat() {
    if (state.player.hp <= 0 && !state.finished) {
      state.finished = true;
      clearInterval(state.enemyTimer);
      document.getElementById('player-char').classList.add('defeated');
      log(`プレイヤー敗北…`);
      setTimeout(() => state.onLose(), 1200);
    }
  }

  function stop() {
    if (state && state.enemyTimer) clearInterval(state.enemyTimer);
    state = null;
  }

  return { init, playerAction, stop };
})();

// キー入力
document.addEventListener('keydown', (e) => {
  if (!document.getElementById('screen-battle').classList.contains('active')) return;
  const map = { 'a': 'punch', 's': 'kick', 'd': 'special', 'f': 'guard' };
  const action = map[e.key.toLowerCase()];
  if (action) { e.preventDefault(); window.Battle.playerAction(action); }
});

// ボタンクリック
document.querySelectorAll('.action-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    window.Battle.playerAction(btn.dataset.action);
  });
});

// ゲーム状態管理 / 画面遷移
window.Game = (function() {
  let player = null;
  let currentStationIndex = 0;

  function newGame() {
    player = JSON.parse(JSON.stringify(window.PLAYER_INIT));
    currentStationIndex = 0;
    showScreen('screen-title');
  }

  function startGame() {
    player.hp = player.maxHp;
    showScreen('screen-map');
    window.MapUI.render();
  }

  function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
  }

  function boardStation() {
    const st = window.STATIONS[currentStationIndex];
    if (!st) return;
    if (player.defeated.includes(st.id)) {
      // 既にクリア済みは飛ばして次へ
      nextStation();
      return;
    }
    showScreen('screen-battle');
    window.Battle.init(st.enemy, onBattleWin, onBattleLose, st.id);
  }

  function onBattleWin(enemy) {
    window.Battle.stop();
    player.defeated.push(window.STATIONS[currentStationIndex].id);
    showBontanCutscene(enemy);
  }

  function showBontanCutscene(enemy) {
    showScreen('screen-bontan');
    const victim = document.getElementById('bontan-victim');
    victim.querySelector('.char-body').style.background = enemy.color;
    document.getElementById('bontan-message').textContent = '';
    const pants = document.getElementById('bontan-floating');
    pants.classList.remove('fly');
    pants.textContent = '👖';

    // 演出シーケンス
    setTimeout(() => {
      pants.classList.add('fly');
      document.getElementById('bontan-message').textContent =
        `${enemy.name}のボンタンをGET！`;
    }, 700);

    setTimeout(() => {
      // 敵がパンツ姿で逃げる
      victim.style.transition = 'all 1.5s';
      victim.style.right = '-200px';
      victim.querySelector('.char-body').style.height = '120px';
      victim.querySelector('.char-body').innerHTML = '<div style="height:50%; background:white"></div>';
      document.getElementById('bontan-message').textContent =
        `${enemy.name}はパンツ一丁で逃げ去った！💨`;
    }, 1800);

    setTimeout(() => {
      player.bontans.push({ from: enemy.name, color: enemy.bontanColor });
      // HP少し回復
      player.hp = Math.min(player.maxHp, player.hp + 15);
    }, 2400);

    // リセット用に状態を保存
    setTimeout(() => {
      victim.style.right = '80px';
      victim.style.transition = '';
      victim.querySelector('.char-body').style.height = '80px';
      victim.querySelector('.char-body').innerHTML = '';
    }, 4000);
  }

  function nextStation() {
    currentStationIndex++;
    if (currentStationIndex >= window.STATIONS.length) {
      showVictoryScreen();
      return;
    }
    showScreen('screen-map');
    window.MapUI.render();
  }

  function onBattleLose() {
    window.Battle.stop();
    showScreen('screen-defeat');
  }

  function retry() {
    player.hp = player.maxHp;
    boardStation();
  }

  function showVictoryScreen() {
    showScreen('screen-victory');
    const display = document.getElementById('victory-bontans');
    display.innerHTML = player.bontans.map(b =>
      `<span style="color:${b.color}" title="${b.from}">👖</span>`
    ).join('');
  }

  function getPlayer() { return player; }
  function getCurrentStationIndex() { return currentStationIndex; }

  return {
    newGame, startGame, boardStation, nextStation, retry,
    getPlayer, getCurrentStationIndex, showScreen
  };
})();

// イベントバインド
window.addEventListener('DOMContentLoaded', () => {
  window.Game.newGame();

  document.getElementById('btn-start').addEventListener('click', () => window.Game.startGame());
  document.getElementById('btn-board').addEventListener('click', () => window.Game.boardStation());
  document.getElementById('btn-bontan-next').addEventListener('click', () => window.Game.nextStation());
  document.getElementById('btn-retry').addEventListener('click', () => window.Game.retry());
  document.getElementById('btn-newgame').addEventListener('click', () => window.Game.newGame());
});

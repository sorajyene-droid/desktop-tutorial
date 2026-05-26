// 路線図UI
window.MapUI = (function() {

  function render() {
    const mapEl = document.getElementById('route-map');
    const player = window.Game.getPlayer();
    const currentIdx = window.Game.getCurrentStationIndex();

    let html = '';
    let prevLine = null;
    window.STATIONS.forEach((st, idx) => {
      if (prevLine && prevLine !== st.line) {
        html += `<div class="line-divider">━━ ${st.line} ━━</div>`;
      } else if (!prevLine) {
        html += `<div class="line-divider">━━ ${st.line} ━━</div>`;
      }
      prevLine = st.line;

      const defeated = player.defeated.includes(st.id);
      const current = idx === currentIdx;
      const locked = idx > currentIdx;
      const classes = ['station-row'];
      if (current) classes.push('current');
      else if (defeated) classes.push('defeated');
      if (locked) classes.push('locked');

      let marker = '🚉';
      if (defeated) marker = '✅';
      else if (current) marker = '👉';
      else if (st.isFinalBoss) marker = '👑';
      else if (st.isMidBoss) marker = '⚔️';

      html += `
        <div class="${classes.join(' ')}" data-idx="${idx}">
          <span class="station-marker">${marker}</span>
          <div class="station-info">
            <div><strong>${st.name}</strong> (${st.kana})</div>
            <div class="station-enemy">${st.enemy.emoji} ${st.enemy.title}「${st.enemy.name}」 HP:${st.enemy.hp}</div>
          </div>
        </div>
      `;
    });

    mapEl.innerHTML = html;

    // HPとボンタン数の更新
    document.getElementById('map-hp').textContent = player.hp;
    document.getElementById('map-bontans').textContent = player.bontans.length;

    // 現在駅にスクロール
    const currentRow = mapEl.querySelector('.station-row.current');
    if (currentRow) currentRow.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  return { render };
})();

import { GAME_CONFIG } from './config/gameConfig.js';
import { Game } from './core/Game.js';

// 初始化游戏
window.addEventListener('load', () => {
    const canvas = document.getElementById('gameCanvas');
    canvas.width = GAME_CONFIG.CANVAS_WIDTH;
    canvas.height = GAME_CONFIG.CANVAS_HEIGHT;

    const game = new Game(canvas);

    console.log('雷电战机已启动!');
    console.log('操作说明:');
    console.log('- 移动: WASD / 方向键');
    console.log('- 射击: 自动射击');
    console.log('- 暂停: P / ESC');
});
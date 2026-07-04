import { GAME_CONFIG } from '../config/gameConfig.js';

// 渲染器类
export class Renderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.width = canvas.width;
        this.height = canvas.height;
        this.stars = [];
        this.initStars();
    }

    // 初始化星空背景
    initStars() {
        for (let i = 0; i < GAME_CONFIG.BACKGROUND.STAR_COUNT; i++) {
            this.stars.push({
                x: Math.random() * this.width,
                y: Math.random() * this.height,
                size: Math.random() * 2 + 1,
                speed: Math.random() * 2 + 0.5,
            });
        }
    }

    // 清空画布
    clear() {
        this.ctx.clearRect(0, 0, this.width, this.height);
    }

    // 绘制背景
    drawBackground() {
        // 渐变背景
        const gradient = this.ctx.createLinearGradient(0, 0, 0, this.height);
        gradient.addColorStop(0, GAME_CONFIG.BACKGROUND.COLORS[0]);
        gradient.addColorStop(1, GAME_CONFIG.BACKGROUND.COLORS[1]);
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.width, this.height);

        // 绘制星星
        this.ctx.fillStyle = '#ffffff';
        this.stars.forEach(star => {
            this.ctx.globalAlpha = Math.random() * 0.5 + 0.5;
            this.ctx.beginPath();
            this.ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
            this.ctx.fill();

            // 移动星星
            star.y += star.speed;
            if (star.y > this.height) {
                star.y = 0;
                star.x = Math.random() * this.width;
            }
        });
        this.ctx.globalAlpha = 1;
    }

    // 绘制矩形
    drawRect(x, y, width, height, color, glow = false) {
        if (glow) {
            this.ctx.shadowBlur = 10;
            this.ctx.shadowColor = color;
        }
        this.ctx.fillStyle = color;
        this.ctx.fillRect(x, y, width, height);
        this.ctx.shadowBlur = 0;
    }

    // 绘制圆形
    drawCircle(x, y, radius, color, glow = false) {
        if (glow) {
            this.ctx.shadowBlur = 10;
            this.ctx.shadowColor = color;
        }
        this.ctx.fillStyle = color;
        this.ctx.beginPath();
        this.ctx.arc(x, y, radius, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
    }

    // 绘制文本
    drawText(text, x, y, fontSize = 20, color = '#ffffff', align = 'center') {
        this.ctx.font = `${fontSize}px Arial`;
        this.ctx.fillStyle = color;
        this.ctx.textAlign = align;
        this.ctx.fillText(text, x, y);
    }

    // 绘制玩家飞机
    drawPlayer(player) {
        const { x, y, width, height, color, invincible } = player;

        // 无敌时闪烁
        if (invincible && Math.floor(Date.now() / 100) % 2 === 0) {
            return;
        }

        this.ctx.save();
        this.ctx.translate(x + width / 2, y + height / 2);

        // 飞机主体
        this.ctx.fillStyle = color;
        this.ctx.beginPath();
        this.ctx.moveTo(0, -height / 2);
        this.ctx.lineTo(width / 2, height / 2);
        this.ctx.lineTo(0, height / 3);
        this.ctx.lineTo(-width / 2, height / 2);
        this.ctx.closePath();
        this.ctx.fill();

        // 飞机边框
        this.ctx.strokeStyle = '#ffd700';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();

        // 引擎火焰
        this.ctx.fillStyle = '#ff6600';
        this.ctx.beginPath();
        this.ctx.moveTo(-width / 4, height / 3);
        this.ctx.lineTo(0, height / 2 + Math.random() * 10);
        this.ctx.lineTo(width / 4, height / 3);
        this.ctx.closePath();
        this.ctx.fill();

        this.ctx.restore();
    }

    // 绘制敌机
    drawEnemy(enemy) {
        const { x, y, width, height, color, type } = enemy;

        this.ctx.save();
        this.ctx.translate(x + width / 2, y + height / 2);

        // 敌机主体
        this.ctx.fillStyle = color;
        this.ctx.beginPath();
        this.ctx.moveTo(0, height / 2);
        this.ctx.lineTo(width / 2, -height / 2);
        this.ctx.lineTo(0, -height / 3);
        this.ctx.lineTo(-width / 2, -height / 2);
        this.ctx.closePath();
        this.ctx.fill();

        // 敌机边框
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();

        // Boss特殊效果
        if (type === 'BOSS') {
            this.ctx.strokeStyle = '#ff0000';
            this.ctx.lineWidth = 3;
            this.ctx.stroke();
        }

        this.ctx.restore();
    }

    // 绘制子弹
    drawBullet(bullet) {
        const { x, y, width, height, color, isPlayer } = bullet;

        this.ctx.save();
        this.ctx.shadowBlur = 10;
        this.ctx.shadowColor = color;
        this.ctx.fillStyle = color;

        if (isPlayer) {
            // 玩家子弹 - 长条形
            this.ctx.fillRect(x, y, width, height);
        } else {
            // 敌机子弹 - 圆形
            this.ctx.beginPath();
            this.ctx.arc(x + width / 2, y + height / 2, width / 2, 0, Math.PI * 2);
            this.ctx.fill();
        }

        this.ctx.restore();
    }

    // 绘制道具
    drawPowerUp(powerUp) {
        const { x, y, width, height, color, symbol } = powerUp;

        this.ctx.save();
        this.ctx.shadowBlur = 15;
        this.ctx.shadowColor = color;

        // 道具背景
        this.ctx.fillStyle = color;
        this.ctx.beginPath();
        this.ctx.arc(x + width / 2, y + height / 2, width / 2, 0, Math.PI * 2);
        this.ctx.fill();

        // 道具符号
        this.ctx.font = '16px Arial';
        this.ctx.fillStyle = '#ffffff';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(symbol, x + width / 2, y + height / 2);

        this.ctx.restore();
    }

    // 绘制粒子
    drawParticle(particle) {
        const { x, y, size, color, alpha } = particle;

        this.ctx.save();
        this.ctx.globalAlpha = alpha;
        this.ctx.fillStyle = color;
        this.ctx.beginPath();
        this.ctx.arc(x, y, size, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.restore();
    }

    // 绘制HUD
    drawHUD(game) {
        const { player, score, level, energy } = game;

        // 分数
        this.drawText(`分数: ${score}`, 10, 30, 20, '#ffffff', 'left');

        // 关卡
        this.drawText(`关卡: ${level}`, this.width / 2, 30, 20, '#ffffff', 'center');

        // 生命
        let livesText = '生命: ';
        for (let i = 0; i < player.lives; i++) {
            livesText += '❤️';
        }
        this.drawText(livesText, this.width - 10, 30, 20, '#ffffff', 'right');

        // 武器等级
        this.drawText(`武器: Lv${player.weaponLevel}`, 10, this.height - 30, 18, '#ffffff', 'left');

        // 能量条
        const energyBarWidth = 200;
        const energyBarHeight = 20;
        const energyBarX = this.width / 2 - energyBarWidth / 2;
        const energyBarY = this.height - 40;

        // 能量条背景
        this.ctx.fillStyle = '#333333';
        this.ctx.fillRect(energyBarX, energyBarY, energyBarWidth, energyBarHeight);

        // 能量条前景
        const energyPercent = energy / GAME_CONFIG.PLAYER.MAX_ENERGY;
        this.ctx.fillStyle = energyPercent >= 1 ? '#00ff00' : '#ffff00';
        this.ctx.fillRect(energyBarX, energyBarY, energyBarWidth * energyPercent, energyBarHeight);

        // 能量条边框
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2;
        this.ctx.strokeRect(energyBarX, energyBarY, energyBarWidth, energyBarHeight);

        // 能量文字
        this.drawText(`能量: ${energy}/${GAME_CONFIG.PLAYER.MAX_ENERGY}`, this.width / 2, energyBarY - 5, 16, '#ffffff', 'center');

        // 暂停提示
        this.drawText('暂停: P', this.width - 10, this.height - 30, 18, '#ffffff', 'right');
    }

    // 绘制菜单
    drawMenu(title, options, selectedIndex) {
        // 半透明背景
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        this.ctx.fillRect(0, 0, this.width, this.height);

        // 标题
        this.drawText(title, this.width / 2, this.height / 4, 40, '#00d4ff', 'center');

        // 选项
        options.forEach((option, index) => {
            const y = this.height / 2 + index * 50;
            const color = index === selectedIndex ? '#ffff00' : '#ffffff';
            const prefix = index === selectedIndex ? '► ' : '  ';
            this.drawText(prefix + option, this.width / 2, y, 24, color, 'center');
        });
    }

    // 绘制游戏结束
    drawGameOver(score, highScore) {
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
        this.ctx.fillRect(0, 0, this.width, this.height);

        this.drawText('游戏结束', this.width / 2, this.height / 3, 40, '#ff4444', 'center');
        this.drawText(`分数: ${score}`, this.width / 2, this.height / 2, 30, '#ffffff', 'center');
        this.drawText(`最高分: ${highScore}`, this.width / 2, this.height / 2 + 50, 24, '#ffff00', 'center');
        this.drawText('按 R 重新开始', this.width / 2, this.height * 2 / 3, 24, '#ffffff', 'center');
    }

    // 绘制关卡完成
    drawLevelComplete(level, score) {
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        this.ctx.fillRect(0, 0, this.width, this.height);

        this.drawText(`关卡 ${level} 完成!`, this.width / 2, this.height / 3, 40, '#44ff44', 'center');
        this.drawText(`分数: ${score}`, this.width / 2, this.height / 2, 30, '#ffffff', 'center');
        this.drawText('按空格键继续', this.width / 2, this.height * 2 / 3, 24, '#ffffff', 'center');
    }
}
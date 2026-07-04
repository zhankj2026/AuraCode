import { GAME_CONFIG, GAME_STATE, INPUT_KEYS } from '../config/gameConfig.js';
import { Renderer } from './Renderer.js';
import { InputHandler } from './InputHandler.js';
import { ObjectPool } from '../utils/ObjectPool.js';

// 游戏主类
export class Game {
    constructor(canvas) {
        this.canvas = canvas;
        this.renderer = new Renderer(canvas);
        this.input = new InputHandler();

        // 游戏状态
        this.state = GAME_STATE.MENU;
        this.score = 0;
        this.level = 1;
        this.highScore = parseInt(localStorage.getItem('thunder_fighter_highscore')) || 0;

        // 游戏对象
        this.player = null;
        this.bullets = [];
        this.enemies = [];
        this.powerUps = [];
        this.particles = [];

        // 对象池
        this.bulletPool = new ObjectPool(
            () => ({ x: 0, y: 0, width: 0, height: 0, speed: 0, damage: 0, color: '', isPlayer: false, active: false }),
            (bullet) => { bullet.active = false; },
            50
        );

        this.particlePool = new ObjectPool(
            () => ({ x: 0, y: 0, vx: 0, vy: 0, size: 0, color: '', alpha: 1, lifetime: 0, active: false }),
            (particle) => { particle.active = false; },
            100
        );

        // 计时器
        this.lastTime = 0;
        this.deltaTime = 0;
        this.enemySpawnTimer = 0;
        this.playerShootTimer = 0;

        // 菜单选项
        this.menuOptions = ['开始游戏', '排行榜', '退出'];
        this.menuIndex = 0;

        // 绑定事件
        this.bindEvents();

        // 开始游戏循环
        this.gameLoop = this.gameLoop.bind(this);
        requestAnimationFrame(this.gameLoop);
    }

    bindEvents() {
        window.addEventListener('keydown', (e) => {
            if (this.state === GAME_STATE.MENU) {
                if (e.code === 'ArrowUp' || e.code === 'KeyW') {
                    this.menuIndex = (this.menuIndex - 1 + this.menuOptions.length) % this.menuOptions.length;
                } else if (e.code === 'ArrowDown' || e.code === 'KeyS') {
                    this.menuIndex = (this.menuIndex + 1) % this.menuOptions.length;
                } else if (e.code === 'Enter' || e.code === 'Space') {
                    this.handleMenuSelection();
                }
            } else if (this.state === GAME_STATE.PLAYING) {
                if (this.input.isKeyPressed(INPUT_KEYS.PAUSE)) {
                    this.state = GAME_STATE.PAUSED;
                }
            } else if (this.state === GAME_STATE.PAUSED) {
                if (this.input.isKeyPressed(INPUT_KEYS.PAUSE)) {
                    this.state = GAME_STATE.PLAYING;
                }
            } else if (this.state === GAME_STATE.GAME_OVER) {
                if (e.code === 'KeyR') {
                    this.startGame();
                }
            } else if (this.state === GAME_STATE.LEVEL_COMPLETE) {
                if (e.code === 'Space') {
                    this.nextLevel();
                }
            }
        });
    }

    handleMenuSelection() {
        switch (this.menuIndex) {
            case 0: // 开始游戏
                this.startGame();
                break;
            case 1: // 排行榜
                // TODO: 显示排行榜
                break;
            case 2: // 退出
                // TODO: 退出游戏
                break;
        }
    }

    startGame() {
        this.state = GAME_STATE.PLAYING;
        this.score = 0;
        this.level = 1;
        this.enemies = [];
        this.powerUps = [];
        this.bullets = [];
        this.particles = [];

        // 创建玩家
        this.player = {
            x: this.canvas.width / 2 - GAME_CONFIG.PLAYER.WIDTH / 2,
            y: this.canvas.height - 100,
            width: GAME_CONFIG.PLAYER.WIDTH,
            height: GAME_CONFIG.PLAYER.HEIGHT,
            speed: GAME_CONFIG.PLAYER.SPEED,
            lives: GAME_CONFIG.PLAYER.INITIAL_LIVES,
            weaponLevel: GAME_CONFIG.PLAYER.INITIAL_WEAPON_LEVEL,
            energy: GAME_CONFIG.PLAYER.INITIAL_ENERGY,
            invincible: false,
            invincibleTimer: 0,
            exp: 0,
            expToNextLevel: GAME_CONFIG.UPGRADE.EXP_PER_LEVEL,
        };

        this.bulletPool.releaseAll();
        this.particlePool.releaseAll();
    }

    nextLevel() {
        this.level++;
        this.state = GAME_STATE.PLAYING;
        this.enemies = [];
        this.powerUps = [];
        this.bulletPool.releaseAll();
    }

    gameOver() {
        this.state = GAME_STATE.GAME_OVER;
        if (this.score > this.highScore) {
            this.highScore = this.score;
            localStorage.setItem('thunder_fighter_highscore', this.highScore);
        }
    }

    update(deltaTime) {
        if (this.state !== GAME_STATE.PLAYING) return;

        // 更新玩家
        this.updatePlayer(deltaTime);

        // 更新子弹
        this.updateBullets(deltaTime);

        // 更新敌机
        this.updateEnemies(deltaTime);

        // 更新道具
        this.updatePowerUps(deltaTime);

        // 更新粒子
        this.updateParticles(deltaTime);

        // 生成敌机
        this.spawnEnemies(deltaTime);

        // 碰撞检测
        this.checkCollisions();

        // 检查关卡完成
        this.checkLevelComplete();
    }

    updatePlayer(deltaTime) {
        if (!this.player) return;

        // 键盘移动
        const direction = this.input.getDirection();
        if (direction.x !== 0 || direction.y !== 0) {
            this.player.x += direction.x * this.player.speed;
            this.player.y += direction.y * this.player.speed;
        }

        // 边界限制
        this.player.x = Math.max(0, Math.min(this.canvas.width - this.player.width, this.player.x));
        this.player.y = Math.max(0, Math.min(this.canvas.height - this.player.height, this.player.y));

        // 自动射击
        this.playerShootTimer += deltaTime;
        if (this.playerShootTimer >= GAME_CONFIG.PLAYER.SHOOT_INTERVAL) {
            this.playerShoot();
            this.playerShootTimer = 0;
        }

        // 更新无敌状态
        if (this.player.invincible) {
            this.player.invincibleTimer -= deltaTime;
            if (this.player.invincibleTimer <= 0) {
                this.player.invincible = false;
            }
        }
    }

    playerShoot() {
        if (!this.player) return;

        const bullet = this.bulletPool.get();
        bullet.x = this.player.x + this.player.width / 2 - GAME_CONFIG.BULLET.WIDTH / 2;
        bullet.y = this.player.y;
        bullet.width = GAME_CONFIG.BULLET.WIDTH;
        bullet.height = GAME_CONFIG.BULLET.HEIGHT;
        bullet.speed = -GAME_CONFIG.BULLET.PLAYER_SPEED;
        bullet.damage = GAME_CONFIG.BULLET.PLAYER_DAMAGE + Math.floor(this.player.weaponLevel / 3);
        bullet.color = '#00ffff';
        bullet.isPlayer = true;
        bullet.active = true;

        this.bullets.push(bullet);

        // 根据武器等级发射额外子弹
        if (this.player.weaponLevel >= 2) {
            const bullet2 = this.bulletPool.get();
            bullet2.x = this.player.x;
            bullet2.y = this.player.y + 10;
            bullet2.width = GAME_CONFIG.BULLET.WIDTH;
            bullet2.height = GAME_CONFIG.BULLET.HEIGHT;
            bullet2.speed = -GAME_CONFIG.BULLET.PLAYER_SPEED;
            bullet2.damage = bullet.damage;
            bullet2.color = '#00ffff';
            bullet2.isPlayer = true;
            bullet2.active = true;
            this.bullets.push(bullet2);

            const bullet3 = this.bulletPool.get();
            bullet3.x = this.player.x + this.player.width - GAME_CONFIG.BULLET.WIDTH;
            bullet3.y = this.player.y + 10;
            bullet3.width = GAME_CONFIG.BULLET.WIDTH;
            bullet3.height = GAME_CONFIG.BULLET.HEIGHT;
            bullet3.speed = -GAME_CONFIG.BULLET.PLAYER_SPEED;
            bullet3.damage = bullet.damage;
            bullet3.color = '#00ffff';
            bullet3.isPlayer = true;
            bullet3.active = true;
            this.bullets.push(bullet3);
        }
    }

    updateBullets(deltaTime) {
        this.bullets = this.bullets.filter(bullet => {
            bullet.y += bullet.speed;

            // 移除超出屏幕的子弹
            if (bullet.y < -bullet.height || bullet.y > this.canvas.height) {
                this.bulletPool.release(bullet);
                return false;
            }
            return true;
        });
    }

    updateEnemies(deltaTime) {
        this.enemies = this.enemies.filter(enemy => {
            // 简单的AI：向下移动
            enemy.y += enemy.speed;

            // 移除超出屏幕的敌机
            if (enemy.y > this.canvas.height) {
                return false;
            }
            return true;
        });
    }

    updatePowerUps(deltaTime) {
        this.powerUps = this.powerUps.filter(powerUp => {
            powerUp.y += GAME_CONFIG.POWERUP.SPEED;

            // 移除超出屏幕的道具
            if (powerUp.y > this.canvas.height) {
                return false;
            }
            return true;
        });
    }

    updateParticles(deltaTime) {
        this.particles = this.particles.filter(particle => {
            particle.x += particle.vx;
            particle.y += particle.vy;
            particle.alpha -= deltaTime / particle.lifetime;

            if (particle.alpha <= 0) {
                this.particlePool.release(particle);
                return false;
            }
            return true;
        });
    }

    spawnEnemies(deltaTime) {
        this.enemySpawnTimer += deltaTime;
        const spawnInterval = GAME_CONFIG.ENEMY.SPAWN_INTERVAL / (1 + (this.level - 1) * 0.1);

        if (this.enemySpawnTimer >= spawnInterval) {
            this.enemySpawnTimer = 0;

            // 随机选择敌机类型
            const types = ['NORMAL', 'FAST', 'HEAVY'];
            const type = types[Math.floor(Math.random() * types.length)];
            const config = GAME_CONFIG.ENEMY.TYPES[type];

            const enemy = {
                x: Math.random() * (this.canvas.width - config.width),
                y: -config.height,
                width: config.width,
                height: config.height,
                speed: config.speed,
                health: config.health,
                maxHealth: config.health,
                damage: 1,
                score: config.score,
                color: config.color,
                type: type,
            };

            this.enemies.push(enemy);
        }
    }

    checkCollisions() {
        // 玩家子弹与敌机碰撞
        this.bullets.forEach(bullet => {
            if (!bullet.isPlayer || !bullet.active) return;

            this.enemies.forEach(enemy => {
                if (this.checkCollision(bullet, enemy)) {
                    enemy.health -= bullet.damage;
                    bullet.active = false;
                    this.bulletPool.release(bullet);

                    // 创建击中效果
                    this.createParticles(bullet.x, bullet.y, '#ffff00', 5);

                    if (enemy.health <= 0) {
                        this.destroyEnemy(enemy);
                    }
                }
            });
        });

        // 敌机子弹与玩家碰撞
        this.bullets.forEach(bullet => {
            if (bullet.isPlayer || !bullet.active) return;

            if (this.player && !this.player.invincible && this.checkCollision(bullet, this.player)) {
                this.player.lives--;
                bullet.active = false;
                this.bulletPool.release(bullet);
                this.player.invincible = true;
                this.player.invincibleTimer = GAME_CONFIG.PLAYER.INVINCIBLE_TIME;

                if (this.player.lives <= 0) {
                    this.gameOver();
                }
            }
        });

        // 玩家与敌机碰撞
        if (this.player && !this.player.invincible) {
            this.enemies.forEach(enemy => {
                if (this.checkCollision(this.player, enemy)) {
                    this.player.lives--;
                    this.player.invincible = true;
                    this.player.invincibleTimer = GAME_CONFIG.PLAYER.INVINCIBLE_TIME;
                    this.destroyEnemy(enemy);

                    if (this.player.lives <= 0) {
                        this.gameOver();
                    }
                }
            });
        }

        // 玩家与道具碰撞
        if (this.player) {
            this.powerUps = this.powerUps.filter(powerUp => {
                if (this.checkCollision(this.player, powerUp)) {
                    this.collectPowerUp(powerUp);
                    return false;
                }
                return true;
            });
        }
    }

    checkCollision(obj1, obj2) {
        return obj1.x < obj2.x + obj2.width &&
               obj1.x + obj1.width > obj2.x &&
               obj1.y < obj2.y + obj2.height &&
               obj1.y + obj1.height > obj2.y;
    }

    destroyEnemy(enemy) {
        // 创建爆炸效果
        this.createParticles(enemy.x + enemy.width / 2, enemy.y + enemy.height / 2, enemy.color, 20);

        // 增加分数
        this.score += enemy.score;

        // 增加经验
        this.player.exp += GAME_CONFIG.UPGRADE.EXP_PER_KILL;

        // 检查升级
        if (this.player.exp >= this.player.expToNextLevel) {
            this.player.exp = 0;
            this.player.expToNextLevel = Math.floor(this.player.expToNextLevel * GAME_CONFIG.UPGRADE.LEVEL_MULTIPLIER);
            if (this.player.weaponLevel < GAME_CONFIG.PLAYER.MAX_WEAPON_LEVEL) {
                this.player.weaponLevel++;
            }
        }

        // 增加能量
        this.player.energy = Math.min(GAME_CONFIG.PLAYER.MAX_ENERGY, this.player.energy + 5);

        // 掉落道具
        if (Math.random() < GAME_CONFIG.POWERUP.DROP_RATE.NORMAL) {
            this.spawnPowerUp(enemy.x + enemy.width / 2, enemy.y + enemy.height / 2);
        }

        // 移除敌机
        const index = this.enemies.indexOf(enemy);
        if (index > -1) {
            this.enemies.splice(index, 1);
        }
    }

    spawnPowerUp(x, y) {
        const types = ['HEALTH', 'WEAPON', 'SHIELD', 'ENERGY', 'SCORE'];
        const type = types[Math.floor(Math.random() * types.length)];
        const config = GAME_CONFIG.POWERUP.TYPES[type];

        const powerUp = {
            x: x - GAME_CONFIG.POWERUP.WIDTH / 2,
            y: y,
            width: GAME_CONFIG.POWERUP.WIDTH,
            height: GAME_CONFIG.POWERUP.HEIGHT,
            type: type,
            color: config.color,
            symbol: config.symbol,
        };

        this.powerUps.push(powerUp);
    }

    collectPowerUp(powerUp) {
        switch (powerUp.type) {
            case 'HEALTH':
                if (this.player.lives < 5) {
                    this.player.lives++;
                }
                break;
            case 'WEAPON':
                if (this.player.weaponLevel < GAME_CONFIG.PLAYER.MAX_WEAPON_LEVEL) {
                    this.player.weaponLevel++;
                }
                break;
            case 'SHIELD':
                this.player.invincible = true;
                this.player.invincibleTimer = GAME_CONFIG.POWERUP.DURATION;
                break;
            case 'ENERGY':
                this.player.energy = Math.min(GAME_CONFIG.PLAYER.MAX_ENERGY, this.player.energy + 20);
                break;
            case 'SCORE':
                this.score += 100;
                break;
        }
    }

    createParticles(x, y, color, count) {
        for (let i = 0; i < count; i++) {
            const particle = this.particlePool.get();
            particle.x = x;
            particle.y = y;
            particle.vx = (Math.random() - 0.5) * GAME_CONFIG.PARTICLE.SPEED * 2;
            particle.vy = (Math.random() - 0.5) * GAME_CONFIG.PARTICLE.SPEED * 2;
            particle.size = Math.random() * 3 + 1;
            particle.color = color;
            particle.alpha = 1;
            particle.lifetime = GAME_CONFIG.PARTICLE.LIFETIME;
            particle.active = true;
            this.particles.push(particle);
        }
    }

    checkLevelComplete() {
        // 简单的关卡完成条件：达到一定分数
        const targetScore = this.level * 500;
        if (this.score >= targetScore) {
            this.state = GAME_STATE.LEVEL_COMPLETE;
        }
    }

    render() {
        // 清空画布
        this.renderer.clear();

        // 绘制背景
        this.renderer.drawBackground();

        if (this.state === GAME_STATE.MENU) {
            this.renderer.drawMenu('雷电战机', this.menuOptions, this.menuIndex);
        } else if (this.state === GAME_STATE.PLAYING || this.state === GAME_STATE.PAUSED) {
            // 绘制道具
            this.powerUps.forEach(powerUp => {
                this.renderer.drawPowerUp(powerUp);
            });

            // 绘制粒子
            this.particles.forEach(particle => {
                this.renderer.drawParticle(particle);
            });

            // 绘制子弹
            this.bullets.forEach(bullet => {
                if (bullet.active) {
                    this.renderer.drawBullet(bullet);
                }
            });

            // 绘制敌机
            this.enemies.forEach(enemy => {
                this.renderer.drawEnemy(enemy);
            });

            // 绘制玩家
            if (this.player) {
                this.renderer.drawPlayer(this.player);
            }

            // 绘制HUD
            this.renderer.drawHUD({
                player: this.player,
                score: this.score,
                level: this.level,
                energy: this.player ? this.player.energy : 0,
            });

            // 暂停提示
            if (this.state === GAME_STATE.PAUSED) {
                this.renderer.drawText('暂停', this.canvas.width / 2, this.canvas.height / 2, 40, '#ffffff', 'center');
            }
        } else if (this.state === GAME_STATE.GAME_OVER) {
            this.renderer.drawGameOver(this.score, this.highScore);
        } else if (this.state === GAME_STATE.LEVEL_COMPLETE) {
            this.renderer.drawLevelComplete(this.level, this.score);
        }
    }

    gameLoop(timestamp) {
        // 计算delta time
        this.deltaTime = timestamp - this.lastTime;
        this.lastTime = timestamp;

        // 限制最大delta time，防止切换标签页后跳跃
        if (this.deltaTime > 100) {
            this.deltaTime = 100;
        }

        // 更新游戏
        this.update(this.deltaTime);

        // 渲染游戏
        this.render();

        // 下一帧
        requestAnimationFrame(this.gameLoop);
    }
}
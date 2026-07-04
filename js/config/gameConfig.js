// 游戏配置文件
export const GAME_CONFIG = {
    // 画布尺寸
    CANVAS_WIDTH: 600,
    CANVAS_HEIGHT: 800,

    // 游戏帧率
    FPS: 60,

    // 玩家配置
    PLAYER: {
        WIDTH: 40,
        HEIGHT: 50,
        SPEED: 5,
        INITIAL_LIVES: 3,
        INITIAL_WEAPON_LEVEL: 1,
        MAX_WEAPON_LEVEL: 10,
        INITIAL_ENERGY: 0,
        MAX_ENERGY: 100,
        SHOOT_INTERVAL: 150, // 毫秒
        INVINCIBLE_TIME: 2000, // 受伤后无敌时间（毫秒）
    },

    // 子弹配置
    BULLET: {
        PLAYER_SPEED: 10,
        ENEMY_SPEED: 5,
        PLAYER_DAMAGE: 1,
        ENEMY_DAMAGE: 1,
        WIDTH: 6,
        HEIGHT: 15,
    },

    // 敌机配置
    ENEMY: {
        SPAWN_INTERVAL: 1000, // 毫秒
        TYPES: {
            NORMAL: {
                width: 30,
                height: 30,
                health: 1,
                speed: 2,
                score: 10,
                color: '#ff4444',
                shootInterval: 0,
            },
            FAST: {
                width: 25,
                height: 25,
                health: 1,
                speed: 4,
                score: 15,
                color: '#ff8800',
                shootInterval: 0,
            },
            HEAVY: {
                width: 50,
                height: 50,
                health: 5,
                speed: 1,
                score: 30,
                color: '#aa44ff',
                shootInterval: 2000,
            },
            ELITE: {
                width: 40,
                height: 40,
                health: 10,
                speed: 2.5,
                score: 50,
                color: '#ff00ff',
                shootInterval: 1500,
            },
            BOSS: {
                width: 100,
                height: 100,
                health: 100,
                speed: 1,
                score: 500,
                color: '#ff0000',
                shootInterval: 1000,
            },
        },
    },

    // 道具配置
    POWERUP: {
        WIDTH: 25,
        HEIGHT: 25,
        SPEED: 2,
        DURATION: 10000, // 道具效果持续时间（毫秒）
        DROP_RATE: {
            NORMAL: 0.05,
            FAST: 0.05,
            HEAVY: 0.1,
            ELITE: 0.3,
            BOSS: 1.0,
        },
        TYPES: {
            HEALTH: { color: '#ff4444', symbol: '❤️' },
            WEAPON: { color: '#44ff44', symbol: '⚡' },
            SHIELD: { color: '#4444ff', symbol: '🛡️' },
            ENERGY: { color: '#ffff44', symbol: '💣' },
            SCORE: { color: '#ff44ff', symbol: '⭐' },
        },
    },

    // 升级配置
    UPGRADE: {
        EXP_PER_KILL: 10,
        EXP_PER_LEVEL: 100,
        LEVEL_MULTIPLIER: 1.2, // 每级所需经验倍数
    },

    // 必杀技配置
    ULTIMATE: {
        DAMAGE: 50,
        ENERGY_COST: 100,
        INVINCIBLE_TIME: 3000,
    },

    // 粒子配置
    PARTICLE: {
        COUNT: 20,
        LIFETIME: 500,
        SPEED: 3,
    },

    // 背景配置
    BACKGROUND: {
        STAR_COUNT: 100,
        STAR_SPEED: 1,
        COLORS: ['#0a0a2e', '#1a1a4e'],
    },

    // 关卡配置
    LEVEL: {
        COUNT: 5,
        DIFFICULTY_MULTIPLIER: 1.1, // 每关难度倍数
    },

    // 成就配置
    ACHIEVEMENT: {
        STORAGE_KEY: 'thunder_fighter_achievements',
    },

    // 排行榜配置
    LEADERBOARD: {
        STORAGE_KEY: 'thunder_fighter_leaderboard',
        MAX_ENTRIES: 10,
    },
};

// 游戏状态枚举
export const GAME_STATE = {
    MENU: 'menu',
    PLAYING: 'playing',
    PAUSED: 'paused',
    GAME_OVER: 'game_over',
    LEVEL_COMPLETE: 'level_complete',
    VICTORY: 'victory',
};

// 输入键位配置
export const INPUT_KEYS = {
    UP: ['ArrowUp', 'KeyW'],
    DOWN: ['ArrowDown', 'KeyS'],
    LEFT: ['ArrowLeft', 'KeyA'],
    RIGHT: ['ArrowRight', 'KeyD'],
    SHOOT: ['Space'],
    ULTIMATE: ['KeyZ'],
    PAUSE: ['KeyP', 'Escape'],
};
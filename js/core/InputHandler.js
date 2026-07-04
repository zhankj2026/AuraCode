import { INPUT_KEYS } from '../config/gameConfig.js';

// 输入处理器类
export class InputHandler {
    constructor() {
        this.keys = {};
        this.mouse = { x: 0, y: 0, down: false };
        this.init();
    }

    init() {
        // 键盘事件
        window.addEventListener('keydown', (e) => {
            this.keys[e.code] = true;
        });

        window.addEventListener('keyup', (e) => {
            this.keys[e.code] = false;
        });

        // 鼠标事件
        window.addEventListener('mousemove', (e) => {
            const canvas = document.getElementById('gameCanvas');
            if (canvas) {
                const rect = canvas.getBoundingClientRect();
                this.mouse.x = e.clientX - rect.left;
                this.mouse.y = e.clientY - rect.top;
            }
        });

        window.addEventListener('mousedown', () => {
            this.mouse.down = true;
        });

        window.addEventListener('mouseup', () => {
            this.mouse.down = false;
        });

        // 触摸事件（移动端支持）
        window.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const canvas = document.getElementById('gameCanvas');
            if (canvas && e.touches.length > 0) {
                const rect = canvas.getBoundingClientRect();
                this.mouse.x = e.touches[0].clientX - rect.left;
                this.mouse.y = e.touches[0].clientY - rect.top;
            }
        }, { passive: false });

        window.addEventListener('touchstart', () => {
            this.mouse.down = true;
        });

        window.addEventListener('touchend', () => {
            this.mouse.down = false;
        });
    }

    // 检查按键是否按下
    isKeyPressed(keyCodes) {
        if (Array.isArray(keyCodes)) {
            return keyCodes.some(code => this.keys[code]);
        }
        return this.keys[keyCodes];
    }

    // 检查方向键
    getDirection() {
        const direction = { x: 0, y: 0 };
        if (this.isKeyPressed(INPUT_KEYS.UP)) direction.y -= 1;
        if (this.isKeyPressed(INPUT_KEYS.DOWN)) direction.y += 1;
        if (this.isKeyPressed(INPUT_KEYS.LEFT)) direction.x -= 1;
        if (this.isKeyPressed(INPUT_KEYS.RIGHT)) direction.x += 1;
        return direction;
    }

    // 获取鼠标位置
    getMousePosition() {
        return { x: this.mouse.x, y: this.mouse.y };
    }

    // 检查鼠标是否按下
    isMouseDown() {
        return this.mouse.down;
    }

    // 重置输入状态
    reset() {
        this.keys = {};
        this.mouse.down = false;
    }
}
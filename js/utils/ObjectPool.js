// 对象池类 - 用于管理频繁创建销毁的对象
export class ObjectPool {
    constructor(createFn, resetFn, initialSize = 10) {
        this.createFn = createFn;
        this.resetFn = resetFn;
        this.pool = [];
        this.activeObjects = [];

        // 预创建对象
        for (let i = 0; i < initialSize; i++) {
            this.pool.push(this.createFn());
        }
    }

    // 获取对象
    get() {
        let obj;
        if (this.pool.length > 0) {
            obj = this.pool.pop();
        } else {
            obj = this.createFn();
        }
        this.activeObjects.push(obj);
        return obj;
    }

    // 释放对象
    release(obj) {
        const index = this.activeObjects.indexOf(obj);
        if (index > -1) {
            this.activeObjects.splice(index, 1);
            this.resetFn(obj);
            this.pool.push(obj);
        }
    }

    // 释放所有对象
    releaseAll() {
        while (this.activeObjects.length > 0) {
            const obj = this.activeObjects.pop();
            this.resetFn(obj);
            this.pool.push(obj);
        }
    }

    // 获取活跃对象数量
    getActiveCount() {
        return this.activeObjects.length;
    }

    // 获取池中对象数量
    getPoolCount() {
        return this.pool.length;
    }

    // 遍历活跃对象
    forEachActive(callback) {
        this.activeObjects.forEach(callback);
    }
}
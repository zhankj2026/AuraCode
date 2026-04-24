// 游戏配置
const DIFFICULTY = {
    easy: { rows: 9, cols: 9, mines: 10 },
    medium: { rows: 16, cols: 16, mines: 40 },
    hard: { rows: 16, cols: 30, mines: 99 }
};

// 游戏状态
let currentDifficulty = 'easy';
let board = [];
let minesLocations = [];
let minesCount = 10;
let timer = 0;
let timerInterval = null;
let gameOver = false;
let firstClick = true;

// DOM 元素
const boardElement = document.getElementById('board');
const minesCountElement = document.getElementById('mines-count');
const timerElement = document.getElementById('timer');

// 初始化游戏
function initGame() {
    // 重置状态
    board = [];
    minesLocations = [];
    gameOver = false;
    firstClick = true;
    timer = 0;

    const config = DIFFICULTY[currentDifficulty];
    minesCount = config.mines;

    // 更新显示
    minesCountElement.textContent = minesCount;
    timerElement.textContent = timer;

    // 清除定时器
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }

    // 设置棋盘大小
    boardElement.style.gridTemplateColumns = `repeat(${config.cols}, 30px)`;

    // 创建棋盘
    createBoard(config.rows, config.cols);

    // 渲染棋盘
    renderBoard();
}

// 创建棋盘数据
function createBoard(rows, cols) {
    board = [];
    for (let i = 0; i < rows * cols; i++) {
        board.push({
            mine: false,
            revealed: false,
            flagged: false,
            neighborMines: 0
        });
    }
}

// 放置地雷（确保第一次点击不是地雷）
function placeMines(safeIndex) {
    const config = DIFFICULTY[currentDifficulty];
    const totalCells = config.rows * config.cols;
    let minesPlaced = 0;

    while (minesPlaced < config.mines) {
        const randomIndex = Math.floor(Math.random() * totalCells);

        // 避免在第一次点击的位置放置地雷
        if (randomIndex === safeIndex) continue;

        if (!board[randomIndex].mine) {
            board[randomIndex].mine = true;
            minesLocations.push(randomIndex);
            minesPlaced++;
        }
    }
}

// 计算每个格子周围的地雷数量
function calculateNumbers() {
    const config = DIFFICULTY[currentDifficulty];

    for (let i = 0; i < board.length; i++) {
        if (board[i].mine) continue;

        const neighbors = getNeighbors(i, config.rows, config.cols);
        let count = 0;

        neighbors.forEach(index => {
            if (board[index].mine) count++;
        });

        board[i].neighborMines = count;
    }
}

// 获取相邻格子索引
function getNeighbors(index, rows, cols) {
    const neighbors = [];
    const row = Math.floor(index / cols);
    const col = index % cols;

    for (let i = -1; i <= 1; i++) {
        for (let j = -1; j <= 1; j++) {
            if (i === 0 && j === 0) continue;

            const newRow = row + i;
            const newCol = col + j;

            if (newRow >= 0 && newRow < rows && newCol >= 0 && newCol < cols) {
                neighbors.push(newRow * cols + newCol);
            }
        }
    }

    return neighbors;
}

// 渲染棋盘
function renderBoard() {
    boardElement.innerHTML = '';

    board.forEach((cell, index) => {
        const cellElement = document.createElement('div');
        cellElement.classList.add('cell');
        cellElement.dataset.index = index;

        cellElement.addEventListener('click', handleClick);
        cellElement.addEventListener('contextmenu', handleRightClick);

        boardElement.appendChild(cellElement);
    });
}

// 处理左键点击
function handleClick(e) {
    if (gameOver) return;

    const index = parseInt(e.target.dataset.index);

    if (board[index].flagged || board[index].revealed) return;

    // 第一次点击：放置地雷并开始计时
    if (firstClick) {
        placeMines(index);
        calculateNumbers();
        firstClick = false;

        timerInterval = setInterval(() => {
            timer++;
            timerElement.textContent = timer;
        }, 1000);
    }

    revealCell(index);
}

// 处理右键点击
function handleRightClick(e) {
    e.preventDefault();

    if (gameOver || firstClick) return;

    const index = parseInt(e.target.dataset.index);

    if (board[index].revealed) return;

    const cellElement = e.target;

    if (board[index].flagged) {
        board[index].flagged = false;
        cellElement.classList.remove('flagged');
        minesCount++;
    } else {
        board[index].flagged = true;
        cellElement.classList.add('flagged');
        minesCount--;
    }

    minesCountElement.textContent = minesCount;
}

// 揭开格子
function revealCell(index) {
    const config = DIFFICULTY[currentDifficulty];

    if (index < 0 || index >= board.length) return;
    if (board[index].revealed || board[index].flagged) return;

    const cellElement = document.querySelector(`[data-index="${index}"]`);
    board[index].revealed = true;
    cellElement.classList.add('revealed');

    if (board[index].mine) {
        cellElement.classList.add('mine');
        cellElement.textContent = '💣';
        endGame(false);
        return;
    }

    if (board[index].neighborMines > 0) {
        cellElement.textContent = board[index].neighborMines;
        cellElement.style.color = getNumberColor(board[index].neighborMines);
    } else {
        // 递归打开相邻格子
        const neighbors = getNeighbors(index, config.rows, config.cols);
        neighbors.forEach(neighborIndex => {
            revealCell(neighborIndex);
        });
    }

    // 检查胜利
    checkWin();
}

// 获取数字颜色
function getNumberColor(num) {
    const colors = {
        1: '#0000ff',
        2: '#008000',
        3: '#ff0000',
        4: '#000080',
        5: '#800000',
        6: '#008080',
        7: '#000000',
        8: '#808080'
    };
    return colors[num] || '#000';
}

// 检查胜利条件
function checkWin() {
    const config = DIFFICULTY[currentDifficulty];
    let revealedCount = 0;

    board.forEach(cell => {
        if (cell.revealed) revealedCount++;
    });

    const totalCells = config.rows * config.cols;
    if (revealedCount === totalCells - config.mines) {
        endGame(true);
    }
}

// 游戏结束
function endGame(won) {
    gameOver = true;

    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }

    if (won) {
        // 标记所有地雷
        minesLocations.forEach(index => {
            const cellElement = document.querySelector(`[data-index="${index}"]`);
            if (!board[index].flagged) {
                cellElement.classList.add('flagged');
            }
        });

        // 庆祝动画
        document.querySelectorAll('.cell.revealed').forEach(cell => {
            cell.classList.add('win');
        });

        setTimeout(() => {
            alert(`🎉 恭喜你赢了！\n\n难度: ${getDifficultyName()}\n用时: ${timer} 秒`);
        }, 500);
    } else {
        // 显示所有地雷
        minesLocations.forEach(index => {
            const cellElement = document.querySelector(`[data-index="${index}"]`);
            cellElement.classList.add('revealed', 'mine');
            cellElement.textContent = '💣';
        });

        setTimeout(() => {
            alert(`💥 游戏结束！\n\n你踩到了地雷。\n用时: ${timer} 秒`);
        }, 300);
    }
}

// 获取难度名称
function getDifficultyName() {
    const names = {
        easy: '简单',
        medium: '中等',
        hard: '困难'
    };
    return names[currentDifficulty];
}

// 难度选择
document.querySelectorAll('.difficulty-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.difficulty-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentDifficulty = btn.dataset.difficulty;
        initGame();
    });
});

// 初始化游戏
initGame();

class Minesweeper {
    constructor() {
        this.grid = [];
        this.rows = 9;
        this.cols = 9;
        this.mines = 10;
        this.minePositions = [];
        this.gameOver = false;
        this.gameStarted = false;
        this.timer = 0;
        this.timerInterval = null;
        this.flagged = 0;
        this.revealed = 0;

        this.gameBoard = document.getElementById('gameBoard');
        this.mineCountElement = document.getElementById('mineCount');
        this.timerElement = document.getElementById('timer');
        this.messageElement = document.getElementById('message');
        this.restartBtn = document.getElementById('restartBtn');

        this.difficulties = {
            easy: { rows: 9, cols: 9, mines: 10 },
            medium: { rows: 16, cols: 16, mines: 40 },
            hard: { rows: 16, cols: 30, mines: 99 }
        };

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.startNewGame();
    }

    setupEventListeners() {
        // 难度选择
        document.querySelectorAll('.difficulty-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.difficulty-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                const difficulty = e.target.dataset.difficulty;
                const config = this.difficulties[difficulty];
                this.rows = config.rows;
                this.cols = config.cols;
                this.mines = config.mines;
                this.startNewGame();
            });
        });

        // 重新开始按钮
        this.restartBtn.addEventListener('click', () => this.startNewGame());

        // 禁用右键菜单
        this.gameBoard.addEventListener('contextmenu', (e) => e.preventDefault());
    }

    startNewGame() {
        this.gameOver = false;
        this.gameStarted = false;
        this.timer = 0;
        this.flagged = 0;
        this.revealed = 0;
        this.minePositions = [];

        this.stopTimer();
        this.timerElement.textContent = '0';
        this.updateMineCount();
        this.messageElement.className = 'message';
        this.messageElement.style.display = 'none';

        this.createGrid();
    }

    createGrid() {
        this.grid = [];
        this.gameBoard.innerHTML = '';

        const gridElement = document.createElement('div');
        gridElement.className = 'grid';
        gridElement.style.gridTemplateColumns = `repeat(${this.cols}, 30px)`;

        for (let i = 0; i < this.rows; i++) {
            this.grid[i] = [];
            for (let j = 0; j < this.cols; j++) {
                const cell = document.createElement('div');
                cell.className = 'cell';
                cell.dataset.row = i;
                cell.dataset.col = j;

                cell.addEventListener('click', (e) => this.handleClick(e, i, j));
                cell.addEventListener('contextmenu', (e) => this.handleRightClick(e, i, j));

                this.grid[i][j] = {
                    element: cell,
                    isMine: false,
                    revealed: false,
                    flagged: false,
                    neighborMines: 0
                };

                gridElement.appendChild(cell);
            }
        }

        this.gameBoard.appendChild(gridElement);
    }

    placeMines(excludeRow, excludeCol) {
        let placed = 0;
        while (placed < this.mines) {
            const row = Math.floor(Math.random() * this.rows);
            const col = Math.floor(Math.random() * this.cols);

            // 确保第一次点击的位置周围3x3区域没有地雷
            if (Math.abs(row - excludeRow) <= 1 && Math.abs(col - excludeCol) <= 1) {
                continue;
            }

            if (!this.grid[row][col].isMine) {
                this.grid[row][col].isMine = true;
                this.minePositions.push({ row, col });
                placed++;
            }
        }

        this.calculateNeighbors();
    }

    calculateNeighbors() {
        for (let i = 0; i < this.rows; i++) {
            for (let j = 0; j < this.cols; j++) {
                if (!this.grid[i][j].isMine) {
                    this.grid[i][j].neighborMines = this.countNeighborMines(i, j);
                }
            }
        }
    }

    countNeighborMines(row, col) {
        let count = 0;
        for (let i = -1; i <= 1; i++) {
            for (let j = -1; j <= 1; j++) {
                const newRow = row + i;
                const newCol = col + j;
                if (this.isValidCell(newRow, newCol) && this.grid[newRow][newCol].isMine) {
                    count++;
                }
            }
        }
        return count;
    }

    isValidCell(row, col) {
        return row >= 0 && row < this.rows && col >= 0 && col < this.cols;
    }

    handleClick(e, row, col) {
        if (this.gameOver || this.grid[row][col].flagged || this.grid[row][col].revealed) {
            return;
        }

        if (!this.gameStarted) {
            this.gameStarted = true;
            this.placeMines(row, col);
            this.startTimer();
        }

        this.revealCell(row, col);
    }

    handleRightClick(e, row, col) {
        e.preventDefault();
        if (this.gameOver || this.grid[row][col].revealed) {
            return;
        }

        if (!this.gameStarted) {
            this.gameStarted = true;
            this.placeMines(row, col);
            this.startTimer();
        }

        const cell = this.grid[row][col];
        cell.flagged = !cell.flagged;

        if (cell.flagged) {
            cell.element.classList.add('flagged');
            cell.element.textContent = '🚩';
            this.flagged++;
        } else {
            cell.element.classList.remove('flagged');
            cell.element.textContent = '';
            this.flagged--;
        }

        this.updateMineCount();
    }

    revealCell(row, col) {
        const cell = this.grid[row][col];
        if (cell.revealed || cell.flagged) {
            return;
        }

        cell.revealed = true;
        cell.element.classList.add('revealed');
        this.revealed++;

        if (cell.isMine) {
            cell.element.classList.add('exploded');
            cell.element.textContent = '💣';
            this.endGame(false);
            return;
        }

        if (cell.neighborMines > 0) {
            cell.element.textContent = cell.neighborMines;
            cell.element.classList.add(`number-${cell.neighborMines}`);
        } else {
            // 空白格子，递归揭开周围的格子
            for (let i = -1; i <= 1; i++) {
                for (let j = -1; j <= 1; j++) {
                    const newRow = row + i;
                    const newCol = col + j;
                    if (this.isValidCell(newRow, newCol)) {
                        this.revealCell(newRow, newCol);
                    }
                }
            }
        }

        this.checkWin();
    }

    checkWin() {
        const totalCells = this.rows * this.cols;
        const safeCells = totalCells - this.mines;
        if (this.revealed === safeCells) {
            this.endGame(true);
        }
    }

    endGame(won) {
        this.gameOver = true;
        this.stopTimer();

        if (won) {
            this.messageElement.textContent = '🎉 恭喜你赢了！';
            this.messageElement.className = 'message win';
            // 标记所有地雷
            this.minePositions.forEach(pos => {
                const cell = this.grid[pos.row][pos.col];
                if (!cell.flagged) {
                    cell.element.textContent = '🚩';
                    cell.element.classList.add('flagged');
                }
            });
        } else {
            this.messageElement.textContent = '💥 游戏结束！';
            this.messageElement.className = 'message lose';
            // 显示所有地雷
            this.minePositions.forEach(pos => {
                const cell = this.grid[pos.row][pos.col];
                if (!cell.revealed) {
                    cell.element.classList.add('revealed', 'mine');
                    cell.element.textContent = '💣';
                }
            });
            // 标记错误的地雷标记
            for (let i = 0; i < this.rows; i++) {
                for (let j = 0; j < this.cols; j++) {
                    const cell = this.grid[i][j];
                    if (cell.flagged && !cell.isMine) {
                        cell.element.style.backgroundColor = '#FFCDD2';
                        cell.element.textContent = '❌';
                    }
                }
            }
        }

        this.messageElement.style.display = 'block';
    }

    startTimer() {
        this.timerInterval = setInterval(() => {
            this.timer++;
            this.timerElement.textContent = this.timer;
        }, 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    updateMineCount() {
        this.mineCountElement.textContent = this.mines - this.flagged;
    }
}

// 启动游戏
document.addEventListener('DOMContentLoaded', () => {
    new Minesweeper();
});

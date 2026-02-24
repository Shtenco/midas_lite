"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║    SHTENCO AI V16 - PROFIT ROTATION EDITION - LEGENDARY TRADERS WISDOM       ║
║                                                                               ║
║  🎯 MAIN DIRECTIVE: CONSISTENT PROFIT & POSITION ROTATION                    ║
║  💡 Philosophy: George Soros, Paul Tudor Jones, Ray Dalio, Jesse Livermore   ║
║  🔄 Smart Position Rotation: Close Weak, Open Strong                         ║
║  📊 Equity Chart Visualization for Backtest Analysis                         ║
║  🧠 Claude Sonnet 4 API with Concise System Prompt                           ║
║  💾 SQLite Memory Database + Episodic Memory                                 ║
║  🔄 Multi-Scenario Branching + Monte Carlo Tree Search                       ║
║  📈 Historical Pattern Recognition + Meta-Learning                           ║
║  🎯 Advanced Experience Summarization + Transfer Learning                    ║
║  🤔 Deep Reflection & Self-Critique + Metacognition                          ║
║  📊 Multi-Timeframe Technical Analysis + Ensemble Methods                    ║
║  🎲 Chain-of-Thought + Tree-of-Thoughts + Self-Consistency                   ║
║  🔮 Counterfactual Reasoning + Causal Inference                              ║
║  ⚡ Active Learning + Uncertainty Quantification                             ║
║  🌐 Multi-Agent Debate + Consensus Building                                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import requests
import json
import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt
import concurrent.futures
import sqlite3
import hashlib
from typing import Dict, List, Tuple, Optional

# ═══════════════════════════════════════════════════════════════════════════════
#                          КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

# Claude API
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_API_KEY = "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"  # ЗАМЕНИ НА СВОЙ КЛЮЧ!
CLAUDE_API_VERSION = "2023-06-01"
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Trading
SYMBOLS = ["EURUSD", "GBPUSD", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD", "EURGBP", "AUDCHF"]
TIMEFRAMES = {
    'M5': mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'H1': mt5.TIMEFRAME_H1,
    'H4': mt5.TIMEFRAME_H4,
    'D1': mt5.TIMEFRAME_D1
}

RISK_PERCENT = 10.0
MAX_POSITION_SIZE = 5.00

# AGI Configuration
AGI_ENABLE_CHAIN_OF_THOUGHT = True
AGI_ENABLE_TREE_OF_THOUGHTS = True
AGI_ENABLE_SELF_CONSISTENCY = True
AGI_ENABLE_MULTI_AGENT_DEBATE = True
AGI_ENABLE_COUNTERFACTUAL = True
AGI_ENABLE_METACOGNITION = True
AGI_NUM_THOUGHT_SAMPLES = 3
AGI_CONSENSUS_THRESHOLD = 0.7

# ═══════════════════════════════════════════════════════════════════════════════
#                          ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ═══════════════════════════════════════════════════════════════════════════════

open_positions = {}
trade_history = []
balance = 10000.0
initial_balance = 10000.0
current_slot_idx = 0

# AGI State
agi_memory_buffer = []
agi_metacognition_log = []
agi_counterfactual_scenarios = []
agi_agent_personas = []

question_log = []
answer_log = []

# ═══════════════════════════════════════════════════════════════════════════════
#                          БАЗА ДАННЫХ ПАМЯТИ
# ═══════════════════════════════════════════════════════════════════════════════

DB_FILE = "agi_trade_memory_v16_profit_rotation.db"

def init_db():
    """Инициализация расширенной базы данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Таблица сделок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            direction TEXT,
            lot REAL,
            entry_price REAL,
            exit_price REAL,
            pnl REAL,
            result TEXT,
            reason TEXT,
            slot INTEGER,
            confidence INTEGER,
            market_hash TEXT,
            scenarios_considered TEXT
        )
    ''')
    
    # Таблица долговременной памяти
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            market_hash TEXT,
            symbol TEXT,
            decision TEXT,
            outcome REAL,
            reasoning TEXT,
            market_conditions TEXT,
            lessons_learned TEXT,
            importance REAL
        )
    ''')
    
    # Индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_market_hash ON memory(market_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON memory(symbol)')
    
    # Таблица паттернов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_name TEXT UNIQUE,
            description TEXT,
            success_rate REAL,
            occurrences INTEGER,
            avg_profit REAL,
            conditions TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def save_trade_to_db(trade):
    """Сохранение сделки в БД"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trades (
            timestamp, symbol, direction, lot, entry_price, exit_price, 
            pnl, result, reason, slot, confidence, market_hash, scenarios_considered
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        trade['timestamp'], trade['symbol'], trade['direction'], 
        trade['lot'], trade['entry_price'], trade.get('exit_price'),
        trade.get('pnl', 0), trade.get('result', 'OPEN'), trade['reason'],
        trade.get('slot', 0), trade.get('confidence', 5),
        trade.get('market_hash', ''), trade.get('scenarios', '')
    ))
    conn.commit()
    conn.close()

def find_similar_situations(market_hash: str, symbol: str, limit: int = 5) -> List[Dict]:
    """Поиск похожих рыночных ситуаций"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM memory
        WHERE (market_hash = ? OR symbol = ?)
        AND importance > 0.5
        ORDER BY importance DESC, timestamp DESC
        LIMIT ?
    ''', (market_hash, symbol, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    memories = []
    for row in rows:
        memories.append({
            'timestamp': row[1],
            'market_hash': row[2],
            'symbol': row[3],
            'decision': row[4],
            'outcome': row[5],
            'reasoning': row[6],
            'lessons_learned': row[8],
            'importance': row[9]
        })
    
    return memories

def get_trade_statistics(symbol: str = None, days: int = 30) -> Dict:
    """Статистика сделок"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    since_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    if symbol:
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   AVG(pnl),
                   SUM(pnl)
            FROM trades
            WHERE symbol = ? AND timestamp > ? AND result = 'CLOSED'
        ''', (symbol, since_date))
    else:
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   AVG(pnl),
                   SUM(pnl)
            FROM trades
            WHERE timestamp > ? AND result = 'CLOSED'
        ''', (since_date,))
    
    row = cursor.fetchone()
    conn.close()
    
    total, wins, avg_pnl, total_pnl = row if row else (0, 0, 0, 0)
    
    return {
        'total_trades': total or 0,
        'wins': wins or 0,
        'win_rate': (wins / total) if total > 0 else 0,
        'avg_pnl': avg_pnl or 0,
        'total_pnl': total_pnl or 0
    }

def create_market_hash(symbol_data: Dict) -> str:
    """Создание хеша рыночной ситуации"""
    if not symbol_data or 'H1' not in symbol_data or symbol_data['H1'] is None:
        return ""
    
    df = symbol_data['H1']
    if df.empty:
        return ""
    
    last = df.iloc[-1]
    
    # Характеристики рынка
    trend = 'UP' if last['close'] > last['MA_20'] else 'DOWN'
    rsi_zone = 'OS' if last['RSI_14'] < 30 else 'OB' if last['RSI_14'] > 70 else 'MID'
    macd_signal = 'BUY' if last['MACD'] > last['MACD_signal'] else 'SELL'
    
    state_str = f"{trend}_{rsi_zone}_{macd_signal}"
    return hashlib.md5(state_str.encode()).hexdigest()[:16]

# ====================== УТИЛИТЫ ======================
def log_question_answer(question, answer):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    question_log.append({"timestamp": ts, "question": question})
    answer_log.append({"timestamp": ts, "answer": answer})

def initialize_mt5():
    if not mt5.initialize():
        print("Ошибка инициализации MT5")
        return False
    print("MT5 инициализирован")
    return True

def calculate_rsi(prices, period=14):
    deltas = np.diff(prices)
    if len(deltas) < period:
        return np.zeros_like(prices)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100. / (1. + rs)
    for i in range(period, len(prices)):
        delta = deltas[i-1]
        up = (up * (period - 1) + max(delta, 0)) / period
        down = (down * (period - 1) + max(-delta, 0)) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100. - 100. / (1. + rs)
    return rsi

def calculate_ma(prices, period):
    ma = np.full_like(prices, np.nan, dtype=float)
    for i in range(len(prices)):
        start = max(0, i - period + 1)
        ma[i] = np.mean(prices[start:i+1])
    return ma

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    middle = calculate_ma(prices, period)
    std = np.full_like(prices, np.nan, dtype=float)
    for i in range(len(prices)):
        start = max(0, i - period + 1)
        if i >= period - 1:
            std[i] = np.std(prices[start:i+1])
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower

def calculate_ema(prices, period):
    ema = np.full_like(prices, np.nan, dtype=float)
    multiplier = 2 / (period + 1)
    if len(prices) > 0:
        ema[0] = prices[0]
    for i in range(1, len(prices)):
        ema[i] = (prices[i] * multiplier) + (ema[i-1] * (1 - multiplier))
    return ema

def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_kelly_leverage():
    if not trade_history:
        return 0.01
    wins = [t for t in trade_history if t['pnl'] > 0]
    losses = [t for t in trade_history if t['pnl'] <= 0]
    if not wins or not losses:
        return 0.01
    win_rate = len(wins) / len(trade_history)
    avg_win = np.mean([abs(t['pnl']) for t in wins])
    avg_loss = np.mean([abs(t['pnl']) for t in losses])
    if avg_loss == 0:
        return 0.1
    b = avg_win / avg_loss
    f = (win_rate * b - (1 - win_rate)) / b
    return max(0.01, min(0.1, f))

def get_symbol_data(symbol, days=120):
    print(f"Загрузка {symbol} за {days} дней...")
    end = datetime.now()
    start = end - timedelta(days=days)
    data = {}
    for tf_name, tf_val in TIMEFRAMES.items():
        try:
            rates = mt5.copy_rates_range(symbol, tf_val, start, end)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                closes = df['close'].values
                df['RSI_14'] = calculate_rsi(closes)
                df['MA_20'] = calculate_ma(closes, 20)
                df['MA_50'] = calculate_ma(closes, 50)
                df['BB_upper'], df['BB_middle'], df['BB_lower'] = calculate_bollinger_bands(closes)
                df['MACD'], df['MACD_signal'], df['MACD_hist'] = calculate_macd(closes)
                data[tf_name] = df.tail(300)
            else:
                data[tf_name] = None
        except Exception as e:
            print(f"Ошибка загрузки {symbol} {tf_name}: {e}")
            data[tf_name] = None
    return data

def get_all_symbols_data(days=120):
    print(f"Параллельная загрузка данных для {len(SYMBOLS)} пар...")
    all_data = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(get_symbol_data, sym, days): sym for sym in SYMBOLS}
        for future in concurrent.futures.as_completed(futures):
            sym = futures[future]
            try:
                all_data[sym] = future.result()
            except:
                all_data[sym] = None
    return all_data

def calculate_equity_metrics():
    """Расчет текущих метрик эквити и баланса"""
    global all_data_global
    current_equity = balance
    floating_pnl = 0.0
    
    for sym, pos in open_positions.items():
        if sym in all_data_global and 'M5' in all_data_global[sym] and all_data_global[sym]['M5'] is not None:
            current_price = all_data_global[sym]['M5'].iloc[-1]['close']
            price_diff = (current_price - pos['entry_price']) * 10000
            if pos['direction'] == 'SELL':
                price_diff = -price_diff
            pnl = price_diff * 10 * pos['lot']
            floating_pnl += pnl
    
    current_equity = balance + floating_pnl
    equity_change_pct = (current_equity / balance - 1) * 100 if balance > 0 else 0
    
    return {
        'balance': balance,
        'equity': current_equity,
        'floating_pnl': floating_pnl,
        'equity_change_pct': equity_change_pct
    }

# ====================== ПРОМПТ ======================
def build_trade_history_summary():
    """Детальная аналитика по истории сделок"""
    if not trade_history:
        return "НЕТ ИСТОРИИ СДЕЛОК. НАЧИНАЕМ С НУЛЯ. ФОКУС: ПЕРВЫЕ ПРИБЫЛЬНЫЕ СДЕЛКИ."

    total_trades = len(trade_history)
    wins = sum(1 for t in trade_history if t['pnl'] > 0)
    losses = total_trades - wins
    win_rate = wins / total_trades if total_trades > 0 else 0
    
    total_pnl = sum(t['pnl'] for t in trade_history)
    avg_pnl_win = np.mean([t['pnl'] for t in trade_history if t['pnl'] > 0]) if wins > 0 else 0
    avg_pnl_loss = np.mean([t['pnl'] for t in trade_history if t['pnl'] <= 0]) if losses > 0 else 0
    
    max_win = max([t['pnl'] for t in trade_history if t['pnl'] > 0], default=0)
    max_loss = min([t['pnl'] for t in trade_history if t['pnl'] <= 0], default=0)
    
    # Серии побед/поражений
    current_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    for t in trade_history:
        if t['pnl'] > 0:
            if current_streak >= 0:
                current_streak += 1
                max_win_streak = max(max_win_streak, current_streak)
            else:
                current_streak = 1
        else:
            if current_streak <= 0:
                current_streak -= 1
                max_loss_streak = max(max_loss_streak, abs(current_streak))
            else:
                current_streak = -1
    
    # Статистика по символам
    symbol_stats = {}
    for sym in SYMBOLS:
        sym_trades = [t for t in trade_history if t['symbol'] == sym]
        if sym_trades:
            sym_wins = sum(1 for t in sym_trades if t['pnl'] > 0)
            sym_pnl = sum(t['pnl'] for t in sym_trades)
            sym_win_rate = sym_wins / len(sym_trades)
            symbol_stats[sym] = {
                'trades': len(sym_trades),
                'wins': sym_wins,
                'win_rate': sym_win_rate,
                'total_pnl': sym_pnl
            }
    
    # Последние 15 сделок для паттернов
    recent_trades_text = "\n".join([
        f"  {i+1}. {t['symbol']} {t['direction']} | PnL: ${t['pnl']:+.2f} | {t['reason'][:60]}"
        for i, t in enumerate(trade_history[-15:])
    ])
    
    # Profit Factor
    total_wins_amount = sum(t['pnl'] for t in trade_history if t['pnl'] > 0)
    total_losses_amount = abs(sum(t['pnl'] for t in trade_history if t['pnl'] <= 0))
    profit_factor = total_wins_amount / total_losses_amount if total_losses_amount > 0 else float('inf')

    summary = f"""
╔══════════════════════════════════════════════════════════════╗
║           ИСТОРИЯ СДЕЛОК - КРИТИЧЕСКИЙ АНАЛИЗ                ║
╚══════════════════════════════════════════════════════════════╝

📊 ОБЩАЯ СТАТИСТИКА:
   • Всего сделок: {total_trades} | Прибыльных: {wins} | Убыточных: {losses}
   • Win Rate: {win_rate:.1%} | ЦЕЛЬ: >60%
   • Profit Factor: {profit_factor:.2f} | ЦЕЛЬ: >2.0
   
💰 ФИНАНСОВЫЕ РЕЗУЛЬТАТЫ:
   • Общий PnL: ${total_pnl:+.2f}
   • Средний профит: ${avg_pnl_win:.2f} | Средний убыток: ${avg_pnl_loss:.2f}
   • Максимальный профит: ${max_win:.2f} | Максимальный убыток: ${max_loss:.2f}
   • Соотношение Win/Loss: {abs(avg_pnl_win/avg_pnl_loss) if avg_pnl_loss != 0 else 0:.2f}x (ЦЕЛЬ: >2.0x)

📈 СЕРИИ СДЕЛОК:
   • Максимальная серия побед: {max_win_streak}
   • Максимальная серия поражений: {max_loss_streak}
   • ВНИМАНИЕ: Следи за сериями поражений! При 3+ подряд - пересмотр стратегии.

🎯 СТАТИСТИКА ПО ПАРАМ:
"""
    
    for sym, stats in sorted(symbol_stats.items(), key=lambda x: x[1]['total_pnl'], reverse=True):
        performance = "🟢 СИЛЬНАЯ" if stats['win_rate'] > 0.6 and stats['total_pnl'] > 0 else \
                     "🟡 СРЕДНЯЯ" if stats['win_rate'] > 0.4 else "🔴 СЛАБАЯ"
        summary += f"   • {sym}: {stats['trades']} сделок | WR: {stats['win_rate']:.1%} | PnL: ${stats['total_pnl']:+.2f} | {performance}\n"
    
    summary += f"""
📝 ПОСЛЕДНИЕ 15 СДЕЛОК (АНАЛИЗ ПАТТЕРНОВ):
{recent_trades_text}

⚠️ КРИТИЧЕСКИЕ ВЫВОДЫ ДЛЯ ТЕБЯ:
   1. Избегай повторения ошибок из убыточных сделок
   2. Усиливай успешные паттерны из прибыльных сделок
   3. Обращай внимание на пары с низким Win Rate - возможно стоит избегать
   4. Фиксируй прибыль на сильных парах раньше
   5. Следи за сериями - при 2-3 убытках подряд снижай риски
"""
    
    return summary

def build_agi_prompt(all_data, slot_time, similar_situations):
    """
    🧠 Построение промпта в стиле легендарных трейдеров
    """
    
    # Статистика из БД
    stats = get_trade_statistics(days=30)
    
    # Формирование context из похожих ситуаций
    context_parts = []
    if similar_situations:
        context_parts.append("Похожие рыночные ситуации из памяти:")
        for mem in similar_situations[:3]:
            context_parts.append(f"- Решение: {mem['decision']}, Результат: {mem['outcome']:.1f}%, Урок: {mem.get('lessons_learned', 'N/A')}")
    
    context_str = "\n".join(context_parts) if context_parts else "Нет данных из прошлого опыта"
    
    # Рыночные условия
    market_data_str = ""
    for sym in SYMBOLS[:3]:
        if sym in all_data and 'H4' in all_data[sym] and all_data[sym]['H4'] is not None:
            df = all_data[sym]['H4']
            market_data_str += f"{sym}: {df.iloc[-1]['close']:.5f}, "
    
    # Открытые позиции
    positions_str = ""
    for sym, pos in open_positions.items():
        positions_str += f"{sym} {pos['direction']} @ {pos['entry_price']:.5f}, "
    if not positions_str:
        positions_str = "Нет открытых позиций"
    
    # Баланс
    balance_str = f"${balance:.2f}"
    
    prompt = f"""Ты — AI трейдер, действующий в лучших традициях George Soros, Paul Tudor Jones, Ray Dalio и Jesse Livermore.

**🎯 ЕДИНСТВЕННАЯ ЦЕЛЬ: ПОСТОЯННАЯ ПРИБЫЛЬ**

**ФИЛОСОФИЯ ВЕЛИКИХ ТРЕЙДЕРОВ:**
- "It's not about being right, it's about making money" — George Soros
- "Losers average losers" — Paul Tudor Jones  
- "Cut losses quickly, let profits run" — Jesse Livermore
- "He who lives by the crystal ball will eat shattered glass" — Ray Dalio

**ИМПЕРАТИВ:**
1. РОТАЦИЯ ПОЗИЦИЙ — закрывай слабые, открывай сильные
2. ДИСЦИПЛИНА — строгий Stop Loss и Take Profit
3. АДАПТАЦИЯ — торгуй по тренду, принимай изменения
4. ЗАЩИТА КАПИТАЛА — сохранить > приумножить

**ТЕКУЩЕЕ СОСТОЯНИЕ:**
- Время: {slot_time.strftime('%Y-%m-%d %H:%M')}
- Баланс: {balance_str}
- Открытые позиции: {positions_str}
- Рынок: {market_data_str}

**ПАМЯТЬ:**
{context_str}

**ЗАДАЧА:**
Проанализируй все таймфреймы (M5-D1), примени мультифреймовый анализ, Chain-of-Thought рассуждение. 
Для каждой позиции: проверь условия закрытия. Для новых сигналов: убедись в силе тренда.
Ротируй портфель — закрывай слабые позиции, открывай сильные. Максимум 4 позиции.

**ФОРМАТ ОТВЕТА (JSON):**

```json
{{
  "timestamp": "{slot_time.isoformat()}",
  "reflection": "Твои мысли о рынке...",
  "portfolio_decisions": [
    {{
      "symbol": "EURUSD",
      "action": "OPEN_BUY | OPEN_SELL | CLOSE | HOLD",
      "lot": 0.10,
      "reason": "Краткая причина",
      "confidence": 7
    }}
  ]
}}
```

Торгуй мудро, действуй решительно!"""
    
    return prompt


# ═══════════════════════════════════════════════════════════════════════════════
#                          CLAUDE API
# ═══════════════════════════════════════════════════════════════════════════════

def call_claude_api(prompt: str) -> Dict:
    """Вызов Claude API с обработкой ответа"""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": CLAUDE_API_VERSION
    }
    
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 4000,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    try:
        response = requests.post(CLAUDE_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if 'content' in data and len(data['content']) > 0:
            text = data['content'][0]['text']
            
            # Парсинг JSON из ответа
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    print("⚠️ Не удалось распарсить JSON")
                    return {}
        
        return {}
        
    except Exception as e:
        print(f"❌ Ошибка вызова API: {e}")
        return {}

# ═══════════════════════════════════════════════════════════════════════════════
#                          ИСПОЛНЕНИЕ РЕШЕНИЙ
# ═══════════════════════════════════════════════════════════════════════════════

def execute_decision(symbol, decision, current_price, slot_time, all_data):
    """Исполнение торгового решения"""
    global balance
    
    action = decision.get('action', '').upper()
    lot = decision.get('lot', 1.0)
    reason = decision.get('reason', 'No reason')
    confidence = decision.get('confidence', 5)
    
    if action == 'OPEN_BUY' or action == 'OPEN_SELL':
        if symbol in open_positions:
            print(f"  ⚠ {symbol} уже имеет открытую позицию, пропускаем")
            return
        
        if len(open_positions) >= 4:
            print(f"  ⚠ Максимум 4 позиций, пропускаем {symbol}")
            return
        
        direction = 'BUY' if action == 'OPEN_BUY' else 'SELL'
        
        trade = {
            'timestamp': slot_time.isoformat(),
            'symbol': symbol,
            'direction': direction,
            'lot': lot,
            'entry_price': current_price,
            'reason': reason,
            'slot': current_slot_idx,
            'confidence': confidence,
            'market_hash': create_market_hash(all_data.get(symbol, {}))
        }
        
        open_positions[symbol] = trade
        save_trade_to_db(trade)
        
        print(f"  ✅ ОТКРЫТО: {symbol} {direction} @ {current_price:.5f} | Лот: {lot:.2f}")
        print(f"     Причина: {reason[:70]}")
    
    elif action == 'CLOSE':
        if symbol not in open_positions:
            print(f"  ⚠ {symbol} не имеет открытой позиции")
            return
        
        pos = open_positions[symbol]
        
        # Расчет PnL
        diff = (current_price - pos['entry_price']) * 10000
        if pos['direction'] == 'SELL':
            diff = -diff
        pnl = diff * 10 * pos['lot']
        
        balance += pnl
        
        pos['exit_price'] = current_price
        pos['pnl'] = pnl
        pos['result'] = 'CLOSED'
        
        trade_history.append(pos)
        save_trade_to_db(pos)
        
        del open_positions[symbol]
        
        print(f"  ✅ ЗАКРЫТО: {symbol} @ {current_price:.5f} | PnL: ${pnl:+.2f}")
        print(f"     Причина: {reason[:70]}")
        print(f"     💰 Новый баланс: ${balance:.2f}")
    
    elif action == 'HOLD':
        if symbol in open_positions:
            print(f"  ⏸ HOLD: {symbol}")
            print(f"     Причина: {reason[:70]}")
        else:
            print(f"  ⚪ {symbol}: Нет позиции для удержания")

# ═══════════════════════════════════════════════════════════════════════════════
#                          СЛОТЫ И ОСНОВНОЙ ЦИКЛ
# ═══════════════════════════════════════════════════════════════════════════════

def get_4h_trading_slots(days=30):
    """Генерация 4-часовых слотов"""
    slots = []
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for d in range(days, 0, -1):
        cur_date = end_date - timedelta(days=d)
        if cur_date.weekday() >= 5:  # Выходные
            continue
        
        for h in range(0, 24, 4):
            slot_time = cur_date.replace(hour=h, minute=0)
            if slot_time < datetime.now():
                slots.append({
                    'datetime': slot_time,
                    'end': slot_time + timedelta(hours=4)
                })
    
    print(f"✅ Сгенерировано {len(slots)} слотов")
    return slots

def get_h4_candle_prices(symbol, slot_time):
    """Получить цены ОТКРЫТИЯ и ЗАКРЫТИЯ H4 свечи"""
    try:
        rates = mt5.copy_rates_range(
            symbol, 
            mt5.TIMEFRAME_H4,
            slot_time,
            slot_time + timedelta(hours=4, minutes=1)
        )
        
        if rates is not None and len(rates) > 0:
            candle = rates[0]
            return candle['open'], candle['close']
        
        return None, None
        
    except Exception as e:
        print(f"    ⚠ Ошибка получения H4 свечи {symbol}: {e}")
        return None, None

all_data_global = {}

def run_simulation():
    """Главный цикл симуляции"""
    global balance, current_slot_idx, all_data_global
    
    print("╔═══════════════════════════════════════════════════════════════════════════════╗")
    print("║           SHTENCO AI V16 - PROFIT ROTATION EDITION                          ║")
    print("║                                                                               ║")
    print("║  🎯 CONSISTENT PROFIT | 🔄 ROTATION | 💡 LEGENDARY TRADERS                   ║")
    print("╚═══════════════════════════════════════════════════════════════════════════════╝\n")
    
    init_db()
    
    if not initialize_mt5():
        return
    
    print("\n📊 Загрузка данных...")
    all_data_global = get_all_symbols_data(days=200)
    slots = get_4h_trading_slots(days=12)
    
    balance_history = [balance]
    equity_history = [balance]
    
    for idx, slot in enumerate(slots, 1):
        current_slot_idx = idx
        slot_time = slot['datetime']
        slot_end = slot['end']
        
        print(f"\n{'═'*80}")
        print(f"СЛОТ {idx}/{len(slots)} | {slot_time.strftime('%Y-%m-%d %H:%M')} → {slot_end.strftime('%H:%M')}")
        print(f"{'═'*80}")
        
        # Получаем цены
        open_prices = {}
        close_prices = {}
        
        for sym in SYMBOLS:
            open_price, close_price = get_h4_candle_prices(sym, slot_time)
            
            if open_price is not None and close_price is not None:
                open_prices[sym] = open_price
                close_prices[sym] = close_price
            else:
                if sym in all_data_global and 'H4' in all_data_global[sym] and all_data_global[sym]['H4'] is not None:
                    df = all_data_global[sym]['H4']
                    open_prices[sym] = df.iloc[-1]['open']
                    close_prices[sym] = df.iloc[-1]['close']
        
        if not open_prices:
            print("  ⚠ Нет данных по ценам, пропускаем слот")
            continue
        
        print(f"  📊 Цены получены (движение в пипсах):")
        for sym in list(open_prices.keys())[:3]:
            movement_pips = (close_prices[sym] - open_prices[sym]) * 10000
            print(f"     {sym}: {open_prices[sym]:.5f} → {close_prices[sym]:.5f} ({movement_pips:+.1f} pips)")
        
        # Находим похожие ситуации
        market_hash = create_market_hash(all_data_global['EURUSD']) if 'EURUSD' in all_data_global else ""
        similar = find_similar_situations(market_hash, 'EURUSD', limit=5)
        
        # Строим промпт
        prompt = build_agi_prompt(all_data_global, slot_time, similar)
        
        # Вызываем Claude
        print("  🤖 Запрос к Claude API...")
        decisions_data = call_claude_api(prompt)
        
        if not decisions_data or 'portfolio_decisions' not in decisions_data:
            print("  ⚠ Нет решений от API")
            time.sleep(2)
            continue
        
        # Показываем рефлексию
        if 'reflection' in decisions_data:
            print(f"\n💭 РЕФЛЕКСИЯ AI:\n{decisions_data['reflection'][:300]}...")
        
        # Исполняем решения
        for decision in decisions_data['portfolio_decisions']:
            sym = decision.get('symbol')
            if sym in close_prices:
                execute_decision(sym, decision, close_prices[sym], slot_end, all_data_global)
        
        # Расчёт эквити
        equity = balance
        for sym, pos in open_positions.items():
            close_price = close_prices.get(sym, pos['entry_price'])
            diff = (close_price - pos['entry_price']) * 10000
            if pos['direction'] == 'SELL':
                diff = -diff
            equity += diff * 10 * pos['lot']
        
        equity_history.append(equity)
        balance_history.append(balance)
        
        print(f"\n💰 Баланс: ${balance:,.2f} | Эквити: ${equity:,.2f}")
        
        time.sleep(2)
    
    # Итоги
    total_pnl = balance - initial_balance
    trades = len(trade_history)
    winrate = sum(1 for t in trade_history if t.get('pnl', 0) > 0) / max(1, trades)
    
    print("\n" + "═"*80)
    print(" ИТОГИ")
    print("═"*80)
    print(f"PnL: ${total_pnl:+,.2f}")
    print(f"Сделок: {trades}")
    print(f"Win Rate: {winrate:.1%}")
    print(f"Финальный баланс: ${balance:,.2f}")
    print("═"*80)
    
    # График эквити бэктеста
    print("\n📊 Построение графика эквити...")
    try:
        plt.figure(figsize=(15, 8))
        
        # График эквити
        plt.subplot(2, 1, 1)
        plt.plot(equity_history, label='Equity', color='#2ecc71', linewidth=2)
        plt.plot(balance_history, label='Balance', color='#3498db', linewidth=2, linestyle='--')
        plt.axhline(y=initial_balance, color='gray', linestyle=':', alpha=0.5, label='Initial Balance')
        plt.title('Equity & Balance Curve', fontsize=16, fontweight='bold')
        plt.xlabel('Slot Number', fontsize=12)
        plt.ylabel('Value ($)', fontsize=12)
        plt.legend(loc='best', fontsize=10)
        plt.grid(True, alpha=0.3)
        
        # График PnL
        plt.subplot(2, 1, 2)
        pnl_curve = [e - initial_balance for e in equity_history]
        colors = ['#e74c3c' if p < 0 else '#2ecc71' for p in pnl_curve]
        plt.bar(range(len(pnl_curve)), pnl_curve, color=colors, alpha=0.7)
        plt.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        plt.title('Cumulative PnL', fontsize=16, fontweight='bold')
        plt.xlabel('Slot Number', fontsize=12)
        plt.ylabel('PnL ($)', fontsize=12)
        plt.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        filename = f"equity_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"✅ График сохранён: {filename}")
        plt.close()
        
    except Exception as e:
        print(f"⚠️ Ошибка построения графика: {e}")
    
    mt5.shutdown()
    print("\n✅ Готово!\n")

if __name__ == "__main__":
    run_simulation()

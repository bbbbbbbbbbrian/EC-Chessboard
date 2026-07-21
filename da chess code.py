import RPi.GPIO as GPIO
import chess
import time
import os
import sys
import select
from RPLCD.i2c import CharLCD

LOG_FILENAME = "chess_history.txt"

try:
    lcd = CharLCD('PCF8574', 0x27)
    lcd.clear()
except Exception:
    lcd = None

ROW_PINS = [17, 27, 22, 10, 9, 11, 0, 5]   
COL_PINS = [6, 13, 19, 26, 21, 20, 16, 12]  

FILES = ["a", "b", "c", "d", "e", "f", "g", "h"]
RANKS = ["1", "2", "3", "4", "5", "6", "7", "8"]

def setup_hardware():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    for pin in ROW_PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)

    for pin in COL_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def get_sensors():
    """Scans the 8x8 matrix row-by-row and returns a map of {square: 0/1}."""
    sensors = {}

    for r_idx, r_pin in enumerate(ROW_PINS):
        GPIO.output(r_pin, GPIO.LOW)
        time.sleep(0.001)  

        for c_idx, c_pin in enumerate(COL_PINS):
            square_name = f"{FILES[c_idx]}{RANKS[r_idx]}"
            sensors[square_name] = 1 if GPIO.input(c_pin) == GPIO.LOW else 0
        GPIO.output(r_pin, GPIO.HIGH)

    return sensors

def update_lcd(line1, line2=""):
    if lcd:
        lcd.clear()
        lcd.write_string(line1[:16])
        if line2:
            lcd.cursor_pos = (1, 0)
            lcd.write_string(line2[:16])

def draw_ui(board, current_sensors, error_msg=""):
    os.system('clear')
    print("═" * 45)
    print("       SMART CHESS: FULL BOARD MATRIX MODE")
    print("═" * 45)
    print(board)
    print("─" * 45)

    print(" Physical Sensor Matrix (1 = Piece Present):")
    for r in reversed(RANKS): 
        row_str = f" {r} | "
        for f in FILES:
            status = "X" if current_sensors.get(f + r) == 1 else "."
            row_str += f"{status} "
        print(row_str)
    print("     " + " ".join(FILES))

    last_move = board.peek().uci().upper() if board.move_stack else "START"
    print("─" * 45)

    if error_msg:
        print(f" ERROR: {error_msg}")
        update_lcd("ILLEGAL MOVE!", error_msg)
    else:
        status = "CHECK!" if board.is_check() else f"Turn: {'White' if board.turn else 'Black'}"
        print(f"LAST: {last_move} | {status}")
        update_lcd(f"Last: {last_move}", status)

    print("PROMPT > ", end='', flush=True)

def main():
    setup_hardware()
    board = chess.Board()
    last_sensors = get_sensors()
    draw_ui(board, last_sensors)

    try:
        while not board.is_game_over():
            current_sensors = get_sensors()

            if current_sensors != last_sensors:
                draw_ui(board, current_sensors)
                time.sleep(0.8)
                new_sensors = get_sensors()

                removed = [s for s in new_sensors if last_sensors[s] == 1 and new_sensors[s] == 0]
                added = [s for s in new_sensors if last_sensors[s] == 0 and new_sensors[s] == 1]

                if removed and added:
                    from_sq = removed[0]
                    to_sq = added[0]
                    move_uci = from_sq + to_sq

                    if board.piece_at(chess.parse_square(from_sq)):
                        piece = board.piece_at(chess.parse_square(from_sq))
                        if piece.piece_type == chess.PAWN:
                            if (piece.color == chess.WHITE and to_sq[1] == '8') or \
                               (piece.color == chess.BLACK and to_sq[1] == '1'):
                                move_uci += 'q'

                    try:
                        move = chess.Move.from_uci(move_uci)
                        if move in board.legal_moves:
                            board.push(move)
                            last_sensors = new_sensors
                            draw_ui(board, last_sensors)
                        else:
                            draw_ui(board, new_sensors, error_msg=move_uci.upper())
                            time.sleep(2)
                            last_sensors = get_sensors()
                            draw_ui(board, last_sensors)
                    except Exception:
                        pass
                else:
                    last_sensors = new_sensors
                    draw_ui(board, last_sensors)

            if select.select([sys.stdin], [], [], 0.05)[0]:
                user_input = sys.stdin.readline().strip().lower()
                if user_input == 'quit':
                    break
                try:
                    move = chess.Move.from_uci(user_input)
                    if move in board.legal_moves:
                        board.push(move)
                        last_sensors = get_sensors()
                        draw_ui(board, last_sensors)
                    else:
                        update_lcd("ILLEGAL INPUT!", user_input.upper())
                        time.sleep(1.5)
                        draw_ui(board, last_sensors)
                except Exception:
                    pass

    finally:
        GPIO.cleanup()
        if lcd:
            lcd.clear()

if __name__ == "__main__":
    main()